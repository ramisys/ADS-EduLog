from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q
from django.db import transaction, IntegrityError
from django.utils import timezone
from django.urls import reverse
from datetime import timedelta
from decimal import Decimal
import logging
from core.models import (
    TeacherProfile, Subject, ClassSection, StudentProfile, Attendance, Grade, Notification,
    Assessment, AssessmentScore, CategoryWeights, AuditLog
)
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
    
    # Get teacher's subjects - order by code and section to ensure all are included
    # Convert to list to ensure all subjects are evaluated
    subjects = list(Subject.objects.filter(teacher=teacher_profile).select_related('section').order_by('code', 'section__name'))
    
    # Get classes/sections the teacher is advising
    advised_sections = ClassSection.objects.filter(adviser=teacher_profile)
    
    # Get all students in teacher's sections
    section_ids = list(set([s.section.id for s in subjects if s.section]))
    student_count = StudentProfile.objects.filter(section__id__in=section_ids).count() if section_ids else 0
    
    # Get recent attendance records for teacher's subjects
    recent_attendance = Attendance.objects.filter(
        subject__teacher=teacher_profile
    ).select_related('student', 'subject').order_by('-date')[:10]
    
    # Get attendance statistics
    total_attendance = Attendance.objects.filter(subject__teacher=teacher_profile)
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
    
    # Process ALL subjects (each Subject record is unique per section)
    # Calculate average for each subject-section combination
    for subject in subjects:
        # Debug: Log subject being processed
        logger.debug(f"Processing subject ID {subject.id}: code='{subject.code}', section='{subject.section.name if subject.section else None}'")
        
        # Always create the label first (we'll add it regardless of data)
        section_name = subject.section.name if subject.section else None
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
        
        # Calculate average for this subject-section
        subject_grades = Grade.objects.filter(subject=subject)
        has_data = False
        subject_avg = None
        assessment_scores_count = 0
        
        if subject_grades.exists():
            # Calculate from Grade records
            subject_avg_result = subject_grades.aggregate(Avg('grade'))['grade__avg']
            if subject_avg_result is not None:
                subject_avg = float(subject_avg_result)
                has_data = True
                logger.debug(f"Subject {subject.code} ({subject.section.name if subject.section else 'No section'}): Found {subject_grades.count()} Grade records, Average = {subject_avg:.2f}%")
        else:
            # Fallback: Calculate from assessment scores if Grade records don't exist
            assessment_scores = AssessmentScore.objects.filter(
                assessment__subject=subject
            ).select_related('assessment')
            assessment_scores_count = assessment_scores.count()
            
            if assessment_scores.exists():
                # Calculate average from assessment scores
                total_score = sum(float(score.score) for score in assessment_scores)
                total_max = sum(float(score.assessment.max_score) for score in assessment_scores)
                if total_max > 0:
                    subject_avg = (total_score / total_max) * 100
                    has_data = True
                    logger.debug(f"Subject {subject.code} ({subject.section.name if subject.section else 'No section'}): No Grade records, but found {assessment_scores_count} AssessmentScore records, Average = {subject_avg:.2f}%")
        
        # Always add both data and label together to ensure they match
        if has_data and subject_avg is not None:
            rounded_avg = round(subject_avg, 2)
            subject_performance_data.append(rounded_avg)
            subject_section_averages.append(subject_avg)  # Store for class average calculation
        else:
            # Show 0 for subjects without data
            subject_performance_data.append(0)
            logger.debug(f"Subject {subject.code} ({subject.section.name if subject.section else 'No section'}): No data found (Grade count: {subject_grades.count()}, Assessment scores: {assessment_scores_count})")
        
        # Always add the label (ensures data and labels arrays have same length)
        subject_performance_labels.append(label)
    
    # Debug: Log final arrays
    logger.debug(f"Subject performance data array length: {len(subject_performance_data)}, Labels array length: {len(subject_performance_labels)}")
    logger.debug(f"Subject performance data: {subject_performance_data}")
    logger.debug(f"Subject performance labels: {subject_performance_labels}")
    
    # Calculate class average as the average of all subject-section averages
    # This gives the overall average across all subject-sections
    if subject_section_averages:
        average_grade = sum(subject_section_averages) / len(subject_section_averages)
        # Count total number of Grade records for this teacher
        grades_count = Grade.objects.filter(subject__teacher=teacher_profile).count()
    else:
        # Fallback: If no subject-section averages, try to calculate from all grades
        total_grades = Grade.objects.filter(subject__teacher=teacher_profile)
        grades_count = total_grades.count()
        
        if grades_count > 0:
            average_grade_result = total_grades.aggregate(Avg('grade'))['grade__avg']
            if average_grade_result is not None:
                average_grade = float(average_grade_result)
            else:
                average_grade = 0
        else:
            # Final fallback: Calculate from assessment scores
            assessment_scores = AssessmentScore.objects.filter(
                assessment__subject__teacher=teacher_profile
            ).select_related('assessment')
            
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
    section_ids = list(set([s.section.id for s in subjects if s.section]))
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
        # Calculate average across ALL subjects the teacher teaches for this student
        student_grades = Grade.objects.filter(student=student, subject__teacher=teacher_profile)
        if student_grades.exists():
            # Get the subjects these grades are for
            grade_subjects = student_grades.values_list('subject__code', 'subject__section__name').distinct()
            student_avg_result = student_grades.aggregate(Avg('grade'))['grade__avg']
            if student_avg_result is not None:
                student_avg = float(student_avg_result)
                logger.debug(f"Student {student.user.get_full_name()} ({section_name}): Found {student_grades.count()} Grade records across {len(grade_subjects)} subjects {list(grade_subjects)}, Average = {student_avg:.2f}%")
        
        # Fallback: Calculate from assessment scores if Grade records don't exist
        if student_avg is None:
            assessment_scores = AssessmentScore.objects.filter(
                student=student,
                assessment__subject__teacher=teacher_profile
            ).select_related('assessment', 'assessment__subject')
            
            if assessment_scores.exists():
                # Calculate average from assessment scores
                total_score = sum(float(score.score) for score in assessment_scores)
                total_max = sum(float(score.assessment.max_score) for score in assessment_scores)
                if total_max > 0:
                    student_avg = (total_score / total_max) * 100
                    # Get subjects these scores are for
                    score_subjects = assessment_scores.values_list('assessment__subject__code', 'assessment__subject__section__name').distinct()
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
        subject_stats = []
        for subject in subjects:
            subject_students = StudentProfile.objects.filter(section=subject.section).count()
            subject_grades = Grade.objects.filter(subject=subject)
            subject_avg = subject_grades.aggregate(Avg('grade'))['grade__avg'] or 0
            subject_stats.append({
                'subject': subject,
                'student_count': subject_students,
                'average_grade': round(subject_avg, 2),
                'grades_count': subject_grades.count()
            })
    
    # Calculate weekly attendance data (last 7 days)
    today = timezone.now().date()
    weekly_attendance_data = []
    weekly_attendance_labels = []
    
    for i in range(6, -1, -1):  # Last 7 days (6 days ago to today)
        date = today - timedelta(days=i)
        date_attendance = Attendance.objects.filter(
            subject__teacher=teacher_profile,
            date=date
        )
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
    }
    
    return render(request, 'teachers/dashboard.html', context)

