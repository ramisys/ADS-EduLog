from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q
from django.db.models.functions import TruncMonth
from django.utils import timezone
from django.utils.safestring import mark_safe
from datetime import timedelta
import json
from core.models import StudentProfile, Grade, Attendance, Subject, Notification, Assessment, AssessmentScore, StudentEnrollment, Semester, TeacherSubjectAssignment
from core.db_functions import calculate_student_gpa, calculate_attendance_rate

def percentage_to_gwa(percentage):
    """
    Convert percentage grade (0-100) to GWA (General Weighted Average) scale.
    GWA scale: 1.0 (excellent) to 5.0 (failing), where lower is better.
    
    Scale:
    - 97-100% = 1.0
    - 94-96% = 1.25
    - 91-93% = 1.5
    - 88-90% = 1.75
    - 85-87% = 2.0
    - 82-84% = 2.25
    - 79-81% = 2.5
    - 76-78% = 2.75
    - 75% = 3.0
    - Below 75% = 5.0
    """
    if percentage >= 97:
        return 1.0
    elif percentage >= 94:
        return 1.25
    elif percentage >= 91:
        return 1.5
    elif percentage >= 88:
        return 1.75
    elif percentage >= 85:
        return 2.0
    elif percentage >= 82:
        return 2.25
    elif percentage >= 79:
        return 2.5
    elif percentage >= 76:
        return 2.75
    elif percentage >= 75:
        return 3.0
    else:
        return 5.0

