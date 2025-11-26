"""
Notification utility functions for attendance and performance notifications.
"""
from django.utils import timezone
from datetime import timedelta
from django.db.models import Avg, Q
from core.models import (
    Notification, StudentProfile, ParentProfile, Attendance, Grade, Subject, TeacherProfile
)


def send_attendance_notification(student, subject, status, date=None):
    """
    Send attendance notification to student and parent (if linked).
    Only sends for 'absent' and 'late' statuses.
    
    Args:
        student: StudentProfile instance
        subject: Subject instance
        status: 'absent' or 'late'
        date: Date of attendance (defaults to today)
    """
    if status not in ['absent', 'late']:
        return  # Only notify for absent/late
    
    if date is None:
        date = timezone.now().date()
    
    notification_type = 'attendance_absent' if status == 'absent' else 'attendance_late'
    status_display = status.capitalize()
    
    # Create notification for student
    student_message = f"You were marked {status_display.lower()} in {subject.code} - {subject.name} on {date.strftime('%B %d, %Y')}."
    
    Notification.objects.create(
        recipient=student.user,
        message=student_message,
        notification_type=notification_type,
        related_student=student,
        related_subject=subject,
        notification_key=f"{notification_type}_student_{student.id}_subject_{subject.id}_date_{date}"
    )
    
    # Create notification for parent if linked
    if student.parent:
        parent_message = f"Your child {student.user.get_full_name() or student.user.username} was marked {status_display.lower()} in {subject.code} - {subject.name} on {date.strftime('%B %d, %Y')}."
        
        Notification.objects.create(
            recipient=student.parent.user,
            message=parent_message,
            notification_type=notification_type,
            related_student=student,
            related_subject=subject,
            notification_key=f"{notification_type}_parent_{student.parent.id}_student_{student.id}_subject_{subject.id}_date_{date}"
        )


