from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q
from django.db import transaction, IntegrityError
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.urls import reverse
from datetime import timedelta
from decimal import Decimal
import logging
from core.models import (
    TeacherProfile, Subject, ClassSection, StudentProfile, Attendance, Grade, Notification,
    Assessment, AssessmentScore, CategoryWeights, AuditLog, TeacherSubjectAssignment, StudentEnrollment,
    Semester
)
from teachers.forms import AddStudentToAssignmentForm, TeacherSubjectAssignmentForm
from django.db.models import Avg
from core.notifications import send_attendance_notification, check_and_send_performance_notifications, check_consecutive_absences
from core.permissions import role_required, validate_input, validate_teacher_access
from core.db_functions import get_teacher_class_statistics
from django.http import JsonResponse
import json
from django.views.decorators.http import require_http_methods

logger = logging.getLogger(__name__)

@login_required
def dashboard(request):
    # Ensure user is a teacher
    if request.user.role != 'teacher':
        return redirect('dashboard')
    
    try:
        teacher_profile = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        return redirect('dashboard')
    
    # Get current semester
    current_semester = Semester.get_current()
    
    # Get teacher's subject assignments (new architecture) - filter by current semester
    assignments = TeacherSubjectAssignment.objects.filter(
        teacher=teacher_profile
    )
    if current_semester:
        assignments = assignments.filter(semester=current_semester)
    assignments = assignments.select_related('subject', 'section').order_by('subject__code', 'section__name')
    
    # Get unique subjects from assignments
    subjects = [assignment.subject for assignment in assignments]
    
    # Get classes/sections the teacher is advising
    advised_sections = ClassSection.objects.filter(adviser=teacher_profile)
    
    # Get all students enrolled in teacher's assignments for the active semester
    # Count unique students enrolled in the teacher's assignments for the active semester
    teacher_enrollments_for_count = StudentEnrollment.objects.filter(
        assignment__teacher=teacher_profile,
        is_active=True
    )
    if current_semester:
        teacher_enrollments_for_count = teacher_enrollments_for_count.filter(semester=current_semester)
    student_count = teacher_enrollments_for_count.values('student').distinct().count()
    
    # Get recent attendance records for teacher's assignments - filter by current semester
    recent_attendance = Attendance.objects.filter(
        enrollment__assignment__teacher=teacher_profile
    )
    if current_semester:
        recent_attendance = recent_attendance.filter(enrollment__semester=current_semester)
    recent_attendance = recent_attendance.select_related('enrollment', 'enrollment__student', 'enrollment__assignment__subject').order_by('-date')[:10]
    
    # Get attendance statistics - filter by current semester
    total_attendance = Attendance.objects.filter(enrollment__assignment__teacher=teacher_profile)
    if current_semester:
        total_attendance = total_attendance.filter(enrollment__semester=current_semester)
    present_count = total_attendance.filter(status='present').count()
    absent_count = total_attendance.filter(status='absent').count()
    late_count = total_attendance.filter(status='late').count()
    total_attendance_count = total_attendance.count()
    
    # Calculate average attendance percentage
    avg_attendance_percentage = (present_count / total_attendance_count * 100) if total_attendance_count > 0 else 0
    
    # Calculate subject performance data (average grades per subject-section)
    # This will be used for both the chart and the overall class average
    subject_performance_data = []
    subject_performance_labels = []
    subject_section_averages = []  # Store averages for calculating overall class average
    
    # Debug: Log total subjects found
    logger = logging.getLogger(__name__)
    logger.debug(f"Total subjects found for teacher {teacher_profile.id}: {len(subjects)}")
    
    # Process ALL assignments (each assignment is unique per subject-section combination)
    # Calculate average for each subject-section combination
    for assignment in assignments:
        subject = assignment.subject
        section = assignment.section
        
        # Debug: Log assignment being processed
        logger.debug(f"Processing assignment ID {assignment.id}: subject='{subject.code}', section='{section.name if section else None}'")
        
        # Always create the label first (we'll add it regardless of data)
        section_name = section.name if section else None
        if section_name:
            # Check if section name is already part of the code (e.g., "IT101-BSIT1A")
            section_abbrev = section_name.replace(' ', '')
            if section_abbrev in subject.code:
                # Section info already in code, just use code
                label = subject.code
            else:
                # Add section name to distinguish between sections
                label = f"{subject.code} ({section_name})"
        else:
            label = subject.code
        
        # Calculate average for this assignment (subject-section combination)
        # Get enrollments for this assignment in the active semester, then get grades
        enrollments = StudentEnrollment.objects.filter(assignment=assignment, is_active=True)
        if current_semester:
            enrollments = enrollments.filter(semester=current_semester)
        subject_grades = Grade.objects.filter(enrollment__in=enrollments)
        has_data = False
        subject_avg = None
        assessment_scores_count = 0
        
        if subject_grades.exists():
            # Calculate from Grade records
            subject_avg_result = subject_grades.aggregate(Avg('grade'))['grade__avg']
            if subject_avg_result is not None:
                subject_avg = float(subject_avg_result)
                has_data = True
                logger.debug(f"Subject {subject.code} ({section.name if section else 'No section'}): Found {subject_grades.count()} Grade records, Average = {subject_avg:.2f}%")
        else:
            # Fallback: Calculate from assessment scores if Grade records don't exist
            # Get assessments for this assignment
            assessments = Assessment.objects.filter(assignment=assignment)
            assessment_scores = AssessmentScore.objects.filter(
                assessment__in=assessments
            ).select_related('assessment')
            assessment_scores_count = assessment_scores.count()
            
            if assessment_scores.exists():
                # Calculate average from assessment scores
                total_score = sum(float(score.score) for score in assessment_scores)
                total_max = sum(float(score.assessment.max_score) for score in assessment_scores)
                if total_max > 0:
                    subject_avg = (total_score / total_max) * 100
                    has_data = True
                    logger.debug(f"Subject {subject.code} ({section.name if section else 'No section'}): No Grade records, but found {assessment_scores_count} AssessmentScore records, Average = {subject_avg:.2f}%")
        
        # Always add both data and label together to ensure they match
        if has_data and subject_avg is not None:
            rounded_avg = round(subject_avg, 2)
            subject_performance_data.append(rounded_avg)
            subject_section_averages.append(subject_avg)  # Store for class average calculation
        else:
            # Show 0 for subjects without data
            subject_performance_data.append(0)
            logger.debug(f"Subject {subject.code} ({section.name if section else 'No section'}): No data found (Grade count: {subject_grades.count()}, Assessment scores: {assessment_scores_count})")
        
        # Always add the label (ensures data and labels arrays have same length)
        subject_performance_labels.append(label)
    
    # Debug: Log final arrays
    logger.debug(f"Subject performance data array length: {len(subject_performance_data)}, Labels array length: {len(subject_performance_labels)}")
    logger.debug(f"Subject performance data: {subject_performance_data}")
    logger.debug(f"Subject performance labels: {subject_performance_labels}")
    
    # Calculate class average as the average of all subject-section averages
    # This gives the overall average across all subject-sections for the active semester
    if subject_section_averages:
        average_grade = sum(subject_section_averages) / len(subject_section_averages)
        # Count total number of Grade records for this teacher in the active semester
        # Get all enrollments for teacher's assignments in the active semester
        teacher_enrollments = StudentEnrollment.objects.filter(
            assignment__teacher=teacher_profile,
            is_active=True
        )
        if current_semester:
            teacher_enrollments = teacher_enrollments.filter(semester=current_semester)
        grades_count = Grade.objects.filter(enrollment__in=teacher_enrollments).count()
    else:
        # Fallback: If no subject-section averages, try to calculate from all grades
        # Filter by active semester
        teacher_enrollments = StudentEnrollment.objects.filter(
            assignment__teacher=teacher_profile,
            is_active=True
        )
        if current_semester:
            teacher_enrollments = teacher_enrollments.filter(semester=current_semester)
        total_grades = Grade.objects.filter(enrollment__in=teacher_enrollments)
        grades_count = total_grades.count()
        
        if grades_count > 0:
            average_grade_result = total_grades.aggregate(Avg('grade'))['grade__avg']
            if average_grade_result is not None:
                average_grade = float(average_grade_result)
            else:
                average_grade = 0
        else:
            # Final fallback: Calculate from assessment scores
            # Get assessments for teacher's assignments in the active semester
            teacher_assessments = Assessment.objects.filter(assignment__teacher=teacher_profile)
            if current_semester:
                teacher_assessments = teacher_assessments.filter(assignment__semester=current_semester)
            # Filter assessment scores by enrollments in the active semester
            assessment_scores = AssessmentScore.objects.filter(
                assessment__in=teacher_assessments
            )
            if current_semester:
                assessment_scores = assessment_scores.filter(enrollment__semester=current_semester)
            assessment_scores = assessment_scores.select_related('assessment')
            
            if assessment_scores.exists():
                total_score = sum(float(score.score) for score in assessment_scores)
                total_max = sum(float(score.assessment.max_score) for score in assessment_scores)
                if total_max > 0:
                    average_grade = (total_score / total_max) * 100
                else:
                    average_grade = 0
            else:
                average_grade = 0
    
    # Get unread notifications
    notifications = Notification.objects.filter(recipient=request.user, is_read=False).order_by('-created_at')[:5]
    unread_notifications_count = Notification.objects.filter(recipient=request.user, is_read=False).count()
    
    # Calculate grade distribution
    # Get all students in teacher's sections and their average grades
    # Include ALL sections where the teacher teaches subjects
    section_ids = list(set([assignment.section.id for assignment in assignments if assignment.section]))
    logger.debug(f"Grade distribution: Found {len(section_ids)} unique sections: {section_ids}")

    students_in_sections = StudentProfile.objects.filter(section__id__in=section_ids).select_related('section', 'user') if section_ids else StudentProfile.objects.none()
    logger.debug(f"Grade distribution: Found {students_in_sections.count()} students across all sections")

    excellent_count = 0
    good_count = 0
    average_count = 0
    poor_count = 0

    students_by_section = {}
    for student in students_in_sections:
        section_name = student.section.name if student.section else "No Section"
        if section_name not in students_by_section:
            students_by_section[section_name] = 0
        students_by_section[section_name] += 1
        
        student_avg = None
        
        # Try to get average from Grade records first
        # Calculate average across ALL assignments the teacher teaches for this student in the active semester
        # Get enrollments for this student in teacher's assignments in the active semester
        student_enrollments = StudentEnrollment.objects.filter(
            student=student,
            assignment__teacher=teacher_profile,
            is_active=True
        )
        if current_semester:
            student_enrollments = student_enrollments.filter(semester=current_semester)
        student_grades = Grade.objects.filter(enrollment__in=student_enrollments)
        if student_grades.exists():
            # Get the subjects these grades are for
            grade_subjects = student_grades.values_list('enrollment__assignment__subject__code', 'enrollment__assignment__section__name').distinct()
            student_avg_result = student_grades.aggregate(Avg('grade'))['grade__avg']
            if student_avg_result is not None:
                student_avg = float(student_avg_result)
                logger.debug(f"Student {student.user.get_full_name()} ({section_name}): Found {student_grades.count()} Grade records across {len(grade_subjects)} subjects {list(grade_subjects)}, Average = {student_avg:.2f}%")
        
        # Fallback: Calculate from assessment scores if Grade records don't exist
        if student_avg is None:
            # Get assessments for teacher's assignments in the active semester
            teacher_assessments = Assessment.objects.filter(assignment__teacher=teacher_profile)
            if current_semester:
                teacher_assessments = teacher_assessments.filter(assignment__semester=current_semester)
            # Get scores for this student in the active semester
            student_enrollments = StudentEnrollment.objects.filter(
                student=student,
                assignment__teacher=teacher_profile,
                is_active=True
            )
            if current_semester:
                student_enrollments = student_enrollments.filter(semester=current_semester)
            assessment_scores = AssessmentScore.objects.filter(
                enrollment__in=student_enrollments,
                assessment__in=teacher_assessments
            ).select_related('assessment', 'assessment__assignment__subject')
            
            if assessment_scores.exists():
                # Calculate average from assessment scores
                total_score = sum(float(score.score) for score in assessment_scores)
                total_max = sum(float(score.assessment.max_score) for score in assessment_scores)
                if total_max > 0:
                    student_avg = (total_score / total_max) * 100
                    # Get subjects these scores are for
                    score_subjects = assessment_scores.values_list('assessment__assignment__subject__code', 'assessment__assignment__section__name').distinct()
                    logger.debug(f"Student {student.user.get_full_name()} ({section_name}): No Grade records, but found {assessment_scores.count()} AssessmentScore records across {len(score_subjects)} subjects {list(score_subjects)}, Average = {student_avg:.2f}%")
        
        # Categorize student based on average
        # Only count students who have grades (students without any grades are not included in distribution)
        if student_avg is not None:
            if student_avg >= 90:
                excellent_count += 1
            elif student_avg >= 80:
                good_count += 1
            elif student_avg >= 70:
                average_count += 1
            else:
                poor_count += 1
        else:
            logger.debug(f"Student {student.user.get_full_name()} ({section_name}): No grades or assessment scores found")
    
    # Debug: Log grade distribution summary
    logger.debug(f"Grade distribution summary: Excellent={excellent_count}, Good={good_count}, Average={average_count}, Poor={poor_count}")
    logger.debug(f"Students by section: {students_by_section}")
    
    # Also print to console for immediate visibility (remove in production)
    print(f"\n=== GRADE DISTRIBUTION DEBUG ===")
    print(f"Total students checked: {students_in_sections.count()}")
    print(f"Students by section: {students_by_section}")
    print(f"Excellent: {excellent_count}, Good: {good_count}, Average: {average_count}, Poor: {poor_count}")
    print(f"Total with grades: {excellent_count + good_count + average_count + poor_count}")
    print(f"===================================\n")
    
    # Get subject statistics using database function
    teacher_stats = get_teacher_class_statistics(teacher_id=teacher_profile.id)
    if 'error' not in teacher_stats and 'statistics' in teacher_stats:
        # Use function results
        subject_stats = []
        for stat in teacher_stats['statistics']:
            # Find the subject object
            try:
                subject = Subject.objects.get(id=stat['subject_id'])
                subject_stats.append({
                    'subject': subject,
                    'student_count': stat.get('student_count', 0),
                    'average_grade': stat.get('average_grade', 0),
                    'grades_count': 0,  # Not provided by function, will calculate if needed
                    'at_risk_students': stat.get('at_risk_students', 0)
                })
            except Subject.DoesNotExist:
                continue
    else:
        # Fallback to manual calculation if function fails
        # Note: assignments are already filtered by current_semester above
        subject_stats = []
        for assignment in assignments:
            subject = assignment.subject
            section = assignment.section
            # Get enrolled students for this assignment in the active semester
            enrollments = StudentEnrollment.objects.filter(assignment=assignment, is_active=True)
            if current_semester:
                enrollments = enrollments.filter(semester=current_semester)
            subject_students = enrollments.count()
            subject_grades = Grade.objects.filter(enrollment__in=enrollments)
            subject_avg = subject_grades.aggregate(Avg('grade'))['grade__avg'] or 0
            subject_stats.append({
                'subject': subject,
                'student_count': subject_students,
                'average_grade': round(subject_avg, 2),
                'grades_count': subject_grades.count()
            })
    
    # Calculate weekly attendance data (last 7 days) for the active semester
    today = timezone.now().date()
    weekly_attendance_data = []
    weekly_attendance_labels = []
    
    for i in range(6, -1, -1):  # Last 7 days (6 days ago to today)
        date = today - timedelta(days=i)
        date_attendance = Attendance.objects.filter(
            enrollment__assignment__teacher=teacher_profile,
            date=date
        )
        if current_semester:
            date_attendance = date_attendance.filter(enrollment__semester=current_semester)
        present = date_attendance.filter(status='present').count()
        absent = date_attendance.filter(status='absent').count()
        late = date_attendance.filter(status='late').count()
        
        weekly_attendance_data.append({
            'present': present,
            'absent': absent,
            'late': late,
            'total': present + absent + late
        })
        # Format date as "Mon DD" or "Today"
        if i == 0:
            weekly_attendance_labels.append('Today')
        elif i == 1:
            weekly_attendance_labels.append('Yesterday')
        else:
            weekly_attendance_labels.append(date.strftime('%a %d'))
    
    context = {
        'teacher_profile': teacher_profile,
        'subjects': subjects,
        'advised_sections': advised_sections,
        'student_count': student_count,
        'recent_attendance': recent_attendance,
        'present_count': present_count,
        'absent_count': absent_count,
        'late_count': late_count,
        'avg_attendance_percentage': round(avg_attendance_percentage, 1),
        'average_grade': round(average_grade, 2),
        'grades_count': grades_count,
        'notifications': notifications,
        'unread_notifications_count': unread_notifications_count,
        'subject_stats': subject_stats,
        'excellent_count': excellent_count,
        'good_count': good_count,
        'average_count': average_count,
        'poor_count': poor_count,
        'weekly_attendance_data': weekly_attendance_data,
        'weekly_attendance_labels': weekly_attendance_labels,
        'subject_performance_data': subject_performance_data,
        'subject_performance_labels': subject_performance_labels,
        'current_semester': current_semester,
    }
    
    return render(request, 'teachers/dashboard.html', context)