@login_required
def subjects(request):
    if request.user.role != 'teacher':
        return redirect('dashboard')
    
    try:
        teacher_profile = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        return redirect('dashboard')
    
    # Get teacher's subjects with related data
    subjects = Subject.objects.filter(teacher=teacher_profile).select_related('section').order_by('code')
    
    # Get student count for each subject (students in that section)
    subjects_with_counts = []
    total_students = 0
    unique_sections = set()
    unique_student_ids = set()
    
    for subject in subjects:
        student_count = StudentProfile.objects.filter(section=subject.section).count()
        subjects_with_counts.append({
            'subject': subject,
            'student_count': student_count,
        })
        total_students += student_count
        unique_sections.add(subject.section.id)
        
        # Get unique students across all subjects
        section_students = StudentProfile.objects.filter(section=subject.section)
        for student in section_students:
            unique_student_ids.add(student.id)
    
    # Calculate statistics
    total_subjects = len(subjects_with_counts)
    total_unique_students = len(unique_student_ids)
    total_sections = len(unique_sections)
    avg_students_per_subject = (total_students / total_subjects) if total_subjects > 0 else 0
    
    context = {
        'subjects': subjects_with_counts,
        'teacher_profile': teacher_profile,
        'total_subjects': total_subjects,
        'total_students': total_unique_students,
        'total_sections': total_sections,
        'avg_students_per_subject': round(avg_students_per_subject, 1),
    }
    return render(request, 'teachers/subjects.html', context)

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
    
    # Get sections where teacher teaches subjects
    sections_with_subjects_ids = ClassSection.objects.filter(
        subject__teacher=teacher_profile
    ).values_list('id', flat=True).distinct()
    
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
        # Get students in this section
        students = StudentProfile.objects.filter(section=section)
        student_count = students.count()
        total_students_all += student_count
        
        # Get subjects teacher teaches in this section
        subjects = Subject.objects.filter(teacher=teacher_profile, section=section)
        subject_names = [s.name for s in subjects]
        
        # Calculate attendance for this section
        section_attendance = Attendance.objects.filter(
            subject__teacher=teacher_profile,
            subject__section=section
        )
        present_count = section_attendance.filter(status='present').count()
        total_attendance = section_attendance.count()
        attendance_percentage = (present_count / total_attendance * 100) if total_attendance > 0 else 0
        
        total_attendance_present += present_count
        total_attendance_count += total_attendance
        
        # Calculate average grade for this section
        section_grades = Grade.objects.filter(
            subject__teacher=teacher_profile,
            subject__section=section
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
            'subjects': subject_names,
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
    
    # Get all subjects taught by this teacher
    subjects = Subject.objects.filter(teacher=teacher_profile).select_related('section').order_by('code', 'name')
    
    # Get subjects with their students
    subjects_data = []
    unique_student_ids = set()
    student_status_map = {}  # Track overall status per student
    
    for subject in subjects:
        # Get all students in this subject's section
        section_students = StudentProfile.objects.filter(
            section=subject.section
        ).select_related('user', 'section').order_by('user__last_name', 'user__first_name')
        
        student_count = section_students.count()
        if student_count == 0:
            continue
        
        # Calculate statistics for each student in this subject
        students_data = []
        subject_attendance_sum = 0
        subject_grades_sum = 0
        subject_grades_count = 0
        
        for student in section_students:
            # Track unique students across all subjects
            unique_student_ids.add(student.id)
            
            # Calculate attendance percentage for this specific subject
            student_attendance = Attendance.objects.filter(
                student=student,
                subject=subject
            )
            total_attendance = student_attendance.count()
            present_count = student_attendance.filter(status='present').count()
            attendance_percentage = (present_count / total_attendance * 100) if total_attendance > 0 else 0
            subject_attendance_sum += attendance_percentage
            
            # Calculate grade for this specific subject
            student_grades = Grade.objects.filter(
                student=student,
                subject=subject
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
    }
    return render(request, 'teachers/students.html', context)

@login_required
@role_required('teacher')
def attendance(request):
    try:
        teacher_profile = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        return redirect('dashboard')
    
    # Handle POST request to save attendance
    if request.method == 'POST':
        # Validate and sanitize input
        selected_subject_id = validate_input(request.POST.get('subject'), 'integer')
        if not selected_subject_id:
            messages.error(request, 'Invalid subject selected.')
            return redirect('teachers:attendance')
        
        # Validate teacher has access to this subject
        has_access, subject_or_error = validate_teacher_access(request, subject_id=selected_subject_id)
        if not has_access:
            messages.error(request, subject_or_error)
            return redirect('teachers:attendance')
        
        selected_subject = subject_or_error
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
                            section=selected_subject.section
                        )
                        
                        # Check if attendance record exists for today
                        attendance_record = Attendance.objects.filter(
                            student=student,
                            subject=selected_subject,
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
                                    student=student,
                                    subject=selected_subject,
                                    date=today,
                                    status=status
                                )
                                created = True
                                created_count += 1
                            except IntegrityError:
                                # Race condition: another request created it
                                # Fetch and update the existing record
                                attendance_record = Attendance.objects.filter(
                                    student=student,
                                    subject=selected_subject,
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
        
        return redirect(reverse('teachers:attendance') + '?subject=' + str(selected_subject_id) + '&saved=true')
    
    # Get teacher's subjects
    subjects = Subject.objects.filter(teacher=teacher_profile).select_related('section').order_by('code')
    
    # Get today's date
    today = timezone.now().date()
    
    # Get selected subject from query parameter
    selected_subject_id = request.GET.get('subject')
    selected_subject = None
    students_data = []
    
    if selected_subject_id:
        try:
            selected_subject = Subject.objects.get(id=selected_subject_id, teacher=teacher_profile)
            # Get students in this subject's section
            if selected_subject.section:
                students = StudentProfile.objects.filter(section=selected_subject.section).select_related('user').order_by('user__last_name', 'user__first_name')
                
                # Get existing attendance records for today
                attendance_records = Attendance.objects.filter(
                    subject=selected_subject,
                    date=today
                ).select_related('student')
                
                # Create a dictionary mapping student_id to attendance status
                attendance_dict = {record.student.id: record.status for record in attendance_records}
                
                # Prepare students data with attendance status
                for student in students:
                    students_data.append({
                        'student': student,
                        'attendance_status': attendance_dict.get(student.id, '')
                    })
        except Subject.DoesNotExist:
            pass
    
    context = {
        'subjects': subjects,
        'selected_subject': selected_subject,
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
    
    # Get teacher's subjects
    subjects = Subject.objects.filter(teacher=teacher_profile).select_related('section').order_by('code')
    
    # Get all unique sections from teacher's subjects
    section_ids = subjects.values_list('section', flat=True).distinct()
    sections = ClassSection.objects.filter(id__in=section_ids).order_by('name')
    
    # Get all students in teacher's sections
    students = StudentProfile.objects.filter(
        section__in=section_ids
    ).select_related('user', 'section').order_by('section__name', 'user__last_name', 'user__first_name')
    
    # Get all assessments for teacher's subjects
    assessments = Assessment.objects.filter(
        subject__teacher=teacher_profile
    ).select_related('subject', 'created_by').order_by('-date', 'category', 'name')
    
    # Get all assessment scores
    assessment_scores = AssessmentScore.objects.filter(
        assessment__subject__teacher=teacher_profile
    ).select_related('student', 'assessment', 'recorded_by')
    
    # Get category weights for each subject
    category_weights_dict = {}
    for subject in subjects:
        try:
            weights = CategoryWeights.objects.get(subject=subject)
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
    all_subjects = list(subjects.values_list('code', flat=True).distinct())
    
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
    for subject in subjects:
        section_name = subject.section.name
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
        assessments_data.append({
            'id': assessment.id,
            'name': assessment.name,
            'category': assessment.category,
            'subject': assessment.subject.code,  # Use code instead of name for consistency
            'subjectId': assessment.subject.id,
            'maxScore': float(assessment.max_score),
            'date': assessment.date.strftime('%Y-%m-%d'),
            'term': assessment.term,
        })
    
    scores_data = []
    for score in assessment_scores:
        scores_data.append({
            'id': score.id,
            'studentId': score.student.id,
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
        
        # Validate assessment name
        assessment_name = validate_input(data.get('name'), 'string', max_length=200)
        if not assessment_name:
            return JsonResponse({'success': False, 'error': 'Invalid assessment name'}, status=400)
        
        # Check for duplicate assessment name in the same subject
        if Assessment.objects.filter(subject=subject, name=assessment_name).exists():
            return JsonResponse({
                'success': False,
                'error': f'An assessment with the name "{assessment_name}" already exists for this subject.'
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
            subject=subject,
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
        # Get category weights for this subject
        try:
            weights = CategoryWeights.objects.get(subject=subject)
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
        
        # Get all assessments for this subject and term
        assessments = Assessment.objects.filter(subject=subject, term=term)
        
        if not assessments.exists():
            # No assessments for this term, delete grade if exists
            Grade.objects.filter(student=student, subject=subject, term=term).delete()
            return None
        
        # Calculate weighted average for each category
        total_weighted = 0
        total_weight = 0
        
        for category in ['Activities', 'Quizzes', 'Projects', 'Exams']:
            category_assessments = assessments.filter(category=category)
            if not category_assessments.exists():
                continue
            
            # Get all scores for this category
            category_scores = AssessmentScore.objects.filter(
                student=student,
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
                    student=student,
                    subject=subject,
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
            Grade.objects.filter(student=student, subject=subject, term=term).delete()
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
        
        # Handle score deletion or update/create
        try:
            assessment_score = AssessmentScore.objects.get(student=student, assessment=assessment)
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
                    student=student,
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
        
        # Update or create category weights within transaction
        category_weights, created = CategoryWeights.objects.select_for_update().update_or_create(
            subject=subject,
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
    
    # Get teacher's subjects
    subjects = Subject.objects.filter(teacher=teacher_profile).select_related('section').order_by('code')
    
    # Get all sections where teacher teaches
    section_ids = subjects.values_list('section', flat=True).distinct()
    sections = ClassSection.objects.filter(id__in=section_ids).order_by('name')
    
    # Get all students in teacher's sections
    students = StudentProfile.objects.filter(section__in=section_ids).select_related(
        'user', 'section'
    ).order_by('section__name', 'user__last_name', 'user__first_name')
    
    # Calculate low performance students
    # Criteria: GPA < 75 OR Attendance < 70%
    low_performance_students = []
    
    for student in students:
        # Calculate GPA (average grade) for this student
        student_grades = Grade.objects.filter(
            student=student,
            subject__teacher=teacher_profile
        )
        
        gpa = 0
        if student_grades.exists():
            gpa = student_grades.aggregate(Avg('grade'))['grade__avg'] or 0
        
        # Calculate attendance percentage
        student_attendance = Attendance.objects.filter(
            student=student,
            subject__teacher=teacher_profile
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
    if request.user.role != 'teacher':
        return redirect('dashboard')
    context = {
        'page_title': 'Notifications',
        'page_description': 'View and manage all your notifications and alerts.'
    }
    return render(request, 'teachers/notifications.html', context)
    