@login_required
def dashboard(request):
    # Ensure user is a student
    if request.user.role != 'student':
        return redirect('dashboard')
    
    try:
        student_profile = StudentProfile.objects.get(user=request.user)
    except StudentProfile.DoesNotExist:
        return redirect('dashboard')
    
    # Get current semester
    current_semester = Semester.get_current()
    
    # Get student's enrollments for current semester
    enrollments = StudentEnrollment.objects.filter(
        student=student_profile,
        is_active=True
    )
    if current_semester:
        enrollments = enrollments.filter(semester=current_semester)
    
    # Get subjects from enrollments
    subjects = [enrollment.assignment.subject for enrollment in enrollments.select_related('assignment__subject')]
    
    # Get recent grades - filter by current semester
    recent_grades = Grade.objects.filter(enrollment__student=student_profile)
    if current_semester:
        recent_grades = recent_grades.filter(enrollment__semester=current_semester)
    recent_grades = recent_grades.select_related('enrollment__assignment__subject').order_by('-id')[:10]
    
    # Get grade statistics using database function (filtered by current semester)
    all_grades = Grade.objects.filter(enrollment__student=student_profile)
    if current_semester:
        all_grades = all_grades.filter(enrollment__semester=current_semester)
    
    gpa_result = calculate_student_gpa(student_id=student_profile.id)
    if 'error' not in gpa_result:
        average_grade = gpa_result.get('average_grade', 0)
        total_subjects_with_grades = gpa_result.get('grade_count', 0)
    else:
        # Fallback to manual calculation if function fails
        average_grade = all_grades.aggregate(Avg('grade'))['grade__avg'] or 0
        total_subjects_with_grades = all_grades.values('enrollment__assignment__subject').distinct().count()
    
    # Get recent attendance - filter by current semester
    recent_attendance = Attendance.objects.filter(enrollment__student=student_profile)
    if current_semester:
        recent_attendance = recent_attendance.filter(enrollment__semester=current_semester)
    recent_attendance = recent_attendance.select_related('enrollment__assignment__subject').order_by('-date')[:10]
    
    # Get total attendance queryset (needed for monthly data later) - filter by current semester
    total_attendance = Attendance.objects.filter(enrollment__student=student_profile)
    if current_semester:
        total_attendance = total_attendance.filter(enrollment__semester=current_semester)
    
    # Calculate attendance statistics using database function
    attendance_result = calculate_attendance_rate(student_id=student_profile.id)
    if 'error' not in attendance_result:
        present_count = attendance_result.get('present_count', 0)
        absent_count = attendance_result.get('absent_count', 0)
        late_count = attendance_result.get('late_count', 0)
        total_count = attendance_result.get('total_count', 0)
        attendance_percentage = attendance_result.get('attendance_rate', 0)
    else:
        # Fallback to manual calculation if function fails
        present_count = total_attendance.filter(status='present').count()
        absent_count = total_attendance.filter(status='absent').count()
        late_count = total_attendance.filter(status='late').count()
        total_count = total_attendance.count()
        attendance_percentage = (present_count / total_count * 100) if total_count > 0 else 0
    
    # Get unread notifications
    notifications = Notification.objects.filter(recipient=request.user, is_read=False).order_by('-created_at')[:5]
    alerts_count = notifications.count()
    
    # Calculate GWA (General Weighted Average) from percentage grade
    # Assuming grades are stored as percentages (0-100)
    gwa = percentage_to_gwa(float(average_grade)) if average_grade > 0 else 5.0
    gwa = round(gwa, 2)
    
    # Determine GWA ranking badge (for GWA, lower is better)
    if gwa <= 1.5:
        gwa_badge = "Excellent"
        gwa_badge_class = "bg-success-subtle text-success"
    elif gwa <= 2.0:
        gwa_badge = "Very Good"
        gwa_badge_class = "bg-success-subtle text-success"
    elif gwa <= 2.75:
        gwa_badge = "Good"
        gwa_badge_class = "bg-info-subtle text-info"
    elif gwa <= 3.0:
        gwa_badge = "Passing"
        gwa_badge_class = "bg-warning-subtle text-warning"
    else:
        gwa_badge = "Needs Improvement"
        gwa_badge_class = "bg-danger-subtle text-danger"
    
    # Determine attendance badge
    if attendance_percentage >= 95:
        attendance_badge = "Excellent"
        attendance_badge_class = "bg-success-subtle text-success"
    elif attendance_percentage >= 90:
        attendance_badge = "Very Good"
        attendance_badge_class = "bg-success-subtle text-success"
    elif attendance_percentage >= 80:
        attendance_badge = "Good"
        attendance_badge_class = "bg-info-subtle text-info"
    else:
        attendance_badge = "Needs Improvement"
        attendance_badge_class = "bg-warning-subtle text-warning"
    
    # Determine average grade badge
    if average_grade >= 90:
        grade_badge = "Excellent"
        grade_badge_class = "bg-success-subtle text-success"
    elif average_grade >= 80:
        grade_badge = "Performing well"
        grade_badge_class = "bg-info-subtle text-info"
    elif average_grade >= 70:
        grade_badge = "Average"
        grade_badge_class = "bg-warning-subtle text-warning"
    else:
        grade_badge = "Needs Improvement"
        grade_badge_class = "bg-danger-subtle text-danger"
    
    # Determine alerts badge
    if alerts_count == 0:
        alerts_badge = "All clear"
        alerts_badge_class = "bg-success-subtle text-success"
    elif alerts_count <= 2:
        alerts_badge = "Action needed"
        alerts_badge_class = "bg-warning-subtle text-warning"
    else:
        alerts_badge = "Urgent"
        alerts_badge_class = "bg-danger-subtle text-danger"
    
    # Get grades by subject
    grades_by_subject = {}
    for subject in subjects:
        subject_grades = Grade.objects.filter(enrollment__student=student_profile, enrollment__assignment__subject=subject)
        if subject_grades.exists():
            grades_by_subject[subject] = {
                'grades': subject_grades.order_by('term'),
                'average': subject_grades.aggregate(Avg('grade'))['grade__avg'] or 0
            }
    
    # Calculate performance distribution
    excellent_count = 0  # >= 90%
    good_count = 0  # 80-89%
    needs_improvement_count = 0  # < 80%
    
    for subject in subjects:
        subject_grades = Grade.objects.filter(enrollment__student=student_profile, enrollment__assignment__subject=subject)
        if subject_grades.exists():
            avg_grade = subject_grades.aggregate(Avg('grade'))['grade__avg'] or 0
            if avg_grade >= 90:
                excellent_count += 1
            elif avg_grade >= 80:
                good_count += 1
            else:
                needs_improvement_count += 1
    
    # Get monthly attendance data (last 6 months) for chart
    month_pointer = timezone.now().date().replace(day=1)
    month_starts = []
    for _ in range(6):
        month_starts.append(month_pointer)
        if month_pointer.month == 1:
            month_pointer = month_pointer.replace(year=month_pointer.year - 1, month=12)
        else:
            month_pointer = month_pointer.replace(month=month_pointer.month - 1)
    month_starts.reverse()
    
    monthly_attendance_data = []
    attendance_trend_data = []
    
    for start_date in month_starts:
        # Calculate end date (first day of next month)
        if start_date.month == 12:
            end_date = start_date.replace(year=start_date.year + 1, month=1)
        else:
            end_date = start_date.replace(month=start_date.month + 1)
        
        month_attendance = total_attendance.filter(date__gte=start_date, date__lt=end_date)
        month_present = month_attendance.filter(status='present').count()
        month_total = month_attendance.count()
        month_rate = (month_present / month_total * 100) if month_total > 0 else 0
        
        monthly_attendance_data.append({
            'month': start_date.strftime('%b'),
            'rate': round(month_rate, 1),
        })
        
        attendance_trend_data.append({
            'month': start_date.strftime('%b'),
            'rate': round(month_rate, 1),
        })
    
    # Get grade progress by subject (current vs previous term) for chart
    grade_progress_by_subject = []
    for subject in subjects:
        subject_grades = Grade.objects.filter(enrollment__student=student_profile, enrollment__assignment__subject=subject).order_by('term')
        if subject_grades.exists():
            # Get latest term (current) and previous term
            terms_list = list(subject_grades.values_list('term', flat=True).distinct().order_by('term'))
            if len(terms_list) >= 2:
                # Has both current and previous term
                current_term = terms_list[-1]
                previous_term = terms_list[-2]
                
                current_grades = subject_grades.filter(term=current_term)
                previous_grades = subject_grades.filter(term=previous_term)
                
                current_avg = current_grades.aggregate(Avg('grade'))['grade__avg'] or 0
                previous_avg = previous_grades.aggregate(Avg('grade'))['grade__avg'] or 0
            elif len(terms_list) == 1:
                # Only has current term
                current_term = terms_list[0]
                current_grades = subject_grades.filter(term=current_term)
                current_avg = current_grades.aggregate(Avg('grade'))['grade__avg'] or 0
                previous_avg = 0  # No previous term data
            else:
                current_avg = 0
                previous_avg = 0
            
            grade_progress_by_subject.append({
                'subject': subject.name[:15],  # Limit length
                'current': round(current_avg, 2),
                'previous': round(previous_avg, 2),
            })
    
    # Calculate performance distribution with more categories
    excellent_count = 0  # >= 90%
    good_count = 0  # 80-89%
    average_count = 0  # 70-79%
    needs_improvement_count = 0  # < 70%
    
    for subject in subjects:
        subject_grades = Grade.objects.filter(enrollment__student=student_profile, enrollment__assignment__subject=subject)
        if subject_grades.exists():
            avg_grade = subject_grades.aggregate(Avg('grade'))['grade__avg'] or 0
            if avg_grade >= 90:
                excellent_count += 1
            elif avg_grade >= 80:
                good_count += 1
            elif avg_grade >= 70:
                average_count += 1
            else:
                needs_improvement_count += 1
    
    # Get subject performance data for radar chart (all subjects, even without grades)
    subject_performance_data = []
    subject_labels = []
    for enrollment in enrollments:
        subject = enrollment.assignment.subject
        subject_grades = Grade.objects.filter(enrollment=enrollment)
        if current_semester:
            subject_grades = subject_grades.filter(enrollment__semester=current_semester)
        if subject_grades.exists():
            avg_grade = subject_grades.aggregate(Avg('grade'))['grade__avg'] or 0
            subject_performance_data.append(round(avg_grade, 2))
        else:
            subject_performance_data.append(0)  # No grades yet
        subject_labels.append(subject.name[:10])  # Use subject name, limit length
    
    context = {
        'student_profile': student_profile,
        'subjects': subjects,
        'recent_grades': recent_grades,
        'recent_attendance': recent_attendance,
        'average_grade': round(average_grade, 2),
        'total_subjects_with_grades': total_subjects_with_grades,
        'present_count': present_count,
        'absent_count': absent_count,
        'late_count': late_count,
        'attendance_percentage': round(attendance_percentage, 1),
        'notifications': notifications,
        'alerts_count': alerts_count,
        'grades_by_subject': grades_by_subject,
        'gwa': gwa,
        'gwa_badge': gwa_badge,
        'gwa_badge_class': gwa_badge_class,
        'attendance_badge': attendance_badge,
        'attendance_badge_class': attendance_badge_class,
        'grade_badge': grade_badge,
        'grade_badge_class': grade_badge_class,
        'alerts_badge': alerts_badge,
        'alerts_badge_class': alerts_badge_class,
        'excellent_count': excellent_count,
        'good_count': good_count,
        'average_count': average_count,
        'needs_improvement_count': needs_improvement_count,
        'monthly_attendance_data': monthly_attendance_data,
        'attendance_trend_data': attendance_trend_data,
        'grade_progress_by_subject': grade_progress_by_subject,
        'subject_performance_data': subject_performance_data,
        'subject_labels': subject_labels,
        'current_semester': current_semester,
        'performance_distribution': {
            'excellent': excellent_count,
            'good': good_count,
            'average': average_count,
            'needsImprovement': needs_improvement_count,
        },
    }
    
    return render(request, 'students/dashboard.html', context)