@login_required
@role_required('teacher')
def subjects(request):
    """
    View to list teacher's subject assignments and manage them.
    Shows both legacy Subject assignments and new TeacherSubjectAssignment records.
    """
    try:
        teacher_profile = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        messages.error(request, 'Teacher profile not found.')
        return redirect('dashboard')
    
    # Get current semester
    current_semester = Semester.get_current()
    
    # Get teacher's subject assignments (new architecture) - filter by active semester
    assignments = TeacherSubjectAssignment.objects.filter(
        teacher=teacher_profile
    )
    # Filter by active semester only
    if current_semester:
        assignments = assignments.filter(semester=current_semester)
    else:
        # If no active semester, show empty list
        assignments = assignments.none()
        # Note: Removed automatic warning message to prevent duplicate toasts
    
    assignments = assignments.select_related('subject', 'section', 'semester').order_by('section__name', 'subject__code')
    
    # Group assignments by section
    sections_dict = {}
    total_students = 0
    unique_student_ids = set()
    
    for assignment in assignments:
        section = assignment.section
        
        # Skip assignments without a section (shouldn't happen, but safety check)
        if not section:
            logger.warning(f"Assignment {assignment.id} has no section, skipping")
            continue
            
        section_id = section.id
        
        # Count only enrolled students for this assignment
        student_count = StudentEnrollment.objects.filter(
            assignment=assignment,
            is_active=True
        ).count()
        total_students += student_count
        
        # Get unique enrolled students
        enrolled_students = StudentEnrollment.objects.filter(
            assignment=assignment,
            is_active=True
        ).values_list('student_id', flat=True)
        unique_student_ids.update(enrolled_students)
        
        # Group by section
        if section_id not in sections_dict:
            sections_dict[section_id] = {
                'section': section,
                'assignments': []
            }
        
        sections_dict[section_id]['assignments'].append({
            'id': assignment.id,
            'subject_code': assignment.subject.code if assignment.subject else 'N/A',
            'subject_name': assignment.subject.name if assignment.subject else 'Unknown Subject',
            'student_count': student_count,
        })
    
    # Convert to list format for template
    sections_data = list(sections_dict.values())
    
    # Calculate statistics
    total_subjects = len(assignments)
    total_unique_students = len(unique_student_ids)
    total_sections = len(sections_data)
    avg_students_per_subject = (total_students / total_subjects) if total_subjects > 0 else 0
    
    context = {
        'sections': sections_data,
        'teacher_profile': teacher_profile,
        'total_subjects': total_subjects,
        'total_students': total_unique_students,
        'total_sections': total_sections,
        'avg_students_per_subject': round(avg_students_per_subject, 1),
        'current_semester': current_semester,
    }
    return render(request, 'teachers/subjects.html', context)