def check_and_send_performance_notifications(student, subject=None):
    """
    Check student performance and send notifications if status changes or thresholds are crossed.
    Only sends notifications if there's a change or new threshold breach.
    
    Args:
        student: StudentProfile instance
        subject: Subject instance (optional, if None checks all subjects)
    """
    if subject:
        subjects_to_check = [subject]
    else:
        # Get all subjects for this student
        if student.section:
            subjects_to_check = Subject.objects.filter(section=student.section)
        else:
            return
    
    today = timezone.now().date()
    
    for subj in subjects_to_check:
        # Calculate attendance percentage for this subject
        student_attendance = Attendance.objects.filter(
            student=student,
            subject=subj
        )
        total_attendance = student_attendance.count()
        present_count = student_attendance.filter(status='present').count()
        attendance_percentage = (present_count / total_attendance * 100) if total_attendance > 0 else 0
        
        # Calculate GPA for this subject
        student_grades = Grade.objects.filter(
            student=student,
            subject=subj
        )
        gpa = student_grades.aggregate(Avg('grade'))['grade__avg'] or 0
        
        # Determine current status
        if attendance_percentage >= 80 and gpa >= 80:
            current_status = 'active'
        elif attendance_percentage < 70 or gpa < 70:
            current_status = 'at_risk'
        else:
            current_status = 'active'
        
        # Check for performance status change (at_risk <-> active)
        status_key = f"performance_status_student_{student.id}_subject_{subj.id}"
        last_status_notification = Notification.objects.filter(
            notification_key__startswith=status_key,
            notification_type__in=['performance_at_risk', 'performance_improved']
        ).order_by('-created_at').first()
        
        last_status = None
        if last_status_notification:
            if last_status_notification.notification_type == 'performance_at_risk':
                last_status = 'at_risk'
            elif last_status_notification.notification_type == 'performance_improved':
                last_status = 'active'
        
        # Send notification if status changed
        if last_status != current_status:
            if current_status == 'at_risk':
                # Student became at risk
                reason = []
                if attendance_percentage < 70:
                    reason.append(f"attendance ({attendance_percentage:.1f}%)")
                if gpa < 70:
                    reason.append(f"GPA ({gpa:.2f})")
                
                student_message = f"Performance Alert: You are now marked as 'At Risk' in {subj.code} - {subj.name} due to low {', '.join(reason)}."
                
                Notification.objects.create(
                    recipient=student.user,
                    message=student_message,
                    notification_type='performance_at_risk',
                    related_student=student,
                    related_subject=subj,
                    notification_key=f"{status_key}_{today}"
                )
                
                # Notify parent
                if student.parent:
                    parent_message = f"Performance Alert: {student.user.get_full_name() or student.user.username} is now marked as 'At Risk' in {subj.code} - {subj.name} due to low {', '.join(reason)}."
                    
                    Notification.objects.create(
                        recipient=student.parent.user,
                        message=parent_message,
                        notification_type='performance_at_risk',
                        related_student=student,
                        related_subject=subj,
                        notification_key=f"{status_key}_parent_{student.parent.id}_{today}"
                    )
                
                # Notify teacher
                if subj.teacher and subj.teacher.user:
                    teacher_message = f"Alert: {student.user.get_full_name() or student.user.username} ({student.student_id}) is now marked as 'At Risk' in {subj.code} - {subj.name} due to low {', '.join(reason)}."
                    
                    Notification.objects.create(
                        recipient=subj.teacher.user,
                        message=teacher_message,
                        notification_type='teacher_student_at_risk',
                        related_student=student,
                        related_subject=subj,
                        notification_key=f"{status_key}_teacher_{subj.teacher.id}_{today}"
                    )
            
            elif current_status == 'active' and last_status == 'at_risk':
                # Student improved from at_risk to active
                student_message = f"Great job! Your performance has improved in {subj.code} - {subj.name} and you're back to 'Active' status."
                
                Notification.objects.create(
                    recipient=student.user,
                    message=student_message,
                    notification_type='performance_improved',
                    related_student=student,
                    related_subject=subj,
                    notification_key=f"{status_key}_{today}"
                )
                
                # Notify parent
                if student.parent:
                    parent_message = f"Great news! {student.user.get_full_name() or student.user.username}'s performance has improved in {subj.code} - {subj.name} and is back to 'Active' status."
                    
                    Notification.objects.create(
                        recipient=student.parent.user,
                        message=parent_message,
                        notification_type='performance_improved',
                        related_student=student,
                        related_subject=subj,
                        notification_key=f"{status_key}_parent_{student.parent.id}_{today}"
                    )
        
        # Check for attendance warning (75% threshold - warning before at_risk)
        if attendance_percentage < 75 and total_attendance > 0:
            warning_key = f"performance_warning_attendance_student_{student.id}_subject_{subj.id}"
            # Check if we already sent this warning today
            last_warning = Notification.objects.filter(
                notification_key=warning_key,
                created_at__date=today
            ).first()
            
            if not last_warning:
                student_message = f"Performance Warning: Your attendance in {subj.code} - {subj.name} is below 75% ({attendance_percentage:.1f}%). Please improve your attendance."
                
                Notification.objects.create(
                    recipient=student.user,
                    message=student_message,
                    notification_type='performance_warning_attendance',
                    related_student=student,
                    related_subject=subj,
                    notification_key=warning_key
                )
                
                # Notify parent
                if student.parent:
                    parent_message = f"Performance Warning: {student.user.get_full_name() or student.user.username}'s attendance in {subj.code} - {subj.name} is below 75% ({attendance_percentage:.1f}%)."
                    
                    Notification.objects.create(
                        recipient=student.parent.user,
                        message=parent_message,
                        notification_type='performance_warning_attendance',
                        related_student=student,
                        related_subject=subj,
                        notification_key=f"{warning_key}_parent_{student.parent.id}"
                    )
        
        # Check for GPA warning (75% threshold)
        if gpa > 0 and gpa < 75:
            warning_key = f"performance_warning_gpa_student_{student.id}_subject_{subj.id}"
            # Check if we already sent this warning today
            last_warning = Notification.objects.filter(
                notification_key=warning_key,
                created_at__date=today
            ).first()
            
            if not last_warning:
                student_message = f"Performance Warning: Your GPA in {subj.code} - {subj.name} is below 75% ({gpa:.2f}). Please work on improving your grades."
                
                Notification.objects.create(
                    recipient=student.user,
                    message=student_message,
                    notification_type='performance_warning_gpa',
                    related_student=student,
                    related_subject=subj,
                    notification_key=warning_key
                )
                
                # Notify parent
                if student.parent:
                    parent_message = f"Performance Warning: {student.user.get_full_name() or student.user.username}'s GPA in {subj.code} - {subj.name} is below 75% ({gpa:.2f})."
                    
                    Notification.objects.create(
                        recipient=student.parent.user,
                        message=parent_message,
                        notification_type='performance_warning_gpa',
                        related_student=student,
                        related_subject=subj,
                        notification_key=f"{warning_key}_parent_{student.parent.id}"
                    )


