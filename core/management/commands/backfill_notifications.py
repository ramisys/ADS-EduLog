"""
Management command to backfill notifications for existing attendance and grade records.
This command will:
1. Check all existing attendance records (absent/late only) and create notifications
2. Check all existing grades and send performance notifications based on current status
3. Check for consecutive absences and send notifications

Usage:
    python manage.py backfill_notifications
    python manage.py backfill_notifications --attendance-only
    python manage.py backfill_notifications --performance-only
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Q
from core.models import Attendance, Grade, StudentProfile, Subject, Notification
from core.notifications import (
    send_attendance_notification,
    check_and_send_performance_notifications,
    check_consecutive_absences
)


class Command(BaseCommand):
    help = 'Backfill notifications for existing attendance and grade records'

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
        parser.add_argument(
            '--skip-existing',
            action='store_true',
            help='Skip creating notifications if they already exist (based on notification_key)',
        )

    def handle(self, *args, **options):
        attendance_only = options['attendance_only']
        performance_only = options['performance_only']
        skip_existing = options['skip_existing']

        self.stdout.write(self.style.SUCCESS('Starting notification backfill...'))
        
        if not performance_only:
            self.stdout.write('\n=== Processing Attendance Notifications ===')
            self.process_attendance_notifications(skip_existing)
        
        if not attendance_only:
            self.stdout.write('\n=== Processing Performance Notifications ===')
            self.process_performance_notifications(skip_existing)
            
            self.stdout.write('\n=== Processing Consecutive Absences ===')
            self.process_consecutive_absences(skip_existing)
        
        self.stdout.write(self.style.SUCCESS('\n=== Notification Backfill Complete ==='))

    def process_attendance_notifications(self, skip_existing):
        """Process all existing attendance records (absent/late only)"""
        # Get all attendance records that are absent or late
        attendance_records = Attendance.objects.filter(
            status__in=['absent', 'late']
        ).select_related('student', 'subject', 'student__user', 'student__parent__user')
        
        total = attendance_records.count()
        self.stdout.write(f'Found {total} attendance records (absent/late)')
        
        if total == 0:
            self.stdout.write(self.style.WARNING('  No absent/late records found. Nothing to process.'))
            return
        
        created_count = 0
        skipped_count = 0
        error_count = 0
        
        for attendance in attendance_records:
            try:
                if skip_existing:
                    # Check if notification already exists
                    notification_key = f"{'attendance_absent' if attendance.status == 'absent' else 'attendance_late'}_student_{attendance.student.id}_subject_{attendance.subject.id}_date_{attendance.date}"
                    if Notification.objects.filter(notification_key=notification_key).exists():
                        skipped_count += 1
                        continue
                
                # Check if student has a user
                if not attendance.student.user:
                    self.stdout.write(
                        self.style.WARNING(f'  Skipping attendance {attendance.id}: Student has no user account')
                    )
                    continue
                
                send_attendance_notification(
                    attendance.student,
                    attendance.subject,
                    attendance.status,
                    attendance.date
                )
                created_count += 1
                
                if created_count % 50 == 0:
                    self.stdout.write(f'  Processed {created_count} attendance notifications...')
            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(f'  Error processing attendance {attendance.id}: {str(e)}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Created {created_count} attendance notifications'
                + (f', skipped {skipped_count} existing' if skip_existing else '')
                + (f', {error_count} errors' if error_count > 0 else '')
            )
        )

    def process_performance_notifications(self, skip_existing):
        """
        Process all students and check their performance status.
        Note: This will only send notifications if there's a status change or threshold breach.
        For existing data, it will check current status and send appropriate notifications.
        """
        students = StudentProfile.objects.select_related('user', 'parent__user', 'section')
        
        total = students.count()
        self.stdout.write(f'Found {total} students to check')
        self.stdout.write('Note: Performance notifications are only sent for status changes or threshold breaches.')
        
        processed_count = 0
        notification_count = 0
        error_count = 0
        
        for student in students:
            try:
                # Check if student has a user
                if not student.user:
                    self.stdout.write(
                        self.style.WARNING(f'  Skipping student {student.id}: No user account')
                    )
                    continue
                
                # Check performance for all subjects this student is enrolled in
                if student.section:
                    subjects = Subject.objects.filter(section=student.section)
                    for subject in subjects:
                        # Check if student has any grades or attendance for this subject
                        has_grades = Grade.objects.filter(student=student, subject=subject).exists()
                        has_attendance = Attendance.objects.filter(student=student, subject=subject).exists()
                        
                        if has_grades or has_attendance:
                            # Check and send performance notifications
                            # This function handles deduplication internally and only sends
                            # notifications if there's a status change or threshold breach
                            try:
                                check_and_send_performance_notifications(student, subject)
                                notification_count += 1
                            except Exception as e:
                                error_count += 1
                                self.stdout.write(
                                    self.style.ERROR(f'  Error checking performance for student {student.id}, subject {subject.id}: {str(e)}')
                                )
                else:
                    self.stdout.write(
                        self.style.WARNING(f'  Student {student.id} has no section assigned')
                    )
                
                processed_count += 1
                
                if processed_count % 20 == 0:
                    self.stdout.write(f'  Processed {processed_count} students...')
            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(f'  Error processing student {student.id}: {str(e)}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Processed {processed_count} students, checked {notification_count} subject-student combinations'
                + (f', {error_count} errors' if error_count > 0 else '')
            )
        )

    def process_consecutive_absences(self, skip_existing):
        """Check all students for consecutive absences"""
        students = StudentProfile.objects.select_related('user', 'parent__user', 'section')
        
        total = students.count()
        self.stdout.write(f'Found {total} students to check for consecutive absences')
        
        processed_count = 0
        notification_count = 0
        
        for student in students:
            try:
                if student.section:
                    subjects = Subject.objects.filter(section=student.section)
                    for subject in subjects:
                        # Check for consecutive absences
                        # This function handles deduplication internally
                        check_consecutive_absences(student, subject)
                        notification_count += 1
                
                processed_count += 1
                
                if processed_count % 20 == 0:
                    self.stdout.write(f'  Processed {processed_count} students...')
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error processing student {student.id}: {str(e)}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Processed {processed_count} students, checked {notification_count} subject-student combinations'
            )
        )