@login_required
@role_required('teacher')
def assign_subject(request):
    """
    View to create a new subject assignment.
    Handles both GET (show form) and POST (create assignment).
    """
    try:
        teacher_profile = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        messages.error(request, 'Teacher profile not found.')
        return redirect('teachers:subjects')
    
    # Get current semester and validate it's active
    current_semester = Semester.get_current()
    if not current_semester:
        messages.error(request, 'No active semester is set. Please contact the administrator.')
        return redirect('teachers:subjects')
    
    if current_semester.status != 'active':
        messages.error(
            request,
            f'Cannot assign subjects when semester is {current_semester.get_status_display()}. '
            f'Only active semesters allow subject assignments.'
        )
        return redirect('teachers:subjects')
    
    if request.method == 'POST':
        # Check if subjects were selected
        selected_subjects = request.POST.getlist('subjects')
        if not selected_subjects:
            messages.error(request, 'Please select at least one subject to assign.')
            form = TeacherSubjectAssignmentForm(request.POST, teacher=teacher_profile)
        else:
            form = TeacherSubjectAssignmentForm(request.POST, teacher=teacher_profile)
        
        if form.is_valid():
            try:
                assignments = form.save_many()
                if not assignments:
                    messages.warning(request, 'No new assignments were created. All selected subjects may already be assigned.')
                    return redirect('teachers:subjects')
                
                # Re-fetch all assignments with select_related to ensure relationships are loaded
                assignment_ids = [a.pk for a in assignments if a.pk]
                if not assignment_ids:
                    messages.error(request, 'Assignments were created but could not be retrieved.')
                    return redirect('teachers:subjects')
                
                assignments = TeacherSubjectAssignment.objects.select_related('subject', 'section').filter(pk__in=assignment_ids)
                
                # Filter out any assignments without subjects and collect subject info safely
                valid_assignments = []
                for assignment in assignments:
                    if not assignment.subject_id:
                        logger.warning(f"Assignment {assignment.id} is missing subject_id")
                        continue
                    try:
                        # Try to access subject to ensure it exists
                        subject_code = assignment.subject.code
                        subject_name = assignment.subject.name
                        section_name = assignment.section.name if assignment.section else 'Unknown'
                        valid_assignments.append({
                            'assignment': assignment,
                            'subject_code': subject_code,
                            'subject_name': subject_name,
                            'section_name': section_name
                        })
                    except Exception as e:
                        logger.error(f"Error accessing subject for assignment {assignment.id}: {str(e)}")
                        continue
                
                if not valid_assignments:
                    messages.error(request, 'Assignments were created but none have valid subjects.')
                    return redirect('teachers:subjects')
                
                # Create success message based on number of valid assignments
                if len(valid_assignments) == 1:
                    info = valid_assignments[0]
                    messages.success(
                        request,
                        f'Successfully assigned {info["subject_code"]} ({info["subject_name"]}) to section {info["section_name"]}.'
                    )
                else:
                    subject_codes = [info['subject_code'] for info in valid_assignments]
                    subject_names = ', '.join(subject_codes)
                    section_name = valid_assignments[0]['section_name']
                    messages.success(
                        request,
                        f'Successfully assigned {len(valid_assignments)} subjects ({subject_names}) to section {section_name}.'
                    )
                return redirect('teachers:subjects')
            except ValidationError as e:
                # ValidationError from model - semester status check
                # This should not happen if view-level check works, but handle it gracefully
                # Don't add duplicate message - view already checked and redirected
                error_msg = str(e)
                logger.warning(f"ValidationError caught in assign_subject (should not happen): {error_msg}")
                # Don't add message - view already handled it
                return redirect('teachers:subjects')
            except Exception as e:
                logger.error(f"Error creating subject assignment: {str(e)}", exc_info=True)
                messages.error(request, f'An error occurred while creating the assignment: {str(e)}')
        else:
            # Form has errors, they will be displayed in template
            # Log form errors for debugging
            logger.warning(f"Form validation failed: {form.errors}")
    else:
        form = TeacherSubjectAssignmentForm(teacher=teacher_profile)
    
    context = {
        'form': form,
        'teacher_profile': teacher_profile,
        'current_semester': current_semester,
    }
    return render(request, 'teachers/assign_subject.html', context)


@login_required
@role_required('teacher')
def get_sections_by_year_level(request):
    """AJAX endpoint to get sections for a given year level"""
    year_level_id = request.GET.get('year_level_id')
    
    if not year_level_id:
        return JsonResponse({'error': 'Year level ID is required'}, status=400)
    
    try:
        from core.models import YearLevel, ClassSection
        year_level = YearLevel.objects.get(id=year_level_id)
        sections = ClassSection.objects.filter(
            year_level=year_level
        ).order_by('name').values('id', 'name')
        
        return JsonResponse({
            'sections': list(sections)
        })
    except YearLevel.DoesNotExist:
        return JsonResponse({'error': 'Year level not found'}, status=404)
    except Exception as e:
        logger.error(f"Error getting sections: {str(e)}", exc_info=True)
        return JsonResponse({'error': 'An error occurred'}, status=500)


@login_required
@role_required('teacher')
def get_subjects_by_year_level(request):
    """AJAX endpoint to get subjects for a given year level"""
    year_level_id = request.GET.get('year_level_id')
    
    if not year_level_id:
        return JsonResponse({'error': 'Year level ID is required'}, status=400)
    
    try:
        from core.models import YearLevel, Subject
        year_level = YearLevel.objects.get(id=year_level_id)
        
        # Get subjects for this year level
        # Subjects are organized by year level - we'll match by subject code pattern
        # Year 1: IT101, IT102, etc. (codes like "IT101-BSIT1A")
        # Year 2: IT201, IT202, etc. (codes like "IT201-BSIT2A")
        # Year 3: IT301, IT302, etc. (codes like "IT301-BSIT3A")
        # Year 4: IT401, IT402, etc. (codes like "IT401-BSIT4A")
        level = year_level.level
        # Match subjects that start with the year level number (e.g., IT1xx for year 1)
        # Subjects may have codes like "IT101-BSIT1A", so we match the base code pattern
        subjects = Subject.objects.filter(
            is_active=True,
            code__startswith=f'IT{level}'
        ).order_by('code', 'name').values('id', 'code', 'name')
        
        return JsonResponse({
            'subjects': list(subjects)
        })
    except YearLevel.DoesNotExist:
        return JsonResponse({'error': 'Year level not found'}, status=404)
    except Exception as e:
        logger.error(f"Error getting subjects: {str(e)}", exc_info=True)
        return JsonResponse({'error': 'An error occurred'}, status=500)


@login_required
@role_required('teacher')
@require_http_methods(["POST"])
def remove_assignment(request, assignment_id):
    """
    View to remove a subject assignment.
    Only allows teachers to remove their own assignments.
    Requires POST method for security.
    """
    try:
        teacher_profile = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        messages.error(request, 'Teacher profile not found.')
        return redirect('teachers:subjects')
    
    # Validate assignment_id
    assignment_id = validate_input(assignment_id, 'integer')
    if not assignment_id:
        messages.error(request, 'Invalid assignment ID.')
        return redirect('teachers:subjects')
    
    try:
        assignment = TeacherSubjectAssignment.objects.get(
            id=assignment_id,
            teacher=teacher_profile
        )
        subject_code = assignment.subject.code
        section_name = assignment.section.name
        assignment.delete()
        messages.success(
            request,
            f'Successfully removed assignment: {subject_code} in section {section_name}.'
        )
    except TeacherSubjectAssignment.DoesNotExist:
        messages.error(request, 'Assignment not found or you do not have permission to remove it.')
    except Exception as e:
        logger.error(f"Error removing assignment: {str(e)}", exc_info=True)
        messages.error(request, 'An error occurred while removing the assignment.')
    
    return redirect('teachers:subjects')

@login_required
def sections(request):
    if request.user.role != 'teacher':
        return redirect('dashboard')
    
    try:
        teacher_profile = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        return redirect('dashboard')
    
    # Get sections where teacher is adviser
    advised_section_ids = ClassSection.objects.filter(adviser=teacher_profile).values_list('id', flat=True)
    
    # Get current semester
    current_semester = Semester.get_current()
    
    # Get sections where teacher teaches subjects (through assignments) - filter by active semester
    sections_with_subjects_filter = ClassSection.objects.filter(
        teacher_subject_assignments__teacher=teacher_profile
    )
    if current_semester:
        sections_with_subjects_filter = sections_with_subjects_filter.filter(
            teacher_subject_assignments__semester=current_semester
        )
    sections_with_subjects_ids = sections_with_subjects_filter.values_list('id', flat=True).distinct()
    
    # Combine both sets of IDs
    all_section_ids = set(list(advised_section_ids) + list(sections_with_subjects_ids))
    
    # Get all unique sections
    all_sections = ClassSection.objects.filter(id__in=all_section_ids).order_by('name')
    
    # Calculate statistics for each section
    sections_data = []
    total_students_all = 0
    total_attendance_present = 0
    total_attendance_count = 0
    total_grades_sum = 0
    total_grades_count = 0
    
    for section in all_sections:
        # Get assignments teacher has in this section - filter by active semester
        section_assignments = TeacherSubjectAssignment.objects.filter(
            teacher=teacher_profile,
            section=section
        )
        if current_semester:
            section_assignments = section_assignments.filter(semester=current_semester)
        section_assignments = section_assignments.select_related('subject', 'section').order_by('subject__code')
        
        # Calculate attendance for this section
        # Get enrollments for this section's assignments
        section_enrollments = StudentEnrollment.objects.filter(
            assignment__teacher=teacher_profile,
            assignment__section=section,
            is_active=True
        )
        
        # Count unique enrolled students in this section (across all assignments)
        enrolled_student_ids = section_enrollments.values_list('student_id', flat=True).distinct()
        student_count = len(enrolled_student_ids)
        total_students_all += student_count
        section_attendance = Attendance.objects.filter(
            enrollment__in=section_enrollments
        )
        present_count = section_attendance.filter(status='present').count()
        total_attendance = section_attendance.count()
        attendance_percentage = (present_count / total_attendance * 100) if total_attendance > 0 else 0
        
        total_attendance_present += present_count
        total_attendance_count += total_attendance
        
        # Calculate average grade for this section
        section_grades = Grade.objects.filter(
            enrollment__in=section_enrollments
        )
        if section_grades.exists():
            avg_grade = section_grades.aggregate(Avg('grade'))['grade__avg'] or 0
            total_grades_sum += avg_grade * section_grades.count()
            total_grades_count += section_grades.count()
        else:
            avg_grade = 0
        
        sections_data.append({
            'section': section,
            'student_count': student_count,
            'assignments': list(section_assignments),  # Pass actual TeacherSubjectAssignment objects
            'attendance_percentage': round(attendance_percentage, 1) if attendance_percentage else 0,
            'avg_grade': round(avg_grade, 2) if avg_grade else 0,
        })
    
    # Calculate overall statistics
    total_sections = all_sections.count()
    overall_attendance = (total_attendance_present / total_attendance_count * 100) if total_attendance_count > 0 else 0
    overall_avg_grade = (total_grades_sum / total_grades_count) if total_grades_count > 0 else 0
    
    context = {
        'sections': sections_data,
        'total_sections': total_sections,
        'total_students': total_students_all,
        'overall_attendance': round(overall_attendance, 1),
        'overall_avg_grade': round(overall_avg_grade, 2),
    }
    return render(request, 'teachers/sections.html', context)

