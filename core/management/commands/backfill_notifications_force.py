"""
Alternative backfill command that forces notification creation for current status.
This version will create notifications for students who are currently at-risk,
even if no status change occurred.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Avg
from core.models import Attendance, Grade, StudentProfile, Subject, Notification, TeacherProfile


class Command(BaseCommand):
    help = 'Force backfill notifications - creates notifications for current status'

    def add_arguments(self, parser):
        parser.add_argument(
            '--attendance-only',
            action='store_true',
            help='Only process attendance notifications',
        )
        parser.add_argument(
            '--performance-only',
            action='store_true',
            help='Only process performance notifications',
        )

    def handle(self, *args, **options):
        attendance_only = options['attendance_only']
        performance_only = options['performance_only']

        self.stdout.write(self.style.SUCCESS('Starting FORCE notification backfill...'))
        self.stdout.write(self.style.WARNING('This will create notifications for current status, not just changes.\n'))
        
        if not performance_only:
            self.stdout.write('\n=== Processing Attendance Notifications ===')
            self.process_attendance_notifications()
        
        if not attendance_only:
            self.stdout.write('\n=== Processing Performance Notifications (Current Status) ===')
            self.process_performance_notifications_force()
            
            self.stdout.write('\n=== Processing Consecutive Absences ===')
            self.process_consecutive_absences_force()
        
        self.stdout.write(self.style.SUCCESS('\n=== Force Notification Backfill Complete ==='))

    def process_attendance_notifications(self):
        """Process all existing attendance records (absent/late only)"""
        attendance_records = Attendance.objects.filter(
            status__in=['absent', 'late']
        ).select_related('student', 'subject', 'student__user', 'student__parent__user')
        
        total = attendance_records.count()
        self.stdout.write(f'Found {total} attendance records (absent/late)')
        
        if total == 0:
            self.stdout.write(self.style.WARNING('  No absent/late records found.'))
            return
        
        created_count = 0
        error_count = 0
        
        for attendance in attendance_records:
            try:
                if not attendance.student.user:
                    continue
                
                notification_type = 'attendance_absent' if attendance.status == 'absent' else 'attendance_late'
                notification_key = f"{notification_type}_student_{attendance.student.id}_subject_{attendance.subject.id}_date_{attendance.date}"
                
                # Check if already exists
                if Notification.objects.filter(notification_key=notification_key).exists():
                    continue
                
                status_display = attendance.status.capitalize()
                student_message = f"You were marked {status_display.lower()} in {attendance.subject.code} - {attendance.subject.name} on {attendance.date.strftime('%B %d, %Y')}."
                
                Notification.objects.create(
                    recipient=attendance.student.user,
                    message=student_message,
                    notification_type=notification_type,
                    related_student=attendance.student,
                    related_subject=attendance.subject,
                    notification_key=notification_key
                )
                
                # Create for parent
                if attendance.student.parent and attendance.student.parent.user:
                    parent_key = f"{notification_key}_parent_{attendance.student.parent.id}"
                    if not Notification.objects.filter(notification_key=parent_key).exists():
                        parent_message = f"Your child {attendance.student.user.get_full_name() or attendance.student.user.username} was marked {status_display.lower()} in {attendance.subject.code} - {attendance.subject.name} on {attendance.date.strftime('%B %d, %Y')}."
                        
                        Notification.objects.create(
                            recipient=attendance.student.parent.user,
                            message=parent_message,
                            notification_type=notification_type,
                            related_student=attendance.student,
                            related_subject=attendance.subject,
                            notification_key=parent_key
                        )
                
                created_count += 1
                
                if created_count % 50 == 0:
                    self.stdout.write(f'  Created {created_count} notifications...')
            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(f'  Error: {str(e)}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(f'Created {created_count} attendance notifications' + (f', {error_count} errors' if error_count > 0 else ''))
        )

    def process_performance_notifications_force(self):
        """Force create performance notifications for current status"""
        students = StudentProfile.objects.select_related('user', 'parent__user', 'section')
        
        total = students.count()
        self.stdout.write(f'Found {total} students to check')
        
        created_count = 0
        processed_count = 0
        
        for student in students:
            try:
                if not student.user or not student.section:
                    continue
                
                subjects = Subject.objects.filter(section=student.section)
                for subject in subjects:
                    # Calculate current status
                    student_attendance = Attendance.objects.filter(
                        student=student,
                        subject=subject
                    )
                    total_attendance = student_attendance.count()
                    if total_attendance == 0:
                        continue
                    
                    present_count = student_attendance.filter(status='present').count()
                    attendance_percentage = (present_count / total_attendance * 100)
                    
                    student_grades = Grade.objects.filter(
                        student=student,
                        subject=subject
                    )
                    gpa = student_grades.aggregate(Avg('grade'))['grade__avg'] or 0
                    
                    # Determine current status
                    if attendance_percentage >= 80 and gpa >= 80:
                        current_status = 'active'
                    elif attendance_percentage < 70 or gpa < 70:
                        current_status = 'at_risk'
                    else:
                        current_status = 'active'
                    
                    # Create notification if at_risk and no notification exists
                    if current_status == 'at_risk':
                        status_key = f"performance_status_student_{student.id}_subject_{subject.id}"
                        if not Notification.objects.filter(
                            notification_key__startswith=status_key,
                            notification_type='performance_at_risk'
                        ).exists():
                            reason = []
                            if attendance_percentage < 70:
                                reason.append(f"attendance ({attendance_percentage:.1f}%)")
                            if gpa < 70:
                                reason.append(f"GPA ({gpa:.2f})")
                            
                            student_message = f"Performance Alert: You are marked as 'At Risk' in {subject.code} - {subject.name} due to low {', '.join(reason)}."
                            
                            Notification.objects.create(
                                recipient=student.user,
                                message=student_message,
                                notification_type='performance_at_risk',
                                related_student=student,
                                related_subject=subject,
                                notification_key=f"{status_key}_{timezone.now().date()}"
                            )
                            
                            if student.parent and student.parent.user:
                                parent_message = f"Performance Alert: {student.user.get_full_name() or student.user.username} is marked as 'At Risk' in {subject.code} - {subject.name} due to low {', '.join(reason)}."
                                
                            Notification.objects.create(
                                recipient=student.parent.user,
                                message=parent_message,
                                notification_type='performance_at_risk',
                                related_student=student,
                                related_subject=subject,
                                notification_key=f"{status_key}_parent_{student.parent.id}_{timezone.now().date()}"
                            )
                            
                            # Notify teacher
                            if subject.teacher and subject.teacher.user:
                                teacher_message = f"Alert: {student.user.get_full_name() or student.user.username} ({student.student_id}) is marked as 'At Risk' in {subject.code} - {subject.name} due to low {', '.join(reason)}."
                                Notification.objects.create(
                                    recipient=subject.teacher.user,
                                    message=teacher_message,
                                    notification_type='teacher_student_at_risk',
                                    related_student=student,
                                    related_subject=subject,
                                    notification_key=f"{status_key}_teacher_{subject.teacher.id}_{timezone.now().date()}"
                                )
                            
                            created_count += 1
                    
                    # Check for warnings
                    if attendance_percentage < 75:
                        warning_key = f"performance_warning_attendance_student_{student.id}_subject_{subject.id}"
                        if not Notification.objects.filter(notification_key=warning_key).exists():
                            student_message = f"Performance Warning: Your attendance in {subject.code} - {subject.name} is below 75% ({attendance_percentage:.1f}%)."
                            Notification.objects.create(
                                recipient=student.user,
                                message=student_message,
                                notification_type='performance_warning_attendance',
                                related_student=student,
                                related_subject=subject,
                                notification_key=warning_key
                            )
                            created_count += 1
                    
                    if gpa > 0 and gpa < 75:
                        warning_key = f"performance_warning_gpa_student_{student.id}_subject_{subject.id}"
                        if not Notification.objects.filter(notification_key=warning_key).exists():
                            student_message = f"Performance Warning: Your GPA in {subject.code} - {subject.name} is below 75% ({gpa:.2f})."
                            Notification.objects.create(
                                recipient=student.user,
                                message=student_message,
                                notification_type='performance_warning_gpa',
                                related_student=student,
                                related_subject=subject,
                                notification_key=warning_key
                            )
                            created_count += 1
                
                processed_count += 1
                if processed_count % 20 == 0:
                    self.stdout.write(f'  Processed {processed_count} students, created {created_count} notifications...')
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'  Error processing student {student.id}: {str(e)}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(f'Processed {processed_count} students, created {created_count} performance notifications')
        )

    def process_consecutive_absences_force(self):
        """Check for consecutive absences"""
        students = StudentProfile.objects.select_related('user', 'parent__user', 'section')
        
        created_count = 0
        for student in students:
            try:
                if not student.user or not student.section:
                    continue
                
                subjects = Subject.objects.filter(section=student.section)
                for subject in subjects:
                    recent_attendance = Attendance.objects.filter(
                        student=student,
                        subject=subject,
                        status='absent'
                    ).order_by('-date')[:5]
                    
                    if len(recent_attendance) >= 3:
                        # Check if they're consecutive
                        dates = [att.date for att in recent_attendance[:3]]
                        if all((dates[i] - dates[i+1]).days == 1 for i in range(len(dates)-1)):
                            notification_key = f"consecutive_absences_student_{student.id}_subject_{subject.id}_days_3"
                            if not Notification.objects.filter(notification_key=notification_key).exists():
                                student_message = f"Warning: You have been absent for 3 consecutive days in {subject.code} - {subject.name}."
                                Notification.objects.create(
                                    recipient=student.user,
                                    message=student_message,
                                    notification_type='consecutive_absences',
                                    related_student=student,
                                    related_subject=subject,
                                    notification_key=notification_key
                                )
                                
                                # Notify teacher
                                if subject.teacher and subject.teacher.user:
                                    teacher_message = f"Alert: {student.user.get_full_name() or student.user.username} ({student.student_id}) has been absent for 3 consecutive days in {subject.code} - {subject.name}. Please follow up."
                                    Notification.objects.create(
                                        recipient=subject.teacher.user,
                                        message=teacher_message,
                                        notification_type='teacher_consecutive_absences',
                                        related_student=student,
                                        related_subject=subject,
                                        notification_key=f"{notification_key}_teacher_{subject.teacher.id}"
                                    )
                                
                                created_count += 1
            except Exception as e:
                pass
        
        self.stdout.write(
            self.style.SUCCESS(f'Created {created_count} consecutive absence notifications')
        )

