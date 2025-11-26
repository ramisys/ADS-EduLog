from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Avg
from core.models import ParentProfile, StudentProfile, Grade, Attendance, Notification

@login_required
def dashboard(request):
    # Ensure user is a parent
    if request.user.role != 'parent':
        return redirect('dashboard')
    
    try:
        parent_profile = ParentProfile.objects.get(user=request.user)
    except ParentProfile.DoesNotExist:
        return redirect('dashboard')
    
    # Get all children (students) of this parent
    children = StudentProfile.objects.filter(parent=parent_profile)
    
    # Get grades for all children
    children_grades = Grade.objects.filter(student__in=children).select_related('student', 'subject').order_by('-id')[:10]
    
    # Get attendance for all children
    children_attendance = Attendance.objects.filter(student__in=children).select_related('student', 'subject').order_by('-date')[:10]
    
    # Get unread notifications
    notifications = Notification.objects.filter(recipient=request.user, is_read=False).order_by('-created_at')[:5]
    
    # Statistics for each child
    children_stats = []
    for child in children:
        child_grades = Grade.objects.filter(student=child)
        child_avg = child_grades.aggregate(Avg('grade'))['grade__avg'] or 0
        
        child_attendance = Attendance.objects.filter(student=child)
        present_count = child_attendance.filter(status='present').count()
        absent_count = child_attendance.filter(status='absent').count()
        late_count = child_attendance.filter(status='late').count()
        total_attendance = child_attendance.count()
        attendance_percentage = (present_count / total_attendance * 100) if total_attendance > 0 else 0
        
        children_stats.append({
            'child': child,
            'average_grade': round(child_avg, 2),
            'grades_count': child_grades.count(),
            'present_count': present_count,
            'absent_count': absent_count,
            'late_count': late_count,
            'attendance_percentage': round(attendance_percentage, 1),
            'total_attendance': total_attendance,
        })
    
    # Overall statistics
    all_grades = Grade.objects.filter(student__in=children)
    overall_avg = all_grades.aggregate(Avg('grade'))['grade__avg'] or 0
    
    all_attendance = Attendance.objects.filter(student__in=children)
    total_present = all_attendance.filter(status='present').count()
    total_absent = all_attendance.filter(status='absent').count()
    total_late = all_attendance.filter(status='late').count()
    
    context = {
        'parent_profile': parent_profile,
        'children': children,
        'children_grades': children_grades,
        'children_attendance': children_attendance,
        'notifications': notifications,
        'children_stats': children_stats,
        'overall_avg': round(overall_avg, 2),
        'total_present': total_present,
        'total_absent': total_absent,
        'total_late': total_late,
    }
    
    return render(request, 'parents/dashboard.html', context)


@login_required
def child_subjects(request):
    if request.user.role != 'parent':
        return redirect('dashboard')
    context = {
        'page_title': 'Child Subjects',
        'page_description': 'View all subjects your children are enrolled in.'
    }
    return render(request, 'parents/child_subjects.html', context)


@login_required
def attendance(request):
    if request.user.role != 'parent':
        return redirect('dashboard')
    context = {
        'page_title': 'Attendance',
        'page_description': 'View attendance records for all your children.'
    }
    return render(request, 'parents/attendance.html', context)


@login_required
def grades(request):
    if request.user.role != 'parent':
        return redirect('dashboard')
    context = {
        'page_title': 'Grades',
        'page_description': 'View grades and academic performance for all your children.'
    }
    return render(request, 'parents/grades.html', context)


@login_required
def reports(request):
    if request.user.role != 'parent':
        return redirect('dashboard')
    context = {
        'page_title': 'Performance Reports',
        'page_description': 'Generate and view comprehensive performance reports for your children.'
    }
    return render(request, 'parents/reports.html', context)


@login_required
def notifications(request):
    if request.user.role != 'parent':
        return redirect('dashboard')
    
    try:
        parent_profile = ParentProfile.objects.get(user=request.user)
    except ParentProfile.DoesNotExist:
        return redirect('dashboard')
    
    # Get all notifications for the parent
    all_notifications = Notification.objects.filter(recipient=request.user).order_by('-created_at')
    
    # Handle mark as read
    if request.method == 'POST' and 'mark_read' in request.POST:
        notification_id = request.POST.get('mark_read')
        try:
            notification = Notification.objects.get(id=notification_id, recipient=request.user)
            notification.is_read = True
            notification.save()
            return redirect('parents:notifications')
        except Notification.DoesNotExist:
            pass
    
    # Handle mark all as read
    if request.method == 'POST' and 'mark_all_read' in request.POST:
        Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
        return redirect('parents:notifications')
    
    unread_count = all_notifications.filter(is_read=False).count()
    
    context = {
        'page_title': 'Notifications',
        'page_description': 'View and manage all your notifications and alerts.',
        'notifications': all_notifications,
        'unread_count': unread_count,
    }
    return render(request, 'parents/notifications.html', context)