@login_required
def students(request):
    if request.user.role != 'teacher':
        return redirect('dashboard')
    
    try:
        teacher_profile = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        return redirect('dashboard')
    
    # Get current semester
    current_semester = Semester.get_current()
    
    # Get assignment filter from query parameter (optional)
    assignment_id = request.GET.get('assignment')
    selected_assignment = None
    
    # Get assignments for this teacher - filter by active semester
    assignments = TeacherSubjectAssignment.objects.filter(
        teacher=teacher_profile
    )
    if current_semester:
        assignments = assignments.filter(semester=current_semester)
    else:
        assignments = assignments.none()
        # Note: Removed automatic warning message to prevent duplicate toasts
    
    assignments = assignments.select_related('subject', 'section').order_by('subject__code', 'subject__name')
    
    # Filter by assignment if specified
    if assignment_id:
        try:
            selected_assignment = TeacherSubjectAssignment.objects.get(
                id=assignment_id,
                teacher=teacher_profile
            )
            assignments = assignments.filter(id=assignment_id)
        except TeacherSubjectAssignment.DoesNotExist:
            messages.error(request, 'Assignment not found or access denied.')
            return redirect('teachers:students')
    
    # Get subjects with their students
    subjects_data = []
    unique_student_ids = set()
    student_status_map = {}  # Track overall status per student
    
    for assignment in assignments:
        subject = assignment.subject
        section = assignment.section
        
        # Get enrolled students for this assignment
        enrollments = StudentEnrollment.objects.filter(
            assignment=assignment,
            is_active=True
        ).select_related('student', 'student__user', 'student__section')
        
        enrolled_students = [e.student for e in enrollments]
        student_count = len(enrolled_students)
        # Show assignment even if no students when filtering by assignment
        if student_count == 0 and not selected_assignment:
            continue
        
        # Sort students by name
        enrolled_students.sort(key=lambda s: (s.user.last_name, s.user.first_name))
        
        # Calculate statistics for each student in this assignment
        students_data = []
        subject_attendance_sum = 0
        subject_grades_sum = 0
        subject_grades_count = 0
        
        # Process students if any exist
        if student_count > 0:
            for student in enrolled_students:
                # Track unique students across all subjects
                unique_student_ids.add(student.id)
                
                # Get enrollment for this student-assignment combination
                enrollment = StudentEnrollment.objects.get(
                    student=student,
                    assignment=assignment,
                    is_active=True
                )
                
                # Calculate attendance percentage for this specific enrollment
                student_attendance = Attendance.objects.filter(
                    enrollment=enrollment
                )
                total_attendance = student_attendance.count()
                present_count = student_attendance.filter(status='present').count()
                attendance_percentage = (present_count / total_attendance * 100) if total_attendance > 0 else 0
                subject_attendance_sum += attendance_percentage
                
                # Calculate grade for this specific enrollment
                student_grades = Grade.objects.filter(
                    enrollment=enrollment
                )
                if student_grades.exists():
                    gpa = student_grades.aggregate(Avg('grade'))['grade__avg'] or 0
                    subject_grades_sum += gpa
                    subject_grades_count += 1
                else:
                    gpa = 0
                
                # Determine status based on this subject's performance
                if attendance_percentage >= 80 and gpa >= 80:
                    status = 'active'
                elif attendance_percentage < 70 or gpa < 70:
                    status = 'at_risk'
                else:
                    status = 'active'
                
                # Track overall status (if at_risk in any subject, mark as at_risk)
                if student.id not in student_status_map:
                    student_status_map[student.id] = status
                elif status == 'at_risk':
                    student_status_map[student.id] = 'at_risk'
                
                students_data.append({
                    'student': student,
                    'attendance_percentage': round(attendance_percentage, 1),
                    'gpa': round(gpa, 2),
                    'status': status,
                })
        
        # Calculate subject averages
        avg_attendance = (subject_attendance_sum / student_count) if student_count > 0 else 0
        avg_gpa = (subject_grades_sum / subject_grades_count) if subject_grades_count > 0 else 0
        
        subjects_data.append({
            'subject': subject,
            'assignment': assignment,  # Include assignment for section info
            'section': section,
            'students': students_data,
            'student_count': student_count,
            'avg_attendance': round(avg_attendance, 1),
            'avg_gpa': round(avg_gpa, 2),
        })
    
    # Calculate total counts based on unique students
    total_students_count = len(unique_student_ids)
    active_students_count = sum(1 for status in student_status_map.values() if status == 'active')
    at_risk_count = sum(1 for status in student_status_map.values() if status == 'at_risk')
    
    # Sort subjects by code
    subjects_data.sort(key=lambda x: (x['subject'].code, x['subject'].name))
    
    context = {
        'subjects': subjects_data,
        'total_students': total_students_count,
        'active_students': active_students_count,
        'at_risk_students': at_risk_count,
        'total_subjects': len(subjects_data),
        'selected_assignment': selected_assignment,
        'all_assignments': TeacherSubjectAssignment.objects.filter(
            teacher=teacher_profile
        ).select_related('subject', 'section').order_by('subject__code', 'subject__name'),
    }
    return render(request, 'teachers/students.html', context)


@login_required
@role_required('teacher')
def add_student(request):
    """
    View to add students to a subject assignment.
    Handles both GET (show form) and POST (enroll students).
    """
    try:
        teacher_profile = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        messages.error(request, 'Teacher profile not found.')
        return redirect('teachers:students')
    
    # Get assignment from query parameter (required)
    assignment_id = request.GET.get('assignment')
    if not assignment_id:
        messages.error(request, 'Please select a subject assignment.')
        return redirect('teachers:students')
    
    try:
        assignment = TeacherSubjectAssignment.objects.get(
            id=assignment_id,
            teacher=teacher_profile
        )
    except TeacherSubjectAssignment.DoesNotExist:
        messages.error(request, 'Assignment not found or access denied.')
        return redirect('teachers:students')
    
    # Check if semester allows enrollment
    if assignment.semester and not assignment.semester.can_enroll_students():
        messages.error(
            request,
            f'Cannot enroll students in {assignment.semester.get_status_display()} semester.'
        )
        return redirect('teachers:students')
    
    if request.method == 'POST':
        form = AddStudentToAssignmentForm(request.POST, assignment=assignment)
        if form.is_valid():
            try:
                enrollments = form.save()
                if enrollments:
                    count = len(enrollments)
                    messages.success(
                        request,
                        f'Successfully enrolled {count} student{"s" if count > 1 else ""} in '
                        f'{assignment.subject.code} ({assignment.section.name}).'
                    )
                else:
                    messages.warning(request, 'No students were enrolled. They may already be enrolled.')
                
                # Redirect back to students page with assignment filter
                return redirect(f"{reverse('teachers:students')}?assignment={assignment.id}")
            except Exception as e:
                logger.error(f"Error enrolling students: {str(e)}", exc_info=True)
                messages.error(request, f'An error occurred while enrolling students: {str(e)}')
        else:
            # Form has errors, they will be displayed in template
            logger.warning(f"Form validation failed: {form.errors}")
    else:
        form = AddStudentToAssignmentForm(assignment=assignment)
    
    # Get available students count for display
    available_students_count = form.fields['students'].queryset.count()
    
    # Get currently enrolled students count
    enrolled_count = StudentEnrollment.objects.filter(
        assignment=assignment,
        is_active=True
    ).count()
    
    context = {
        'form': form,
        'assignment': assignment,
        'teacher_profile': teacher_profile,
        'available_students_count': available_students_count,
        'enrolled_count': enrolled_count,
    }
    return render(request, 'teachers/add_student.html', context)


@login_required
@role_required('teacher')
def enroll_student(request):
    """
    Main enrollment flow view - 3-step process:
    1. Search student
    2. Select subject & section
    3. Confirm enrollment
    """
    try:
        teacher_profile = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        messages.error(request, 'Teacher profile not found.')
        return redirect('teachers:students')
    
    # Get current semester
    current_semester = Semester.get_current()
    
    if not current_semester:
        messages.error(request, 'No active semester is set. Please contact the administrator.')
        return redirect('teachers:students')
    
    if not current_semester.can_enroll_students():
        messages.error(
            request,
            f'Enrollment is not allowed for {current_semester.get_status_display()} semester.'
        )
        return redirect('teachers:students')
    
    context = {
        'teacher_profile': teacher_profile,
        'current_semester': current_semester,
    }
    return render(request, 'teachers/enroll_student.html', context)


@login_required
@role_required('teacher')
@require_http_methods(["GET"])
def search_students(request):
    """
    AJAX endpoint to search students by ID or Name.
    Returns only active students.
    """
    try:
        teacher_profile = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        return JsonResponse({'error': 'Teacher profile not found'}, status=404)
    
    query = request.GET.get('q', '').strip()
    
    if not query or len(query) < 2:
        return JsonResponse({'students': []})
    
    # Search by student_id or name (first_name, last_name, username)
    students = StudentProfile.objects.filter(
        Q(student_id__icontains=query) |
        Q(user__first_name__icontains=query) |
        Q(user__last_name__icontains=query) |
        Q(user__username__icontains=query)
    ).select_related('user', 'section', 'year_level').order_by('user__last_name', 'user__first_name')[:20]
    
    # Format results
    results = []
    for student in students:
        results.append({
            'id': student.id,
            'student_id': student.student_id,
            'name': student.user.get_full_name() or student.user.username,
            'email': student.user.email or '',
            'section': student.section.name if student.section else 'No Section',
            'year_level': student.year_level.name if student.year_level else 'N/A',
        })
    
    return JsonResponse({'students': results})


@login_required
@role_required('teacher')
@require_http_methods(["GET"])
def get_eligible_assignments(request):
    """
    AJAX endpoint to get eligible assignments for a selected student.
    Returns only teacher's assignments for current semester, excluding already enrolled.
    """
    try:
        teacher_profile = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        return JsonResponse({'error': 'Teacher profile not found'}, status=404)
    
    # Validate student_id
    student_id = validate_input(request.GET.get('student_id'), 'integer')
    if not student_id:
        return JsonResponse({'error': 'Invalid student ID'}, status=400)
    
    try:
        student = StudentProfile.objects.select_related('user', 'section', 'year_level').get(id=student_id)
    except StudentProfile.DoesNotExist:
        return JsonResponse({'error': 'Student not found'}, status=404)
    
    # Get current semester
    current_semester = Semester.get_current()
    if not current_semester:
        return JsonResponse({'error': 'No active semester is set'}, status=400)
    
    if not current_semester.can_enroll_students():
        return JsonResponse({
            'error': f'Enrollment is not allowed for {current_semester.get_status_display()} semester.'
        }, status=400)
    
    # If student has no section, return available sections for their year level
    if not student.section:
        if not student.year_level:
            return JsonResponse({
                'error': f'Student {student.student_id} does not have a year level assigned.',
                'needs_section': True,
                'assignments': []
            })
        
        # Get sections matching student's year level
        available_sections = ClassSection.objects.filter(
            year_level=student.year_level
        ).order_by('name').values('id', 'name')
        
        return JsonResponse({
            'needs_section': True,
            'student_year_level': student.year_level.name,
            'sections': list(available_sections),
            'assignments': []
        })
    
    # 🔒 SECURITY: Validate student's year level matches section's year level
    if student.year_level != student.section.year_level:
        return JsonResponse({
            'error': f"Student's year level ({student.year_level.name}) does not match section's year level ({student.section.year_level.name}).",
            'assignments': []
        })
    
    # Get teacher's assignments for current semester that match student's section
    assignments = TeacherSubjectAssignment.objects.filter(
        teacher=teacher_profile,
        semester=current_semester,
        section=student.section  # Only assignments for student's section
    ).select_related('subject', 'section', 'semester', 'section__year_level').order_by('subject__code', 'section__name')
    
    # Debug: Check if teacher has any assignments for this section (even without semester filter)
    all_teacher_assignments_for_section = TeacherSubjectAssignment.objects.filter(
        teacher=teacher_profile,
        section=student.section
    ).count()
    
    # Get already enrolled assignment IDs for this student
    enrolled_assignment_ids = StudentEnrollment.objects.filter(
        student=student,
        assignment__in=assignments,
        is_active=True
    ).values_list('assignment_id', flat=True)
    
    # Filter out already enrolled assignments
    eligible_assignments = assignments.exclude(id__in=enrolled_assignment_ids)
    
    # Provide helpful error messages if no assignments found
    if not assignments.exists():
        if all_teacher_assignments_for_section == 0:
            return JsonResponse({
                'error': f'You do not have any subject assignments for section {student.section.name}. Please assign subjects to this section first.',
                'assignments': []
            })
        else:
            return JsonResponse({
                'error': f'You have assignments for section {student.section.name}, but none are assigned to the current semester ({current_semester.name} - {current_semester.academic_year}). Please check your subject assignments.',
                'assignments': []
            })
    
    # Check if all assignments are already enrolled
    if eligible_assignments.count() == 0 and assignments.count() > 0:
        enrolled_count = len(enrolled_assignment_ids)
        return JsonResponse({
            'error': f'This student is already enrolled in all {enrolled_count} of your subjects for section {student.section.name} in the current semester.',
            'assignments': []
        })
    
    # Format results
    results = []
    for assignment in eligible_assignments:
        results.append({
            'id': assignment.id,
            'subject_code': assignment.subject.code,
            'subject_name': assignment.subject.name,
            'section_name': assignment.section.name,
            'semester_name': assignment.semester.name if assignment.semester else 'N/A',
            'semester_year': assignment.semester.academic_year if assignment.semester else 'N/A',
        })
    
    return JsonResponse({
        'assignments': results,
        'student': {
            'id': student.id,
            'student_id': student.student_id,
            'name': student.user.get_full_name() or student.user.username,
            'section': student.section.name if student.section else 'No Section',
        },
        'debug_info': {
            'total_assignments_for_section': assignments.count(),
            'enrolled_count': len(enrolled_assignment_ids),
            'eligible_count': eligible_assignments.count(),
            'current_semester': current_semester.name if current_semester else None,
        }
    })


