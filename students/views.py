from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Avg
from core.models import StudentProfile, Grade, Attendance, Subject, Notification

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
    
    # Get grades by subject
    grades_by_subject = {}
    for subject in subjects:
        subject_grades = Grade.objects.filter(student=student_profile, subject=subject)
        if subject_grades.exists():
            grades_by_subject[subject] = {
                'grades': subject_grades.order_by('term'),
                'average': subject_grades.aggregate(Avg('grade'))['grade__avg'] or 0
            }
    
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
        'grades_by_subject': grades_by_subject,
    }
    
    return render(request, 'students/dashboard.html', context)


@login_required
def subjects(request):
    if request.user.role != 'student':
        return redirect('dashboard')
    context = {
        'page_title': 'Subjects',
        'page_description': 'View all your enrolled subjects and course information.'
    }
    return render(request, 'students/subjects.html', context)


@login_required
def attendance(request):
    if request.user.role != 'student':
        return redirect('dashboard')
    context = {
        'page_title': 'Attendance',
        'page_description': 'View your attendance records and history.'
    }
    return render(request, 'students/attendance.html', context)


@login_required
def grades(request):
    if request.user.role != 'student':
        return redirect('dashboard')
    context = {
        'page_title': 'Grades',
        'page_description': 'View your grades and academic performance.'
    }
    return render(request, 'students/grades.html', context)


@login_required
def notifications(request):
    if request.user.role != 'student':
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
    
    context = {
        'page_title': 'Notifications',
        'page_description': 'View and manage all your notifications and alerts.',
        'notifications': all_notifications,
        'unread_count': unread_count,
    }
    return render(request, 'students/notifications.html', context)