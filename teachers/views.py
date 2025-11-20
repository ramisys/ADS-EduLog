from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Avg
from core.models import TeacherProfile, Subject, ClassSection, StudentProfile, Attendance, Grade, Notification

@login_required
def dashboard(request):
    # Ensure user is a teacher
    if request.user.role != 'teacher':
        return redirect('dashboard')
    
    try:
        teacher_profile = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        return redirect('dashboard')
    
    # Get teacher's subjects
    subjects = Subject.objects.filter(teacher=teacher_profile).select_related('section')
    
    # Get classes/sections the teacher is advising
    advised_sections = ClassSection.objects.filter(adviser=teacher_profile)
    
    # Get all students in teacher's sections
    student_count = StudentProfile.objects.filter(section__in=subjects.values_list('section', flat=True).distinct()).count()
    
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
    
    # Get grades statistics
    total_grades = Grade.objects.filter(subject__teacher=teacher_profile)
    average_grade = total_grades.aggregate(Avg('grade'))['grade__avg'] or 0
    grades_count = total_grades.count()
    
    # Get unread notifications
    notifications = Notification.objects.filter(recipient=request.user, is_read=False).order_by('-created_at')[:5]
    unread_notifications_count = Notification.objects.filter(recipient=request.user, is_read=False).count()
    
    # Calculate grade distribution
    # Get all students in teacher's sections and their average grades
    students_in_sections = StudentProfile.objects.filter(section__in=subjects.values_list('section', flat=True).distinct())
    excellent_count = 0
    good_count = 0
    average_count = 0
    poor_count = 0
    
    for student in students_in_sections:
        student_grades = Grade.objects.filter(student=student, subject__teacher=teacher_profile)
        if student_grades.exists():
            student_avg = student_grades.aggregate(Avg('grade'))['grade__avg'] or 0
            if student_avg >= 90:
                excellent_count += 1
            elif student_avg >= 80:
                good_count += 1
            elif student_avg >= 70:
                average_count += 1
            else:
                poor_count += 1
    
    # Get subject statistics
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
    }
    
    return render(request, 'teachers/dashboard.html', context)