def check_consecutive_absences(student, subject=None):
    """
    Check for consecutive absences and send notification if 3+ consecutive days.
    
    Args:
        student: StudentProfile instance
        subject: Subject instance (optional, if None checks all subjects)
    """
    if subject:
        subjects_to_check = [subject]
    else:
        if student.section:
            subjects_to_check = Subject.objects.filter(section=student.section)
        else:
            return
    
    today = timezone.now().date()
    
    for subj in subjects_to_check:
        # Get last 5 days of attendance records
        recent_attendance = Attendance.objects.filter(
            student=student,
            subject=subj,
            date__lte=today
        ).order_by('-date')[:5]
        
        if len(recent_attendance) < 3:
            continue
        
        # Check for consecutive absences
        consecutive_absent_days = 0
        for att in recent_attendance:
            if att.status == 'absent':
                consecutive_absent_days += 1
            else:
                break
        
        # Send notification if 3+ consecutive absences
        if consecutive_absent_days >= 3:
            notification_key = f"consecutive_absences_student_{student.id}_subject_{subj.id}_days_{consecutive_absent_days}"
            
            # Check if we already sent this notification today
            last_notification = Notification.objects.filter(
                notification_key=notification_key,
                created_at__date=today
            ).first()
            
            if not last_notification:
                student_message = f"Warning: You have been absent for {consecutive_absent_days} consecutive days in {subj.code} - {subj.name}. Please contact your teacher."
                
                Notification.objects.create(
                    recipient=student.user,
                    message=student_message,
                    notification_type='consecutive_absences',
                    related_student=student,
                    related_subject=subj,
                    notification_key=notification_key
                )
                
                # Notify parent
                if student.parent:
                    parent_message = f"Warning: {student.user.get_full_name() or student.user.username} has been absent for {consecutive_absent_days} consecutive days in {subj.code} - {subj.name}. Please contact the school."
                    
                    Notification.objects.create(
                        recipient=student.parent.user,
                        message=parent_message,
                        notification_type='consecutive_absences',
                        related_student=student,
                        related_subject=subj,
                        notification_key=f"{notification_key}_parent_{student.parent.id}"
                    )
                
                # Notify teacher
                if subj.teacher and subj.teacher.user:
                    teacher_message = f"Alert: {student.user.get_full_name() or student.user.username} ({student.student_id}) has been absent for {consecutive_absent_days} consecutive days in {subj.code} - {subj.name}. Please follow up."
                    
                    Notification.objects.create(
                        recipient=subj.teacher.user,
                        message=teacher_message,
                        notification_type='teacher_consecutive_absences',
                        related_student=student,
                        related_subject=subj,
                        notification_key=f"{notification_key}_teacher_{subj.teacher.id}"
                    )