@login_required
def subjects(request):
    if request.user.role != 'student':
        return redirect('dashboard')
    
    try:
        student_profile = StudentProfile.objects.get(user=request.user)
    except StudentProfile.DoesNotExist:
        return redirect('dashboard')
    
    # Get student's subjects (based on their section)
    subjects_list = []
    if student_profile.section:
        subjects_list = Subject.objects.filter(section=student_profile.section).select_related('teacher', 'teacher__user', 'section')
    
    # Prepare subjects with detailed statistics
    subjects_with_stats = []
    total_credits = 0  # Placeholder - credits not in model
    pending_tasks_count = 0  # Could be calculated from assessments if needed
    
    for subject in subjects_list:
        # Get grades for this subject
        subject_grades = Grade.objects.filter(enrollment__student=student_profile, enrollment__assignment__subject=subject)
        average_grade = subject_grades.aggregate(Avg('grade'))['grade__avg'] or 0
        average_grade = round(average_grade, 2)
        
        # Calculate grade letter
        if average_grade >= 97:
            grade_letter = "A+"
        elif average_grade >= 93:
            grade_letter = "A"
        elif average_grade >= 90:
            grade_letter = "A-"
        elif average_grade >= 87:
            grade_letter = "B+"
        elif average_grade >= 83:
            grade_letter = "B"
        elif average_grade >= 80:
            grade_letter = "B-"
        elif average_grade >= 77:
            grade_letter = "C+"
        elif average_grade >= 73:
            grade_letter = "C"
        elif average_grade >= 70:
            grade_letter = "C-"
        elif average_grade >= 67:
            grade_letter = "D+"
        elif average_grade >= 65:
            grade_letter = "D"
        else:
            grade_letter = "F"
        
        # Get attendance for this subject
        subject_attendance = Attendance.objects.filter(enrollment__student=student_profile, enrollment__assignment__subject=subject)
        present_count = subject_attendance.filter(status='present').count()
        total_attendance_count = subject_attendance.count()
        attendance_percentage = (present_count / total_attendance_count * 100) if total_attendance_count > 0 else 0
        attendance_percentage = round(attendance_percentage, 1)
        
        # Get assessments/tasks for this subject (for pending tasks count)
        subject_assessments = Assessment.objects.filter(subject=subject)
        completed_assessments = AssessmentScore.objects.filter(
            student=student_profile,
            assessment__subject=subject
        ).count()
        pending_assessments = subject_assessments.count() - completed_assessments
        pending_tasks_count += max(0, pending_assessments)
        
        # Calculate course progress (simplified - based on assessments completed)
        total_assessments = subject_assessments.count()
        course_progress = (completed_assessments / total_assessments * 100) if total_assessments > 0 else 0
        course_progress = round(course_progress, 1)
        
        # Get teacher name
        teacher_name = subject.teacher.user.get_full_name() if subject.teacher and subject.teacher.user else "TBA"
        
        subjects_with_stats.append({
            'subject': subject,
            'average_grade': average_grade,
            'grade_letter': grade_letter,
            'attendance_percentage': attendance_percentage,
            'course_progress': course_progress,
            'completed_assessments': completed_assessments,
            'total_assessments': total_assessments,
            'pending_assessments': pending_assessments,
            'teacher_name': teacher_name,
        })
    
    # Calculate overall statistics
    total_courses = len(subjects_with_stats)
    total_credits = total_courses * 3  # Placeholder - 3 credits per course (not in model)
    
    # Calculate overall average attendance
    if subjects_with_stats:
        overall_attendance = sum(s['attendance_percentage'] for s in subjects_with_stats) / len(subjects_with_stats)
        overall_attendance = round(overall_attendance, 1)
    else:
        overall_attendance = 0
    
    context = {
        'page_title': 'Subjects',
        'page_description': 'View all your enrolled subjects and course information.',
        'subjects': subjects_with_stats,
        'total_courses': total_courses,
        'total_credits': total_credits,
        'pending_tasks_count': pending_tasks_count,
        'overall_attendance': overall_attendance,
        'student_profile': student_profile,
    }
    return render(request, 'students/subjects.html', context)