@login_required
@role_required('teacher')
@require_http_methods(["POST"])
@transaction.atomic
def assign_student_section(request):
    """
    Assign a section to a student. Used when student has no section during enrollment.
    """
    try:
        teacher_profile = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Teacher profile not found'}, status=404)
    
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON data'}, status=400)
    
    # Validate input
    student_id = validate_input(data.get('student_id'), 'integer')
    section_id = validate_input(data.get('section_id'), 'integer')
    
    if not student_id or not section_id:
        return JsonResponse({
            'success': False,
            'error': 'Student ID and Section ID are required'
        }, status=400)
    
    # Get current semester and validate it's active
    current_semester = Semester.get_current()
    if not current_semester:
        return JsonResponse({
            'success': False,
            'error': 'No active semester is set. Please contact the administrator.'
        }, status=400)
    
    if current_semester.status != 'active':
        return JsonResponse({
            'success': False,
            'error': f'Cannot assign sections when semester is {current_semester.get_status_display()}. Only active semesters allow section assignments.'
        }, status=400)
    
    # Get student
    try:
        student = StudentProfile.objects.select_related('user', 'section', 'year_level').get(id=student_id)
    except StudentProfile.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Student not found'}, status=404)
    
    # Get section
    try:
        section = ClassSection.objects.select_related('year_level').get(id=section_id)
    except ClassSection.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Section not found'}, status=404)
    
    # 🔒 SECURITY: Validate student's year level matches section's year level
    if student.year_level != section.year_level:
        return JsonResponse({
            'success': False,
            'error': f"Student's year level ({student.year_level.name}) does not match section's year level ({section.year_level.name})"
        }, status=400)
    
    # Assign section
    try:
        student.section = section
        student.full_clean()  # Run model validation
        student.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Successfully assigned {student.user.get_full_name()} to section {section.name}',
            'section_name': section.name
        })
    except Exception as e:
        logger.error(f"Error assigning section: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'Failed to assign section: {str(e)}'
        }, status=500)


@login_required
@role_required('teacher')
@require_http_methods(["POST"])
@transaction.atomic
def create_enrollment(request):
    """
    Create student enrollment with comprehensive server-side validation.
    """
    try:
        teacher_profile = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Teacher profile not found'}, status=404)
    
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON data'}, status=400)
    
    # Validate input
    student_id = validate_input(data.get('student_id'), 'integer')
    assignment_id = validate_input(data.get('assignment_id'), 'integer')
    
    if not student_id or not assignment_id:
        return JsonResponse({
            'success': False,
            'error': 'Student ID and Assignment ID are required'
        }, status=400)
    
    # Get student
    try:
        student = StudentProfile.objects.select_related('user', 'section', 'year_level').get(id=student_id)
    except StudentProfile.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Student not found'}, status=404)
    
    # Get assignment and validate teacher ownership
    try:
        assignment = TeacherSubjectAssignment.objects.select_related(
            'teacher', 'subject', 'section', 'semester'
        ).get(id=assignment_id)
    except TeacherSubjectAssignment.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Assignment not found'}, status=404)
    
    # 🔒 SECURITY: Validate teacher owns the assignment
    if assignment.teacher != teacher_profile:
        return JsonResponse({
            'success': False,
            'error': 'You do not have permission to enroll students in this assignment'
        }, status=403)
    
    # 🔒 SECURITY: Validate semester is active
    if not assignment.semester:
        return JsonResponse({
            'success': False,
            'error': 'Assignment does not have a semester assigned'
        }, status=400)
    
    if not assignment.semester.can_enroll_students():
        return JsonResponse({
            'success': False,
            'error': f'Enrollment is not allowed for {assignment.semester.get_status_display()} semester'
        }, status=400)
    
    # 🔒 SECURITY: Validate student's section matches assignment's section
    if student.section != assignment.section:
        return JsonResponse({
            'success': False,
            'error': f"Student's section ({student.section.name if student.section else 'None'}) "
                    f"does not match assignment's section ({assignment.section.name})"
        }, status=400)
    
    # 🔒 SECURITY: Validate student's year level matches section's year level
    if student.year_level != assignment.section.year_level:
        return JsonResponse({
            'success': False,
            'error': f"Student's year level ({student.year_level.name}) "
                    f"does not match section's year level ({assignment.section.year_level.name})"
        }, status=400)
    
    # 🔒 SECURITY: Check for duplicate enrollment
    existing_enrollment = StudentEnrollment.objects.filter(
        student=student,
        assignment=assignment,
        is_active=True
    ).first()
    
    if existing_enrollment:
        return JsonResponse({
            'success': False,
            'error': f'Student is already enrolled in {assignment.subject.code} ({assignment.section.name})'
        }, status=400)
    
    # Create enrollment
    try:
        enrollment = StudentEnrollment(
            student=student,
            assignment=assignment,
            semester=assignment.semester  # Explicitly set from assignment
        )
        enrollment.full_clean()  # Run model validation
        enrollment.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Successfully enrolled {student.user.get_full_name()} in {assignment.subject.code} ({assignment.section.name})',
            'enrollment_id': enrollment.id
        })
    except Exception as e:
        logger.error(f"Error creating enrollment: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'Failed to create enrollment: {str(e)}'
        }, status=500)


