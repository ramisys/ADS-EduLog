from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q
from django.db.models.functions import TruncMonth
from django.utils import timezone
from django.utils.safestring import mark_safe
from datetime import timedelta
import json
from core.models import StudentProfile, Grade, Attendance, Subject, Notification, Assessment, AssessmentScore

@login_required
def dashboard(request):
    # Ensure user is a student
    if request.user.role != 'student':
        return redirect('dashboard')
    
    try:
        student_profile = StudentProfile.objects.get(user=request.user)
    except StudentProfile.DoesNotExist:
        return redirect('dashboard')
    
    # Get student's subjects (based on their section)
    subjects = []
    if student_profile.section:
        subjects = Subject.objects.filter(section=student_profile.section)
    
    # Get recent grades
    recent_grades = Grade.objects.filter(student=student_profile).select_related('subject').order_by('-id')[:10]
    
    # Get grade statistics
    all_grades = Grade.objects.filter(student=student_profile)
    average_grade = all_grades.aggregate(Avg('grade'))['grade__avg'] or 0
    total_subjects_with_grades = all_grades.values('subject').distinct().count()
    
    # Get recent attendance
    recent_attendance = Attendance.objects.filter(student=student_profile).select_related('subject').order_by('-date')[:10]
    
    # Calculate attendance statistics
    total_attendance = Attendance.objects.filter(student=student_profile)
    present_count = total_attendance.filter(status='present').count()
    absent_count = total_attendance.filter(status='absent').count()
    late_count = total_attendance.filter(status='late').count()
    total_count = total_attendance.count()
    attendance_percentage = (present_count / total_count * 100) if total_count > 0 else 0
    
    # Get unread notifications
    notifications = Notification.objects.filter(recipient=request.user, is_read=False).order_by('-created_at')[:5]
    alerts_count = notifications.count()
    
    # Calculate GPA (convert percentage to 4.0 scale)
    # Assuming grades are stored as percentages (0-100)
    gpa = (float(average_grade) / 100) * 4.0 if average_grade > 0 else 0.0
    gpa = round(gpa, 2)
    
    # Determine GPA ranking badge (simplified - can be enhanced with actual ranking)
    if gpa >= 3.7:
        gpa_badge = "Top 15%"
        gpa_badge_class = "bg-success-subtle text-success"
    elif gpa >= 3.3:
        gpa_badge = "Top 30%"
        gpa_badge_class = "bg-success-subtle text-success"
    elif gpa >= 3.0:
        gpa_badge = "Above Average"
        gpa_badge_class = "bg-info-subtle text-info"
    else:
        gpa_badge = "Average"
        gpa_badge_class = "bg-warning-subtle text-warning"
    
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
        subject_grades = Grade.objects.filter(student=student_profile, subject=subject)
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
        subject_grades = Grade.objects.filter(student=student_profile, subject=subject)
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
        subject_grades = Grade.objects.filter(student=student_profile, subject=subject).order_by('term')
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
        subject_grades = Grade.objects.filter(student=student_profile, subject=subject)
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
    for subject in subjects:
        subject_grades = Grade.objects.filter(student=student_profile, subject=subject)
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
        'gpa': gpa,
        'gpa_badge': gpa_badge,
        'gpa_badge_class': gpa_badge_class,
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
        subject_grades = Grade.objects.filter(student=student_profile, subject=subject)
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
        subject_attendance = Attendance.objects.filter(student=student_profile, subject=subject)
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
    all_attendance = Attendance.objects.filter(student=student_profile).select_related('subject', 'subject__teacher__user').order_by('-date')
    
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
    
    # Get attendance by subject
    subjects = []
    if student_profile.section:
        subjects = Subject.objects.filter(section=student_profile.section)
    
    attendance_by_subject = []
    for subject in subjects:
        subject_attendance = Attendance.objects.filter(student=student_profile, subject=subject)
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
        attendance_history.append({
            'date': record.date.strftime('%Y-%m-%d'),
            'subject': record.subject.name,
            'subject_code': record.subject.code,
            'status': record.status,
        })
    
    # Get unique subjects for filter dropdown
    subject_list = list(subjects.values_list('name', flat=True))
    
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
    all_grades = Grade.objects.filter(student=student_profile).select_related('subject', 'subject__teacher__user')
    
    # Calculate current GPA (from all grades)
    average_grade = all_grades.aggregate(Avg('grade'))['grade__avg'] or 0
    current_gpa = (float(average_grade) / 100) * 4.0 if average_grade > 0 else 0.0
    current_gpa = round(current_gpa, 2)
    
    # For cumulative GPA, we'll use the same for now (can be enhanced with historical data)
    cumulative_gpa = current_gpa
    
    # Get subjects with grades
    subjects = []
    if student_profile.section:
        subjects = Subject.objects.filter(section=student_profile.section)
    
    course_grades = []
    total_credits = 0
    grade_distribution = {'A+': 0, 'A': 0, 'A-': 0, 'B+': 0, 'B': 0, 'B-': 0, 'C+': 0, 'C': 0, 'C-': 0, 'D+': 0, 'D': 0, 'F': 0}
    
    for subject in subjects:
        subject_grades = Grade.objects.filter(student=student_profile, subject=subject)
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
            
            teacher_name = subject.teacher.user.get_full_name() if subject.teacher and subject.teacher.user else "TBA"
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
    
    # Get GPA trend by term (semester)
    terms = all_grades.values_list('term', flat=True).distinct().order_by('term')
    semester_gpa = []
    for term in terms:
        term_grades = all_grades.filter(term=term)
        term_avg = term_grades.aggregate(Avg('grade'))['grade__avg'] or 0
        term_gpa = (float(term_avg) / 100) * 4.0 if term_avg > 0 else 0.0
        semester_gpa.append({
            'semester': term,
            'gpa': round(term_gpa, 2)
        })
    
    # If no term data, create placeholder
    if not semester_gpa:
        semester_gpa = [{'semester': 'Current', 'gpa': current_gpa}]
    
    # Determine GPA badge
    if current_gpa >= 3.7:
        gpa_badge = "Top 15%"
        gpa_badge_class = "bg-success-subtle text-success"
    elif current_gpa >= 3.3:
        gpa_badge = "Top 30%"
        gpa_badge_class = "bg-success-subtle text-success"
    elif current_gpa >= 3.0:
        gpa_badge = "Above Average"
        gpa_badge_class = "bg-info-subtle text-info"
    else:
        gpa_badge = "Average"
        gpa_badge_class = "bg-warning-subtle text-warning"
    
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
    
    context = {
        'page_title': 'Grades',
        'page_description': 'View your grades and academic performance.',
        'student_profile': student_profile,
        'current_gpa': current_gpa,
        'cumulative_gpa': cumulative_gpa,
        'total_credits': total_credits,
        'class_rank': class_rank,
        'total_students': total_students,
        'gpa_badge': gpa_badge,
        'gpa_badge_class': gpa_badge_class,
        'course_grades': course_grades,
        'grade_distribution': grade_distribution_data,
        'semester_gpa': semester_gpa,
        'strengths': strengths,
        'growth_opportunities': growth_opportunities,
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
            completed_score = AssessmentScore.objects.filter(student=student_profile, assessment=assessment).first()
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