@login_required
def attendance(request):
    if request.user.role != 'student':
        return redirect('dashboard')
    
    try:
        student_profile = StudentProfile.objects.get(user=request.user)
    except StudentProfile.DoesNotExist:
        return redirect('dashboard')
    
    # Get all attendance records
    all_attendance = Attendance.objects.filter(enrollment__student=student_profile).select_related('enrollment__student', 'enrollment__assignment__subject', 'enrollment__assignment__teacher__user').order_by('-date')
    
    # Calculate overall statistics
    present_count = all_attendance.filter(status='present').count()
    absent_count = all_attendance.filter(status='absent').count()
    late_count = all_attendance.filter(status='late').count()
    total_count = all_attendance.count()
    attendance_rate = (present_count / total_count * 100) if total_count > 0 else 0
    attendance_rate = round(attendance_rate, 1)
    
    # Determine attendance badge
    if attendance_rate >= 95:
        attendance_badge = "Excellent"
        attendance_badge_class = "bg-success-subtle text-success"
    elif attendance_rate >= 90:
        attendance_badge = "Very Good"
        attendance_badge_class = "bg-success-subtle text-success"
    elif attendance_rate >= 80:
        attendance_badge = "Good"
        attendance_badge_class = "bg-info-subtle text-info"
    else:
        attendance_badge = "Needs Improvement"
        attendance_badge_class = "bg-warning-subtle text-warning"
    
    # Get attendance by subject - get subjects from student's enrollments
    enrollments = StudentEnrollment.objects.filter(
        student=student_profile,
        is_active=True
    ).select_related('assignment__subject', 'assignment__subject__code').distinct()
    
    # Get unique subjects from enrollments
    subject_ids = set()
    subject_dict = {}  # Store subject objects by ID for later use
    for enrollment in enrollments:
        if enrollment.assignment and enrollment.assignment.subject:
            subject = enrollment.assignment.subject
            subject_ids.add(subject.id)
            subject_dict[subject.id] = subject
    
    # Always use a queryset, even if empty
    if subject_ids:
        subjects = Subject.objects.filter(id__in=subject_ids)
    else:
        subjects = Subject.objects.none()
    
    attendance_by_subject = []
    for subject in subjects:
        subject_attendance = Attendance.objects.filter(enrollment__student=student_profile, enrollment__assignment__subject=subject)
        subject_present = subject_attendance.filter(status='present').count()
        subject_absent = subject_attendance.filter(status='absent').count()
        subject_late = subject_attendance.filter(status='late').count()
        subject_total = subject_attendance.count()
        subject_rate = (subject_present / subject_total * 100) if subject_total > 0 else 0
        subject_rate = round(subject_rate, 1)
        
        attendance_by_subject.append({
            'subject': subject,
            'present': subject_present,
            'absent': subject_absent,
            'late': subject_late,
            'total': subject_total,
            'rate': subject_rate,
        })
    
    # Get monthly attendance data (last 6 months)
    month_pointer = timezone.now().date().replace(day=1)
    month_starts = []
    for _ in range(6):
        month_starts.append(month_pointer)
        if month_pointer.month == 1:
            month_pointer = month_pointer.replace(year=month_pointer.year - 1, month=12)
        else:
            month_pointer = month_pointer.replace(month=month_pointer.month - 1)
    month_starts.reverse()
    
    monthly_attendance = []
    attendance_trend = []
    
    for start_date in month_starts:
        # Calculate end date (first day of next month)
        if start_date.month == 12:
            end_date = start_date.replace(year=start_date.year + 1, month=1)
        else:
            end_date = start_date.replace(month=start_date.month + 1)
        
        month_attendance = all_attendance.filter(date__gte=start_date, date__lt=end_date)
        month_present = month_attendance.filter(status='present').count()
        month_absent = month_attendance.filter(status='absent').count()
        month_late = month_attendance.filter(status='late').count()
        month_total = month_attendance.count()
        month_rate = (month_present / month_total * 100) if month_total > 0 else 0
        
        monthly_attendance.append({
            'month': start_date.strftime('%b'),
            'present': month_present,
            'absent': month_absent,
            'late': month_late,
        })
        
        attendance_trend.append({
            'month': start_date.strftime('%b'),
            'rate': round(month_rate, 1),
        })
    
    # Get attendance history (all records for the table)
    attendance_history = []
    for record in all_attendance[:100]:  # Limit to last 100 records
        subject = record.subject  # Use property which accesses enrollment.assignment.subject
        attendance_history.append({
            'date': record.date.strftime('%Y-%m-%d'),
            'subject': subject.name if subject else 'N/A',
            'subject_code': subject.code if subject else 'N/A',
            'status': record.status,
        })
    
    # Get unique subjects for filter dropdown
    # Extract subject names directly from subject_dict to avoid queryset evaluation issues
    subject_list = [subject.name for subject in subject_dict.values() if subject.name]
    
    context = {
        'page_title': 'Attendance',
        'page_description': 'View your attendance records and history.',
        'student_profile': student_profile,
        'present_count': present_count,
        'absent_count': absent_count,
        'late_count': late_count,
        'total_count': total_count,
        'attendance_rate': attendance_rate,
        'attendance_badge': attendance_badge,
        'attendance_badge_class': attendance_badge_class,
        'attendance_by_subject': attendance_by_subject,
        'monthly_attendance': monthly_attendance,
        'attendance_trend': attendance_trend,
        'attendance_history': attendance_history,
        'subject_list': subject_list,
    }
    return render(request, 'students/attendance.html', context)