@login_required
@role_required('teacher')
def attendance(request):
    try:
        teacher_profile = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        return redirect('dashboard')
    
    # Handle POST request to save attendance
    if request.method == 'POST':
        # Validate and sanitize input - accept assignment_id (new) or subject_id (backward compatibility)
        assignment_id = validate_input(request.POST.get('assignment'), 'integer')
        selected_subject_id = validate_input(request.POST.get('subject'), 'integer')
        
        # Get assignment - prefer assignment_id, fallback to subject_id
        if assignment_id:
            try:
                assignment = TeacherSubjectAssignment.objects.get(
                    id=assignment_id,
                    teacher=teacher_profile
                )
                selected_subject = assignment.subject
            except TeacherSubjectAssignment.DoesNotExist:
                messages.error(request, 'Assignment not found or access denied.')
                return redirect('teachers:attendance')
        elif selected_subject_id:
            # Backward compatibility: get assignment from subject_id
            has_access, subject_or_error = validate_teacher_access(request, subject_id=selected_subject_id)
            if not has_access:
                messages.error(request, subject_or_error)
                return redirect('teachers:attendance')
            selected_subject = subject_or_error
            # Get current semester for filtering
            current_semester = Semester.get_current()
            assignment_filter = TeacherSubjectAssignment.objects.filter(
                teacher=teacher_profile,
                subject=selected_subject
            )
            if current_semester:
                assignment_filter = assignment_filter.filter(semester=current_semester)
            assignment = assignment_filter.first()
            if not assignment:
                messages.error(request, 'Assignment not found.')
                return redirect('teachers:attendance')
        else:
            messages.error(request, 'Invalid assignment or subject selected.')
            return redirect('teachers:attendance')
        
        today = timezone.now().date()
        updated_count = 0
        created_count = 0
        
        # Process each student's attendance within a transaction
        with transaction.atomic():
            for key, value in request.POST.items():
                if key.startswith('student_') and value:
                    student_id = validate_input(key.replace('student_', ''), 'integer')
                    status = validate_input(value, 'string')
                    
                    # Validate status
                    if status not in ['present', 'absent', 'late']:
                        continue
                    
                    if not student_id:
                        continue
                    
                    try:
                        student = StudentProfile.objects.get(
                            id=student_id, 
                            section=assignment.section
                        )
                        
                        # Get or create enrollment for this student-assignment combination
                        enrollment, _ = StudentEnrollment.objects.get_or_create(
                            student=student,
                            assignment=assignment,
                            defaults={'is_active': True}
                        )
                        
                        # Check if attendance record exists for today
                        attendance_record = Attendance.objects.filter(
                            enrollment=enrollment,
                            date=today
                        ).first()
                        
                        old_status = None
                        created = False
                        
                        if attendance_record:
                            # Update existing record - always save to ensure persistence
                            old_status = attendance_record.status
                            attendance_record.status = status
                            attendance_record.save(update_fields=['status'])
                            if old_status != status:
                                updated_count += 1
                        else:
                            # Create new record - explicitly set date to today
                            try:
                                attendance_record = Attendance.objects.create(
                                    enrollment=enrollment,
                                    date=today,
                                    status=status
                                )
                                created = True
                                created_count += 1
                            except IntegrityError:
                                # Race condition: another request created it
                                # Fetch and update the existing record
                                attendance_record = Attendance.objects.filter(
                                    enrollment=enrollment,
                                    date=today
                                ).first()
                                if attendance_record:
                                    old_status = attendance_record.status
                                    if old_status != status:
                                        attendance_record.status = status
                                        attendance_record.save(update_fields=['status'])
                                        updated_count += 1
                                else:
                                    # If we can't find it, skip
                                    continue
                        
                        # Send notification for absent/late (only if status changed or newly created)
                        if status in ['absent', 'late']:
                            if created or (old_status and old_status != status):
                                send_attendance_notification(student, selected_subject, status, today)
                                # Check for consecutive absences
                                if status == 'absent':
                                    check_consecutive_absences(student, selected_subject)
                                # Check performance after attendance update
                                check_and_send_performance_notifications(student, selected_subject)
                    except (StudentProfile.DoesNotExist, ValueError) as e:
                        logger.error(f"Error processing attendance for student {student_id}: {str(e)}")
                        continue
        
        if updated_count > 0 or created_count > 0:
            messages.success(request, f'Attendance updated: {created_count} new, {updated_count} updated.')
        else:
            messages.info(request, 'No attendance changes were made.')
        
        # Redirect with assignment_id
        return redirect(reverse('teachers:attendance') + '?assignment=' + str(assignment.id) + '&saved=true')
    
    # Get current semester
    current_semester = Semester.get_current()
    
    # Get teacher's assignments - filter by active semester
    assignments = TeacherSubjectAssignment.objects.filter(
        teacher=teacher_profile
    )
    if current_semester:
        assignments = assignments.filter(semester=current_semester)
    else:
        assignments = assignments.none()
        messages.warning(request, 'No active semester is set. Please contact the administrator.')
    
    assignments = assignments.select_related('subject', 'section').order_by('subject__code')
    
    # Get unique subjects from assignments
    subjects = [assignment.subject for assignment in assignments]
    
    # Get today's date
    today = timezone.now().date()
    
    # Get selected assignment from query parameter (prefer assignment_id, fallback to subject_id for backward compatibility)
    assignment_id = request.GET.get('assignment')
    selected_subject_id = request.GET.get('subject')
    selected_subject = None
    selected_assignment = None
    students_data = []
    
    if assignment_id:
        # New way: use assignment_id directly
        try:
            selected_assignment = TeacherSubjectAssignment.objects.get(
                id=assignment_id,
                teacher=teacher_profile
            )
            selected_subject = selected_assignment.subject
            # Get enrolled students for this assignment
            enrollments = StudentEnrollment.objects.filter(
                assignment=selected_assignment,
                is_active=True
            ).select_related('student', 'student__user')
            
            students = [e.student for e in enrollments]
            students.sort(key=lambda s: (s.user.last_name, s.user.first_name))
            
            # Get existing attendance records for today
            attendance_records = Attendance.objects.filter(
                enrollment__assignment=selected_assignment,
                date=today
            ).select_related('enrollment', 'enrollment__student')
            
            # Create a dictionary mapping student_id to attendance status
            attendance_dict = {record.enrollment.student.id: record.status for record in attendance_records}
            
            # Prepare students data with attendance status
            for student in students:
                students_data.append({
                    'student': student,
                    'attendance_status': attendance_dict.get(student.id, '')
                })
        except TeacherSubjectAssignment.DoesNotExist:
            messages.error(request, 'Assignment not found or access denied.')
            selected_assignment = None
    elif selected_subject_id:
        # Backward compatibility: get assignment from subject_id
        try:
            selected_assignment = TeacherSubjectAssignment.objects.filter(
                teacher=teacher_profile,
                subject_id=selected_subject_id
            ).first()
            
            if selected_assignment:
                selected_subject = selected_assignment.subject
                # Get enrolled students for this assignment
                enrollments = StudentEnrollment.objects.filter(
                    assignment=selected_assignment,
                    is_active=True
                ).select_related('student', 'student__user')
                
                students = [e.student for e in enrollments]
                students.sort(key=lambda s: (s.user.last_name, s.user.first_name))
                
                # Get existing attendance records for today
                attendance_records = Attendance.objects.filter(
                    enrollment__assignment=selected_assignment,
                    date=today
                ).select_related('enrollment', 'enrollment__student')
                
                # Create a dictionary mapping student_id to attendance status
                attendance_dict = {record.enrollment.student.id: record.status for record in attendance_records}
                
                # Prepare students data with attendance status
                for student in students:
                    students_data.append({
                        'student': student,
                        'attendance_status': attendance_dict.get(student.id, '')
                    })
        except Exception as e:
            logger.error(f"Error loading attendance data: {str(e)}")
            pass
    
    context = {
        'assignments': assignments,  # Pass assignments for dropdown
        'subjects': subjects,  # Keep for backward compatibility
        'selected_subject': selected_subject,
        'selected_assignment': selected_assignment,
        'students_data': students_data,
        'today': today,
        'teacher_profile': teacher_profile,
    }
    return render(request, 'teachers/attendance.html', context)

@login_required
def grades(request):
    if request.user.role != 'teacher':
        return redirect('dashboard')
    
    try:
        teacher_profile = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        return redirect('dashboard')
    
    # Get current semester
    current_semester = Semester.get_current()
    
    # Get teacher's assignments - filter by active semester
    assignments = TeacherSubjectAssignment.objects.filter(
        teacher=teacher_profile
    )
    if current_semester:
        assignments = assignments.filter(semester=current_semester)
    else:
        assignments = assignments.none()
        messages.warning(request, 'No active semester is set. Please contact the administrator.')
    
    assignments = assignments.select_related('subject', 'section').order_by('subject__code')
    
    # Get unique subjects from assignments
    subjects = [assignment.subject for assignment in assignments]
    
    # Get all unique sections from teacher's assignments
    section_ids = list(set([assignment.section.id for assignment in assignments if assignment.section]))
    sections = ClassSection.objects.filter(id__in=section_ids).order_by('name') if section_ids else ClassSection.objects.none()
    
    # Get only enrolled students for teacher's assignments in the active semester
    # This ensures only students who are actually enrolled can have scores entered
    enrolled_student_ids = StudentEnrollment.objects.filter(
        assignment__in=assignments,
        is_active=True
    )
    if current_semester:
        enrolled_student_ids = enrolled_student_ids.filter(semester=current_semester)
    enrolled_student_ids = enrolled_student_ids.values_list('student_id', flat=True).distinct()
    
    students = StudentProfile.objects.filter(
        id__in=enrolled_student_ids
    ).select_related('user', 'section').order_by('section__name', 'user__last_name', 'user__first_name') if enrolled_student_ids else StudentProfile.objects.none()
    
    # Get all assessments for teacher's assignments - filter by active semester
    assessments = Assessment.objects.filter(
        assignment__teacher=teacher_profile
    )
    if current_semester:
        assessments = assessments.filter(assignment__semester=current_semester)
    assessments = assessments.select_related('assignment__subject', 'created_by').order_by('-date', 'category', 'name')
    
    # Get all assessment scores - filter by active semester
    assessment_scores = AssessmentScore.objects.filter(
        assessment__assignment__teacher=teacher_profile
    )
    if current_semester:
        assessment_scores = assessment_scores.filter(enrollment__semester=current_semester)
    assessment_scores = assessment_scores.select_related('enrollment__student', 'assessment', 'recorded_by')
    
    # Get category weights for each assignment
    category_weights_dict = {}
    for assignment in assignments:
        subject = assignment.subject
        try:
            weights = CategoryWeights.objects.get(assignment=assignment)
            category_weights_dict[subject.id] = {
                'Activities': weights.activities_weight,
                'Quizzes': weights.quizzes_weight,
                'Projects': weights.projects_weight,
                'Exams': weights.exams_weight,
            }
        except CategoryWeights.DoesNotExist:
            # Default weights if not set
            category_weights_dict[subject.id] = {
                'Activities': 20,
                'Quizzes': 20,
                'Projects': 30,
                'Exams': 30,
            }
    
    # Get audit logs
    audit_logs = AuditLog.objects.filter(
        user=request.user
    ).select_related('student', 'assessment').order_by('-timestamp')[:50]
    
    # Get unique subject codes (only teacher's subjects)
    # Use codes instead of names since codes are unique per section
    all_subjects = list(set([subject.code for subject in subjects]))
    
    # Get unique section names (only sections where teacher teaches)
    sections_array = list(sections.values_list('name', flat=True))
    
    # Prepare data for JSON serialization
    students_data = []
    for student in students:
        students_data.append({
            'id': student.id,
            'name': student.user.get_full_name() or student.user.username,
            'email': student.user.email,
            'section': student.section.name if student.section else None,
        })
    
    # Create mapping of section to subjects for that section
    # Use subject code (unique per section) instead of name to avoid conflicts
    section_to_subjects = {}
    for assignment in assignments:
        subject = assignment.subject
        section = assignment.section
        if section:
            section_name = section.name
            if section_name not in section_to_subjects:
                section_to_subjects[section_name] = []
            # Use subject code which is unique per section (e.g., "IT102-BSIT1A")
            if subject.code not in section_to_subjects[section_name]:
                section_to_subjects[section_name].append(subject.code)
    
    assessments_data = []
    # Map subject names to IDs for category weights lookup - populate from all subjects
    # Use subject code (which is unique per section) instead of name to avoid conflicts
    subject_name_to_id = {}
    for subject in subjects:
        # Use subject code as key since it's unique per section (e.g., "IT102-BSIT1A")
        # Also map by name for backward compatibility, but code takes precedence
        subject_name_to_id[subject.code] = subject.id
        # If name is different from code, also add name mapping (but code is preferred)
        if subject.name != subject.code:
            # For subjects with same name in different sections, use code instead
            # Only add name mapping if code doesn't already exist
            if subject.name not in subject_name_to_id:
                subject_name_to_id[subject.name] = subject.id
    
    for assessment in assessments:
        subject = assessment.assignment.subject if assessment.assignment else assessment.subject
        section = assessment.assignment.section if assessment.assignment and assessment.assignment.section else None
        assessments_data.append({
            'id': assessment.id,
            'name': assessment.name,
            'category': assessment.category,
            'subject': subject.code,  # Use code instead of name for consistency
            'subjectId': subject.id,
            'section': section.name if section else None,  # Add section information
            'maxScore': float(assessment.max_score),
            'date': assessment.date.strftime('%Y-%m-%d'),
            'term': assessment.term,
        })
    
    scores_data = []
    for score in assessment_scores:
        student = score.enrollment.student if score.enrollment else score.student
        scores_data.append({
            'id': score.id,
            'studentId': student.id,
            'assessmentId': score.assessment.id,
            'score': float(score.score),
        })
    
    audit_logs_data = []
    for log in audit_logs:
        audit_logs_data.append({
            'id': log.id,
            'action': log.action,
            'details': log.details,
            'user': log.user.get_full_name() or log.user.username,
            'timestamp': log.timestamp.strftime('%Y-%m-%d %I:%M %p'),
        })
    
    context = {
        'teacher_profile': teacher_profile,
        'subjects': subjects,
        'sections': sections,
        'students_json': json.dumps(students_data),
        'assessments_json': json.dumps(assessments_data),
        'scores_json': json.dumps(scores_data),
        'category_weights_json': json.dumps(category_weights_dict),
        'subject_name_to_id_json': json.dumps(subject_name_to_id),
        'audit_logs_json': json.dumps(audit_logs_data),
        'all_subjects_json': json.dumps(all_subjects),
        'sections_array_json': json.dumps(sections_array),
        'section_to_subjects_json': json.dumps(section_to_subjects),
    }
    return render(request, 'teachers/grades.html', context)

