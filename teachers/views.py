from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q
from django.utils import timezone
from datetime import timedelta
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
    
    # Calculate weekly attendance data (last 5 days)
    today = timezone.now().date()
    weekly_attendance_data = []
    weekly_attendance_labels = []
    
    for i in range(4, -1, -1):  # Last 5 days (4 days ago to today)
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
        else:
            weekly_attendance_labels.append(date.strftime('%a %d'))
    
    # Calculate subject performance data (average grades per subject)
    subject_performance_data = []
    subject_performance_labels = []
    
    for subject in subjects:
        subject_grades = Grade.objects.filter(subject=subject)
        if subject_grades.exists():
            subject_avg = subject_grades.aggregate(Avg('grade'))['grade__avg'] or 0
            subject_performance_data.append(round(subject_avg, 2))
            subject_performance_labels.append(subject.code)
    
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
    for subject in subjects:
        student_count = StudentProfile.objects.filter(section=subject.section).count()
        subjects_with_counts.append({
            'subject': subject,
            'student_count': student_count,
        })
    
    context = {
        'subjects': subjects_with_counts,
        'teacher_profile': teacher_profile,
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
    
    # Get sections where teacher is adviser or teaches subjects
    advised_section_ids = ClassSection.objects.filter(adviser=teacher_profile).values_list('id', flat=True)
    sections_with_subjects_ids = ClassSection.objects.filter(
        subject__teacher=teacher_profile
    ).values_list('id', flat=True).distinct()
    all_section_ids = set(list(advised_section_ids) + list(sections_with_subjects_ids))
    
    # Get all students in these sections
    all_students = StudentProfile.objects.filter(section__id__in=all_section_ids).select_related('user', 'section').order_by('section__name', 'user__last_name', 'user__first_name')
    
    # Get sections with their students
    sections_data = []
    total_students_count = 0
    active_students_count = 0
    at_risk_count = 0
    
    for section_id in all_section_ids:
        section = ClassSection.objects.get(id=section_id)
        section_students = all_students.filter(section=section)
        student_count = section_students.count()
        if student_count == 0:
            continue
        
        total_students_count += student_count
        
        # Calculate statistics for each student in this section
        students_data = []
        section_attendance_sum = 0
        section_grades_sum = 0
        section_grades_count = 0
        
        for student in section_students:
            # Calculate attendance percentage
            student_attendance = Attendance.objects.filter(
                student=student,
                subject__teacher=teacher_profile
            )
            total_attendance = student_attendance.count()
            present_count = student_attendance.filter(status='present').count()
            attendance_percentage = (present_count / total_attendance * 100) if total_attendance > 0 else 0
            section_attendance_sum += attendance_percentage
            
            # Calculate GPA (average grade)
            student_grades = Grade.objects.filter(
                student=student,
                subject__teacher=teacher_profile
            )
            if student_grades.exists():
                gpa = student_grades.aggregate(Avg('grade'))['grade__avg'] or 0
                section_grades_sum += gpa
                section_grades_count += 1
            else:
                gpa = 0
            
            # Determine status
            if attendance_percentage >= 80 and gpa >= 80:
                status = 'active'
                active_students_count += 1
            elif attendance_percentage < 70 or gpa < 70:
                status = 'at_risk'
                at_risk_count += 1
            else:
                status = 'active'
                active_students_count += 1
            
            students_data.append({
                'student': student,
                'attendance_percentage': round(attendance_percentage, 1),
                'gpa': round(gpa, 2),
                'status': status,
            })
        
        # Calculate section averages
        avg_attendance = (section_attendance_sum / student_count) if student_count > 0 else 0
        avg_gpa = (section_grades_sum / section_grades_count) if section_grades_count > 0 else 0
        
        sections_data.append({
            'section': section,
            'students': students_data,
            'student_count': student_count,
            'avg_attendance': round(avg_attendance, 1),
            'avg_gpa': round(avg_gpa, 2),
        })
    
    # Sort sections by name
    sections_data.sort(key=lambda x: x['section'].name)
    
    context = {
        'sections': sections_data,
        'total_students': total_students_count,
        'active_students': active_students_count,
        'at_risk_students': at_risk_count,
        'total_sections': len(sections_data),
    }
    return render(request, 'teachers/students.html', context)

@login_required
def attendance(request):
    if request.user.role != 'teacher':
        return redirect('dashboard')
    context = {
        'page_title': 'Attendance',
        'page_description': 'Track and manage student attendance records.'
    }
    return render(request, 'teachers/attendance.html', context)

@login_required
def grades(request):
    if request.user.role != 'teacher':
        return redirect('dashboard')
    context = {
        'page_title': 'Grades',
        'page_description': 'View and manage student grades and assessments.'
    }
    return render(request, 'teachers/grades.html', context)

@login_required
def reports(request):
    if request.user.role != 'teacher':
        return redirect('dashboard')
    context = {
        'page_title': 'Reports',
        'page_description': 'Generate and view comprehensive reports and analytics.'
    }
    return render(request, 'teachers/reports.html', context)

@login_required
def notifications(request):
    if request.user.role != 'teacher':
        return redirect('dashboard')
    context = {
        'page_title': 'Notifications',
        'page_description': 'View and manage all your notifications and alerts.'
    }
    return render(request, 'teachers/notifications.html', context)
    