@login_required
def grades(request):
    if request.user.role != 'student':
        return redirect('dashboard')
    
    try:
        student_profile = StudentProfile.objects.get(user=request.user)
    except StudentProfile.DoesNotExist:
        return redirect('dashboard')
    
    # Get all grades
    all_grades = Grade.objects.filter(enrollment__student=student_profile).select_related('enrollment__student', 'enrollment__assignment__subject', 'enrollment__assignment__teacher__user')
    
    # Calculate current GWA (from all grades)
    average_grade = all_grades.aggregate(Avg('grade'))['grade__avg'] or 0
    current_gwa = percentage_to_gwa(float(average_grade)) if average_grade > 0 else 5.0
    current_gwa = round(current_gwa, 2)
    
    # For cumulative GWA, we'll use the same for now (can be enhanced with historical data)
    cumulative_gwa = current_gwa
    
    # Get subjects with grades - get subjects from student's enrollments
    enrollments = StudentEnrollment.objects.filter(
        student=student_profile,
        is_active=True
    ).select_related('assignment__subject').distinct()
    
    # Get unique subjects from enrollments
    subject_ids = set()
    subject_dict = {}  # Store subject objects by ID
    for enrollment in enrollments:
        if enrollment.assignment and enrollment.assignment.subject:
            subject = enrollment.assignment.subject
            subject_ids.add(subject.id)
            subject_dict[subject.id] = subject
    
    # Always use a queryset, even if empty
    if subject_ids:
        subjects = Subject.objects.filter(id__in=subject_ids)
    else:
        subjects = Subject.objects.none()
    
    course_grades = []
    total_credits = 0
    grade_distribution = {'A+': 0, 'A': 0, 'A-': 0, 'B+': 0, 'B': 0, 'B-': 0, 'C+': 0, 'C': 0, 'C-': 0, 'D+': 0, 'D': 0, 'F': 0}
    
    for subject in subjects:
        subject_grades = Grade.objects.filter(enrollment__student=student_profile, enrollment__assignment__subject=subject)
        if subject_grades.exists():
            avg_grade = subject_grades.aggregate(Avg('grade'))['grade__avg'] or 0
            avg_grade = round(avg_grade, 2)
            
            # Calculate grade letter
            if avg_grade >= 97:
                grade_letter = "A+"
            elif avg_grade >= 93:
                grade_letter = "A"
            elif avg_grade >= 90:
                grade_letter = "A-"
            elif avg_grade >= 87:
                grade_letter = "B+"
            elif avg_grade >= 83:
                grade_letter = "B"
            elif avg_grade >= 80:
                grade_letter = "B-"
            elif avg_grade >= 77:
                grade_letter = "C+"
            elif avg_grade >= 73:
                grade_letter = "C"
            elif avg_grade >= 70:
                grade_letter = "C-"
            elif avg_grade >= 67:
                grade_letter = "D+"
            elif avg_grade >= 65:
                grade_letter = "D"
            else:
                grade_letter = "F"
            
            grade_distribution[grade_letter] = grade_distribution.get(grade_letter, 0) + 1
            
            # Get teacher from enrollment/assignment, not directly from subject
            # Find the assignment for this subject and student
            assignment = TeacherSubjectAssignment.objects.filter(
                subject=subject,
                enrollments__student=student_profile,
                enrollments__is_active=True
            ).select_related('teacher__user').first()
            teacher_name = assignment.teacher.user.get_full_name() if assignment and assignment.teacher and assignment.teacher.user else "TBA"
            credits = 3  # Placeholder - not in model
            
            course_grades.append({
                'subject': subject,
                'teacher_name': teacher_name,
                'grade_letter': grade_letter,
                'percentage': avg_grade,
                'credits': credits,
            })
            total_credits += credits
    
    # Prepare grade distribution for chart (only non-zero values)
    grade_distribution_data = []
    for letter, count in grade_distribution.items():
        if count > 0:
            grade_distribution_data.append({
                'name': letter,
                'count': count,
                'value': count * 10  # For chart visualization
            })
    
    # Get GWA trend by term (semester)
    terms = all_grades.values_list('term', flat=True).distinct().order_by('term')
    semester_gwa = []
    for term in terms:
        term_grades = all_grades.filter(term=term)
        term_avg = term_grades.aggregate(Avg('grade'))['grade__avg'] or 0
        term_gwa = percentage_to_gwa(float(term_avg)) if term_avg > 0 else 5.0
        semester_gwa.append({
            'semester': term,
            'gwa': round(term_gwa, 2)
        })
    
    # If no term data, create placeholder
    if not semester_gwa:
        semester_gwa = [{'semester': 'Current', 'gwa': current_gwa}]
    
    # Determine GWA badge (for GWA, lower is better)
    if current_gwa <= 1.5:
        gwa_badge = "Excellent"
        gwa_badge_class = "bg-success-subtle text-success"
    elif current_gwa <= 2.0:
        gwa_badge = "Very Good"
        gwa_badge_class = "bg-success-subtle text-success"
    elif current_gwa <= 2.75:
        gwa_badge = "Good"
        gwa_badge_class = "bg-info-subtle text-info"
    elif current_gwa <= 3.0:
        gwa_badge = "Passing"
        gwa_badge_class = "bg-warning-subtle text-warning"
    else:
        gwa_badge = "Needs Improvement"
        gwa_badge_class = "bg-danger-subtle text-danger"
    
    # Calculate strengths and growth opportunities
    strengths = []
    growth_opportunities = []
    
    for course in course_grades:
        if course['percentage'] >= 90:
            strengths.append(f"{course['subject'].name} - Excellent performance ({course['percentage']}%)")
        elif course['percentage'] < 75:
            growth_opportunities.append(f"{course['subject'].name} - Needs improvement ({course['percentage']}%)")
    
    # Class rank placeholder (would need to calculate from all students)
    class_rank = "N/A"
    total_students = StudentProfile.objects.filter(section=student_profile.section).count() if student_profile.section else 0
    
    # Prepare subject summary data for the grade summary cards (first 3 subjects)
    subject_summary = []
    for course in course_grades[:3]:
        subject_summary.append({
            'id': course['subject'].id,
            'name': course['subject'].name,
            'grade': round(course['percentage'], 0),  # Round for display
        })
    
    # Get detailed assessment scores for grade records
    assessment_scores = (
        AssessmentScore.objects
        .filter(enrollment__student=student_profile)
        .select_related('enrollment__student', 'assessment', 'assessment__assignment__subject', 'recorded_by__user')
        .order_by('-assessment__date', '-created_at')[:50]
    )
    
    detailed_grade_records = []
    for score in assessment_scores:
        assessment = score.assessment
        percentage = round(float(score.percentage), 2) if score.percentage else 0
        
        detailed_grade_records.append({
            'id': f'r{score.id}',
            'title': assessment.name,
            'grade': round(float(score.score), 2),
            'maxGrade': round(float(assessment.max_score), 2),
            'percentage': percentage,  # Add percentage for badge calculation
            'subject': assessment.subject.name,
            'type': assessment.category,
            'date': assessment.date.strftime('%Y-%m-%d') if assessment.date else '',
            'remarks': '',  # AssessmentScore doesn't have remarks field, but template handles empty strings
        })
    
    context = {
        'page_title': 'Grades',
        'page_description': 'View your grades and academic performance.',
        'student_profile': student_profile,
        'current_gwa': current_gwa,
        'cumulative_gwa': cumulative_gwa,
        'total_credits': total_credits,
        'class_rank': class_rank,
        'total_students': total_students,
        'gwa_badge': gwa_badge,
        'gwa_badge_class': gwa_badge_class,
        'course_grades': course_grades,
        'grade_distribution': grade_distribution_data,
        'semester_gwa': semester_gwa,
        'strengths': strengths,
        'growth_opportunities': growth_opportunities,
        'subject_summary': subject_summary,
        'detailed_grade_records': detailed_grade_records,
    }
    return render(request, 'students/grades.html', context)