@login_required
@role_required('teacher')
@require_http_methods(["POST"])
@transaction.atomic
def add_assessment(request):
    """AJAX endpoint to add a new assessment with input validation and transaction"""
    try:
        teacher_profile = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Teacher profile not found'}, status=404)
    
    try:
        import json
        data = json.loads(request.body)
        
        # Validate and sanitize input
        subject_id = validate_input(data.get('subject_id'), 'integer')
        if not subject_id:
            return JsonResponse({'success': False, 'error': 'Invalid subject ID'}, status=400)
        
        # Validate teacher has access to this subject
        has_access, subject_or_error = validate_teacher_access(request, subject_id=subject_id)
        if not has_access:
            return JsonResponse({'success': False, 'error': subject_or_error}, status=403)
        
        subject = subject_or_error
        
        # Get the assignment for this subject and section
        # Filter by section if provided to ensure we get the correct assignment
        assignment = TeacherSubjectAssignment.objects.filter(
            teacher=teacher_profile,
            subject=subject
        )
        
        # Filter by section if provided (section name from frontend)
        section_name = data.get('section')
        if section_name and section_name != 'all':
            assignment = assignment.filter(section__name=section_name)
        
        # Filter by current semester if available
        current_semester = Semester.get_current()
        if current_semester:
            assignment = assignment.filter(semester=current_semester)
        
        assignment = assignment.first()
        
        if not assignment:
            section_info = f" in section {section_name}" if section_name and section_name != 'all' else ""
            return JsonResponse({'success': False, 'error': f'Assignment not found for this subject{section_info}'}, status=404)
        
        # Validate assessment name
        assessment_name = validate_input(data.get('name'), 'string', max_length=200)
        if not assessment_name:
            return JsonResponse({'success': False, 'error': 'Invalid assessment name'}, status=400)
        
        # Check for duplicate assessment name in the same assignment (subject + section combination)
        # This allows the same assessment name in different sections
        if Assessment.objects.filter(assignment=assignment, name=assessment_name).exists():
            section_name = assignment.section.name if assignment.section else 'this section'
            return JsonResponse({
                'success': False,
                'error': f'An assessment with the name "{assessment_name}" already exists for {subject.code} in {section_name}. Please use a different name.'
            }, status=400)
        
        # Validate category
        category = validate_input(data.get('category'), 'string')
        if category not in ['Activities', 'Quizzes', 'Projects', 'Exams']:
            return JsonResponse({'success': False, 'error': 'Invalid category'}, status=400)
        
        # Validate max_score
        max_score = validate_input(data.get('max_score'), 'decimal')
        if not max_score or max_score <= 0:
            return JsonResponse({'success': False, 'error': 'Invalid max score'}, status=400)
        
        # Validate date
        assessment_date = validate_input(data.get('date'), 'date')
        if not assessment_date:
            return JsonResponse({'success': False, 'error': 'Invalid date format'}, status=400)
        
        # Validate term
        term = validate_input(data.get('term', 'Midterm'), 'string')
        if term not in ['Midterm', 'Final']:
            term = 'Midterm'
        
        # Create assessment within transaction
        assessment = Assessment.objects.create(
            name=assessment_name,
            category=category,
            assignment=assignment,
            max_score=Decimal(str(max_score)),
            date=assessment_date,
            term=term,
            created_by=teacher_profile
        )
        
        # Create audit log
        AuditLog.objects.create(
            user=request.user,
            action='Assessment Added',
            details=f'Created new assessment: {assessment.name} ({assessment.category})',
            assessment=assessment
        )
        
        return JsonResponse({
            'success': True,
            'assessment_id': assessment.id,
            'message': 'Assessment added successfully'
        })
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        logger.error(f"Error adding assessment: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': 'An error occurred while adding the assessment'}, status=500)

def recalculate_all_grades_for_subject(subject, term=None):
    """
    Recalculate grades for all students in a subject's section.
    
    Args:
        subject: Subject instance
        term: 'Midterm', 'Final', or None (both)
    """
    try:
        students = StudentProfile.objects.filter(section=subject.section)
        terms_to_process = [term] if term else ['Midterm', 'Final']
        
        for student in students:
            for t in terms_to_process:
                try:
                    calculate_and_update_grade(student, subject, t)
                except Exception as e:
                    logger.error(f"Error recalculating grade for student {student.id}, subject {subject.id}, term {t}: {str(e)}", exc_info=True)
    except Exception as e:
        logger.error(f"Error in recalculate_all_grades_for_subject: {str(e)}", exc_info=True)

def calculate_and_update_grade(student, subject, term='Midterm'):
    """
    Calculate weighted final grade for a student in a subject for a specific term
    and update/create the Grade record in the database.
    
    Args:
        student: StudentProfile instance
        subject: Subject instance
        term: 'Midterm' or 'Final'
    
    Returns:
        float: The calculated grade, or None if no assessments exist
    """
    try:
        # Find the enrollment for this student and subject first
        # Get the assignment for this subject (need to find which assignment the student is enrolled in)
        from core.models import TeacherSubjectAssignment, StudentEnrollment
        
        # Find assignments for this subject
        assignments = TeacherSubjectAssignment.objects.filter(subject=subject)
        # Find enrollment for this student in any of these assignments
        enrollment = StudentEnrollment.objects.filter(
            student=student,
            assignment__in=assignments,
            is_active=True
        ).first()
        
        if not enrollment:
            logger.warning(f"No enrollment found for student {student.user.get_full_name()} in subject {subject.code}")
            return None
        
        # Get category weights for this assignment
        try:
            weights = CategoryWeights.objects.get(assignment=enrollment.assignment)
            category_weights = {
                'Activities': weights.activities_weight,
                'Quizzes': weights.quizzes_weight,
                'Projects': weights.projects_weight,
                'Exams': weights.exams_weight,
            }
        except CategoryWeights.DoesNotExist:
            # Use default weights if not set
            category_weights = {
                'Activities': 20,
                'Quizzes': 20,
                'Projects': 30,
                'Exams': 30,
            }
        
        # Get all assessments for this assignment and term
        assessments = Assessment.objects.filter(
            assignment=enrollment.assignment, 
            term=term
        )
        
        if not assessments.exists():
            # No assessments for this term, delete grade if exists
            Grade.objects.filter(enrollment=enrollment, term=term).delete()
            return None
        
        # Calculate weighted average for each category
        total_weighted = 0
        total_weight = 0
        
        for category in ['Activities', 'Quizzes', 'Projects', 'Exams']:
            category_assessments = assessments.filter(category=category)
            if not category_assessments.exists():
                continue
            
            # Get all scores for this category for this enrollment
            category_scores = AssessmentScore.objects.filter(
                enrollment=enrollment,
                assessment__in=category_assessments
            )
            
            if not category_scores.exists():
                continue
            
            # Calculate category average
            # Convert Decimal to float for calculations
            total_score = float(sum(float(score.score) for score in category_scores))
            total_max = float(sum(float(assessment.max_score) for assessment in category_assessments))
            
            if total_max > 0:
                category_average = (total_score / total_max) * 100.0
                weight = float(category_weights[category]) / 100.0
                total_weighted += category_average * weight
                total_weight += weight
        
        # Calculate final grade
        if total_weight > 0:
            final_grade = round(total_weighted / total_weight, 2)
            
            # Update or create Grade record within a transaction
            with transaction.atomic():
                grade, created = Grade.objects.update_or_create(
                    enrollment=enrollment,
                    term=term,
                    defaults={'grade': Decimal(str(final_grade))}
                )
                
                # Check and send performance notifications after grade update
                check_and_send_performance_notifications(student, subject)
                # Explicitly save to ensure it's persisted
                grade.save()
            
            return final_grade
        else:
            # No valid scores, delete grade if exists
            Grade.objects.filter(enrollment=enrollment, term=term).delete()
            return None
            
    except Exception as e:
        logger.error(f"Error calculating grade for {student.user.get_full_name()} - {subject.code} ({term}): {str(e)}")
        return None

@login_required
@role_required('teacher')
@require_http_methods(["POST"])
@transaction.atomic
def update_score(request):
    """AJAX endpoint to update or create an assessment score with input validation and transaction"""
    try:
        teacher_profile = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Teacher profile not found'}, status=404)
    
    try:
        import json
        data = json.loads(request.body)
        
        # Validate and sanitize input
        student_id = validate_input(data.get('student_id'), 'integer')
        assessment_id = validate_input(data.get('assessment_id'), 'integer')
        score_value = data.get('score')
        
        # Validate required fields
        if not student_id or not assessment_id:
            return JsonResponse({'success': False, 'error': 'Student ID and Assessment ID are required'}, status=400)
        
        # Validate teacher has access to this assessment
        has_access, assessment_or_error = validate_teacher_access(request, assessment_id=assessment_id)
        if not has_access:
            return JsonResponse({'success': False, 'error': assessment_or_error}, status=403)
        
        assessment = assessment_or_error
        
        # Get student
        try:
            student = StudentProfile.objects.select_for_update().get(id=student_id)
        except StudentProfile.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Student not found'}, status=404)
        
        # Validate score if provided
        if score_value is not None:
            score_value = validate_input(score_value, 'decimal')
            if score_value is False:
                return JsonResponse({'success': False, 'error': 'Invalid score value'}, status=400)
            if score_value < 0:
                return JsonResponse({'success': False, 'error': 'Score cannot be negative'}, status=400)
            if score_value > float(assessment.max_score):
                return JsonResponse({
                    'success': False,
                    'error': f'Score cannot exceed maximum score of {assessment.max_score}'
                }, status=400)
        
        # Get enrollment for this student and assignment
        # First try to find enrollment matching assignment and semester
        enrollment = StudentEnrollment.objects.filter(
            student=student,
            assignment=assessment.assignment,
            is_active=True
        )
        
        # If assignment has a semester, prefer enrollment with matching semester
        # but also allow enrollment without semester (will be auto-synced)
        if assessment.assignment.semester:
            enrollment = enrollment.filter(
                Q(semester=assessment.assignment.semester) | Q(semester__isnull=True)
            )
        
        enrollment = enrollment.first()
        
        # If no enrollment found, try without semester filter (for backward compatibility)
        if not enrollment:
            enrollment = StudentEnrollment.objects.filter(
                student=student,
                assignment=assessment.assignment,
                is_active=True
            ).first()
        
        if not enrollment:
            # Provide more detailed error message with logging
            assignment_info = f"{assessment.assignment.subject.code} ({assessment.assignment.section.name if assessment.assignment.section else 'No Section'})"
            semester_info = f" for {assessment.assignment.semester}" if assessment.assignment.semester else ""
            
            # Check all possible enrollments for debugging
            all_enrollments = StudentEnrollment.objects.filter(
                student=student,
                assignment=assessment.assignment
            ).select_related('assignment__section', 'semester')
            
            # Check if student has enrollments for this assignment but different status/semester
            if all_enrollments.exists():
                inactive_enrollments = all_enrollments.filter(is_active=False)
                if inactive_enrollments.exists():
                    return JsonResponse({
                        'success': False, 
                        'error': f'Student has an inactive enrollment in {assignment_info}. Please reactivate the enrollment first.'
                    }, status=400)
                
                # Check for enrollments with different semester
                if assessment.assignment.semester:
                    different_semester = all_enrollments.exclude(semester=assessment.assignment.semester).exclude(semester__isnull=True)
                    if different_semester.exists():
                        diff_sem = different_semester.first().semester
                        return JsonResponse({
                            'success': False, 
                            'error': f'Student is enrolled in {assignment_info} but for a different semester ({diff_sem}). Please enroll the student for {assessment.assignment.semester} first.'
                        }, status=400)
            
            # Check if student is enrolled in the same subject but different section
            student_enrollments = StudentEnrollment.objects.filter(
                student=student,
                assignment__subject=assessment.assignment.subject,
                is_active=True
            ).select_related('assignment__section', 'semester')
            
            if student_enrollments.exists():
                enrolled_sections = [e.assignment.section.name for e in student_enrollments if e.assignment.section]
                if enrolled_sections:
                    sections_str = ', '.join(set(enrolled_sections))
                    return JsonResponse({
                        'success': False, 
                        'error': f'Student is enrolled in {assessment.assignment.subject.code} but in different section(s): {sections_str}. The assessment is for {assessment.assignment.section.name}. Please enroll the student in {assessment.assignment.section.name} first.'
                    }, status=400)
            
            # Log for debugging
            logger.error(
                f"Enrollment not found for student_id={student_id}, assessment_id={assessment_id}, "
                f"assignment_id={assessment.assignment.id}, semester={assessment.assignment.semester}, "
                f"student_section={student.section.name if student.section else None}, "
                f"assignment_section={assessment.assignment.section.name if assessment.assignment.section else None}"
            )
            
            return JsonResponse({
                'success': False, 
                'error': f'Student is not enrolled in {assignment_info}{semester_info}. Please enroll the student first.'
            }, status=400)
        
        # Auto-sync enrollment semester if it doesn't match assignment semester
        if assessment.assignment.semester and enrollment.semester != assessment.assignment.semester:
            enrollment.semester = assessment.assignment.semester
            enrollment.save()
            logger.info(f"Auto-synced enrollment {enrollment.id} semester to {assessment.assignment.semester}")
        
        # Handle score deletion or update/create
        try:
            assessment_score = AssessmentScore.objects.get(enrollment=enrollment, assessment=assessment)
            # Score exists
            if score_value is None:
                # Delete the score
                assessment_score.delete()
                action = 'Score Deleted'
                details = f'Deleted score for {student.user.get_full_name()} - {assessment.name}'
                score_id = None
            else:
                # Update existing score
                assessment_score.score = score_value
                assessment_score.recorded_by = teacher_profile
                assessment_score.save()
                action = 'Score Updated'
                details = f'Updated score for {student.user.get_full_name()} - {assessment.name}: {score_value}/{assessment.max_score}'
                score_id = assessment_score.id
        except AssessmentScore.DoesNotExist:
            # Score doesn't exist
            if score_value is None:
                # Nothing to delete, but still recalculate grades in case other scores changed
                # Calculate and update grades for both Midterm and Final terms
                try:
                    calculate_and_update_grade(student, assessment.subject, 'Midterm')
                    calculate_and_update_grade(student, assessment.subject, 'Final')
                except Exception as grade_error:
                    logger.error(f"Error calculating grades: {str(grade_error)}")
                
                return JsonResponse({
                    'success': True,
                    'score_id': None,
                    'message': 'No score to delete'
                })
            else:
                # Create new score
                assessment_score = AssessmentScore.objects.create(
                    enrollment=enrollment,
                    assessment=assessment,
                    score=score_value,
                    recorded_by=teacher_profile
                )
                action = 'Score Added'
                details = f'Added score for {student.user.get_full_name()} - {assessment.name}: {score_value}/{assessment.max_score}'
                score_id = assessment_score.id
        
        # Create audit log
        AuditLog.objects.create(
            user=request.user,
            action=action,
            details=details,
            student=student,
            assessment=assessment
        )
        
        # Calculate and update grades for both Midterm and Final terms
        # Recalculate for ALL students in the subject's section, not just this student
        # This ensures all grades are consistent
        try:
            recalculate_all_grades_for_subject(assessment.subject, term=None)
        except Exception as grade_error:
            logger.error(f"Error calculating grades after score update: {str(grade_error)}", exc_info=True)
        
        return JsonResponse({
            'success': True,
            'score_id': score_id,
            'message': action
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@login_required
@role_required('teacher')
@require_http_methods(["POST"])
@transaction.atomic
def update_category_weights(request):
    """AJAX endpoint to update category weights for a subject with input validation and transaction"""
    try:
        teacher_profile = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Teacher profile not found'}, status=404)
    
    try:
        import json
        data = json.loads(request.body)
        
        # Validate and sanitize input
        subject_id = validate_input(data.get('subject_id'), 'integer')
        if not subject_id:
            return JsonResponse({'success': False, 'error': 'Subject ID is required'}, status=400)
        
        # Validate teacher has access to this subject
        has_access, subject_or_error = validate_teacher_access(request, subject_id=subject_id)
        if not has_access:
            return JsonResponse({'success': False, 'error': subject_or_error}, status=403)
        
        subject = subject_or_error
        
        weights = data.get('weights', {})
        
        # Validate weights
        activities_weight = validate_input(weights.get('Activities', 20), 'integer')
        quizzes_weight = validate_input(weights.get('Quizzes', 20), 'integer')
        projects_weight = validate_input(weights.get('Projects', 30), 'integer')
        exams_weight = validate_input(weights.get('Exams', 30), 'integer')
        
        if not all([activities_weight, quizzes_weight, projects_weight, exams_weight]):
            return JsonResponse({'success': False, 'error': 'Invalid weight values'}, status=400)
        
        total = activities_weight + quizzes_weight + projects_weight + exams_weight
        if total != 100:
            return JsonResponse({
                'success': False,
                'error': f'Category weights must total 100%. Current total: {total}%'
            }, status=400)
        
        # Get the assignment for this subject
        assignment = TeacherSubjectAssignment.objects.filter(
            teacher=teacher_profile,
            subject=subject
        ).first()
        
        if not assignment:
            return JsonResponse({'success': False, 'error': 'Assignment not found for this subject'}, status=404)
        
        # Update or create category weights within transaction
        category_weights, created = CategoryWeights.objects.select_for_update().update_or_create(
            assignment=assignment,
            defaults={
                'activities_weight': activities_weight,
                'quizzes_weight': quizzes_weight,
                'projects_weight': projects_weight,
                'exams_weight': exams_weight,
            }
        )
        
        # Recalculate grades for ALL students in this subject's section
        try:
            recalculate_all_grades_for_subject(subject, term=None)
        except Exception as grade_error:
            logger.error(f"Error recalculating grades after weight update: {str(grade_error)}", exc_info=True)
        
        # Create audit log
        AuditLog.objects.create(
            user=request.user,
            action='Category Weight Changed',
            details=f'Updated category weights for {subject.code}: Activities {activities_weight}%, Quizzes {quizzes_weight}%, Projects {projects_weight}%, Exams {exams_weight}%'
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Category weights updated successfully'
        })
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        logger.error(f"Error updating category weights: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': 'An error occurred while updating category weights'}, status=500)

@login_required
def reports(request):
    if request.user.role != 'teacher':
        return redirect('dashboard')
    
    try:
        teacher_profile = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        return redirect('dashboard')
    
    # Get teacher's assignments
    assignments = TeacherSubjectAssignment.objects.filter(
        teacher=teacher_profile
    ).select_related('subject', 'section').order_by('subject__code')
    
    # Get unique subjects from assignments
    subjects = [assignment.subject for assignment in assignments]
    
    # Get all sections where teacher teaches
    section_ids = list(set([assignment.section.id for assignment in assignments if assignment.section]))
    sections = ClassSection.objects.filter(id__in=section_ids).order_by('name') if section_ids else ClassSection.objects.none()
    
    # Get all students in teacher's sections
    students = StudentProfile.objects.filter(section__id__in=section_ids).select_related(
        'user', 'section'
    ).order_by('section__name', 'user__last_name', 'user__first_name') if section_ids else StudentProfile.objects.none()
    
    # Calculate low performance students
    # Criteria: GPA < 75 OR Attendance < 70%
    low_performance_students = []
    
    for student in students:
        # Get enrollments for this student in teacher's assignments
        student_enrollments = StudentEnrollment.objects.filter(
            student=student,
            assignment__teacher=teacher_profile,
            is_active=True
        )
        
        # Calculate GPA (average grade) for this student
        student_grades = Grade.objects.filter(
            enrollment__in=student_enrollments
        )
        
        gpa = 0
        if student_grades.exists():
            gpa = student_grades.aggregate(Avg('grade'))['grade__avg'] or 0
        
        # Calculate attendance percentage
        student_attendance = Attendance.objects.filter(
            enrollment__in=student_enrollments
        )
        
        total_attendance = student_attendance.count()
        present_count = student_attendance.filter(status='present').count()
        attendance_percentage = (present_count / total_attendance * 100) if total_attendance > 0 else 0
        
        # Check if student needs attention
        issues = []
        if gpa > 0 and gpa < 75:
            issues.append(f'Low GPA: {gpa:.1f}')
        if total_attendance > 0 and attendance_percentage < 70:
            issues.append(f'Low Attendance: {attendance_percentage:.1f}%')
        
        if issues:
            low_performance_students.append({
                'student': student,
                'gpa': round(gpa, 2),
                'attendance_percentage': round(attendance_percentage, 1),
                'issues': issues,
            })
    
    # Sort by most critical (lowest GPA first)
    low_performance_students.sort(key=lambda x: x['gpa'] if x['gpa'] > 0 else 100)
    
    context = {
        'students': students,
        'subjects': subjects,
        'sections': sections,
        'low_performance_students': low_performance_students,
        'teacher_profile': teacher_profile,
    }
    return render(request, 'teachers/reports.html', context)

@login_required
@login_required
def notifications(request):
    if request.user.role != 'teacher':
        return redirect('dashboard')
    
    # Get all notifications for the teacher
    all_notifications = Notification.objects.filter(recipient=request.user).order_by('-created_at')
    
    # Handle mark as read
    if request.method == 'POST' and 'mark_read' in request.POST:
        notification_id = request.POST.get('mark_read')
        try:
            notification = Notification.objects.get(id=notification_id, recipient=request.user)
            notification.is_read = True
            notification.save()
            return redirect('teachers:notifications')
        except Notification.DoesNotExist:
            pass
    
    # Handle mark all as read
    if request.method == 'POST' and 'mark_all_read' in request.POST:
        Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
        return redirect('teachers:notifications')
    
    unread_count = all_notifications.filter(is_read=False).count()
    
    context = {
        'page_title': 'Notifications',
        'page_description': 'View and manage all your notifications and alerts.',
        'notifications': all_notifications,
        'unread_count': unread_count,
    }
    return render(request, 'teachers/notifications.html', context)
    