@login_required
def notifications(request):
    if request.user.role != 'student':
        return redirect('dashboard')
    
    try:
        student_profile = StudentProfile.objects.get(user=request.user)
    except StudentProfile.DoesNotExist:
        return redirect('dashboard')
    
    # Get all notifications for the student
    all_notifications = Notification.objects.filter(recipient=request.user).order_by('-created_at')
    
    # Handle mark as read
    if request.method == 'POST' and 'mark_read' in request.POST:
        notification_id = request.POST.get('mark_read')
        try:
            notification = Notification.objects.get(id=notification_id, recipient=request.user)
            notification.is_read = True
            notification.save()
            return redirect('students:notifications')
        except Notification.DoesNotExist:
            pass
    
    # Handle mark all as read
    if request.method == 'POST' and 'mark_all_read' in request.POST:
        Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
        return redirect('students:notifications')
    
    unread_count = all_notifications.filter(is_read=False).count()
    
    # Get assessments/tasks for the student
    tasks = []
    if student_profile.section:
        subjects = Subject.objects.filter(section=student_profile.section)
        assessments = Assessment.objects.filter(subject__in=subjects).select_related('subject', 'subject__teacher__user', 'created_by__user').order_by('date')
        
        from datetime import date
        today = date.today()
        
        for assessment in assessments:
            # Check if student has completed this assessment
            completed_score = AssessmentScore.objects.filter(enrollment__student=student_profile, assessment=assessment).first()
            is_completed = completed_score is not None
            
            # Determine status
            if is_completed:
                status = 'completed'
            elif assessment.date < today:
                status = 'pending'  # Overdue
            else:
                status = 'pending'  # Not yet due
            
            # Determine priority based on due date
            days_until = (assessment.date - today).days
            if days_until < 0:
                priority = 'high'  # Overdue
            elif days_until <= 2:
                priority = 'high'  # Due soon
            elif days_until <= 7:
                priority = 'medium'
            else:
                priority = 'low'
            
            teacher_name = assessment.subject.teacher.user.get_full_name() if assessment.subject.teacher and assessment.subject.teacher.user else "TBA"
            
            tasks.append({
                'id': assessment.id,
                'title': assessment.name,
                'subject': assessment.subject.name,
                'teacher': teacher_name,
                'description': f"{assessment.category} - {assessment.subject.code}",
                'dueDate': assessment.date.strftime('%Y-%m-%d'),
                'dueTime': '11:59 PM',  # Placeholder
                'type': assessment.category,
                'points': int(assessment.max_score),
                'estimatedTime': '2 hours',  # Placeholder
                'status': status,
                'priority': priority,
                'completedDate': completed_score.created_at.strftime('%Y-%m-%d') if completed_score and completed_score.created_at else None,
            })
    
    # Calculate task statistics
    pending_tasks = [t for t in tasks if t['status'] == 'pending']
    in_progress_tasks = [t for t in tasks if t['status'] == 'in-progress']
    completed_tasks = [t for t in tasks if t['status'] == 'completed']
    high_priority_tasks = [t for t in tasks if t['priority'] == 'high' and t['status'] != 'completed']
    
    # Get unique subjects for filter
    subject_list = list(set([t['subject'] for t in tasks]))
    
    context = {
        'page_title': 'Notifications',
        'page_description': 'View and manage all your notifications and alerts.',
        'notifications': all_notifications,
        'unread_count': unread_count,
        'tasks': tasks,
        'pending_tasks_count': len(pending_tasks),
        'in_progress_tasks_count': len(in_progress_tasks),
        'completed_tasks_count': len(completed_tasks),
        'high_priority_tasks_count': len(high_priority_tasks),
        'subject_list': subject_list,
    }
    return render(request, 'students/notifications.html', context)