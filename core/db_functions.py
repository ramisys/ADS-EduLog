"""
Database Functions (Stored Procedure Equivalents)
These functions act like stored procedures and can be called from views.
All functions use Django ORM to prevent SQL injection.
"""
from django.db import transaction
from django.db.models import Avg, Count, Q, Sum, F
from django.utils import timezone
from datetime import timedelta, date
from decimal import Decimal
from core.models import (
    StudentProfile, Grade, Attendance, Subject, Assessment, AssessmentScore,
    CategoryWeights, Notification, TeacherProfile
)


@transaction.atomic
def calculate_student_gpa(student_id, term=None):
    """
    Calculate GPA for a student (acts like a stored procedure).
    Uses transaction to ensure data consistency.
    
    Args:
        student_id: StudentProfile ID
        term: 'Midterm', 'Final', or None for all terms
    
    Returns:
        dict with GPA and grade details
    """
    try:
        student = StudentProfile.objects.select_for_update().get(id=student_id)
        
        grade_query = Grade.objects.filter(student=student)
        if term:
            grade_query = grade_query.filter(term=term)
        
        grades = grade_query.select_related('subject')
        
        if not grades.exists():
            return {
                'gpa': 0.0,
                'average_grade': 0.0,
                'grade_count': 0,
                'term': term or 'All Terms'
            }
        
        avg_grade = grades.aggregate(Avg('grade'))['grade__avg'] or 0
        gpa = (float(avg_grade) / 100) * 4.0
        
        return {
            'gpa': round(gpa, 2),
            'average_grade': round(float(avg_grade), 2),
            'grade_count': grades.count(),
            'term': term or 'All Terms',
            'grades': list(grades.values('subject__code', 'subject__name', 'grade', 'term'))
        }
    except StudentProfile.DoesNotExist:
        return {'error': 'Student not found'}
    except Exception as e:
        return {'error': str(e)}


@transaction.atomic
def calculate_attendance_rate(student_id, subject_id=None, start_date=None, end_date=None):
    """
    Calculate attendance rate for a student (acts like a stored procedure).
    Uses transaction and proper date filtering.
    
    Args:
        student_id: StudentProfile ID
        subject_id: Optional Subject ID to filter by subject
        start_date: Optional start date
        end_date: Optional end date
    
    Returns:
        dict with attendance statistics
    """
    try:
        student = StudentProfile.objects.select_for_update().get(id=student_id)
        
        attendance_query = Attendance.objects.filter(student=student)
        
        if subject_id:
            attendance_query = attendance_query.filter(subject_id=subject_id)
        
        if start_date:
            attendance_query = attendance_query.filter(date__gte=start_date)
        
        if end_date:
            attendance_query = attendance_query.filter(date__lte=end_date)
        
        total = attendance_query.count()
        
        if total == 0:
            return {
                'attendance_rate': 0.0,
                'present_count': 0,
                'absent_count': 0,
                'late_count': 0,
                'total_count': 0
            }
        
        present_count = attendance_query.filter(status='present').count()
        absent_count = attendance_query.filter(status='absent').count()
        late_count = attendance_query.filter(status='late').count()
        
        attendance_rate = (present_count / total) * 100
        
        return {
            'attendance_rate': round(attendance_rate, 2),
            'present_count': present_count,
            'absent_count': absent_count,
            'late_count': late_count,
            'total_count': total
        }
    except StudentProfile.DoesNotExist:
        return {'error': 'Student not found'}
    except Exception as e:
        return {'error': str(e)}


@transaction.atomic
def get_student_performance_summary(student_id):
    """
    Get comprehensive performance summary for a student (acts like a stored procedure).
    Uses subqueries and aggregations for efficient data retrieval.
    
    Args:
        student_id: StudentProfile ID
    
    Returns:
        dict with comprehensive performance data
    """
    try:
        student = StudentProfile.objects.select_related('user', 'section').get(id=student_id)
        
        # Get all subjects for the student's section
        subjects = Subject.objects.filter(section=student.section).select_related('teacher', 'teacher__user')
        
        # Calculate overall GPA
        grades = Grade.objects.filter(student=student)
        overall_avg = grades.aggregate(Avg('grade'))['grade__avg'] or 0
        overall_gpa = (float(overall_avg) / 100) * 4.0 if overall_avg > 0 else 0.0
        
        # Calculate overall attendance
        attendance = Attendance.objects.filter(student=student)
        total_attendance = attendance.count()
        present_count = attendance.filter(status='present').count()
        attendance_rate = (present_count / total_attendance * 100) if total_attendance > 0 else 0
        
        # Get subject-wise performance
        subject_performance = []
        for subject in subjects:
            subject_grades = grades.filter(subject=subject)
            subject_attendance = attendance.filter(subject=subject)
            
            subject_avg = subject_grades.aggregate(Avg('grade'))['grade__avg'] or 0
            subject_attendance_count = subject_attendance.count()
            subject_present = subject_attendance.filter(status='present').count()
            subject_attendance_rate = (subject_present / subject_attendance_count * 100) if subject_attendance_count > 0 else 0
            
            subject_performance.append({
                'subject_id': subject.id,
                'subject_code': subject.code,
                'subject_name': subject.name,
                'average_grade': round(float(subject_avg), 2),
                'attendance_rate': round(subject_attendance_rate, 2),
                'grade_count': subject_grades.count(),
                'attendance_count': subject_attendance_count
            })
        
        return {
            'student_id': student.student_id,
            'student_name': student.user.get_full_name(),
            'overall_gpa': round(overall_gpa, 2),
            'overall_average_grade': round(float(overall_avg), 2),
            'overall_attendance_rate': round(attendance_rate, 2),
            'total_subjects': subjects.count(),
            'subject_performance': subject_performance
        }
    except StudentProfile.DoesNotExist:
        return {'error': 'Student not found'}
    except Exception as e:
        return {'error': str(e)}


@transaction.atomic
def get_teacher_class_statistics(teacher_id, subject_id=None):
    """
    Get statistics for a teacher's class (acts like a stored procedure).
    Uses complex aggregations and subqueries.
    
    Args:
        teacher_id: TeacherProfile ID
        subject_id: Optional Subject ID to filter
    
    Returns:
        dict with class statistics
    """
    try:
        teacher = TeacherProfile.objects.select_related('user').get(id=teacher_id)
        
        subjects_query = Subject.objects.filter(teacher=teacher)
        if subject_id:
            subjects_query = subjects_query.filter(id=subject_id)
        
        subjects = subjects_query.select_related('section')
        
        statistics = []
        for subject in subjects:
            # Get students in this subject's section
            students = StudentProfile.objects.filter(section=subject.section)
            
            # Calculate average grade for this subject
            grades = Grade.objects.filter(subject=subject, student__in=students)
            avg_grade = grades.aggregate(Avg('grade'))['grade__avg'] or 0
            
            # Calculate attendance statistics
            attendance = Attendance.objects.filter(subject=subject, student__in=students)
            total_attendance = attendance.count()
            present_count = attendance.filter(status='present').count()
            attendance_rate = (present_count / total_attendance * 100) if total_attendance > 0 else 0
            
            # Count students at risk (GPA < 75 or attendance < 70%)
            at_risk_count = 0
            for student in students:
                student_grades = grades.filter(student=student)
                student_attendance = attendance.filter(student=student)
                
                if student_grades.exists():
                    student_avg = student_grades.aggregate(Avg('grade'))['grade__avg'] or 0
                else:
                    student_avg = 0
                
                student_attendance_count = student_attendance.count()
                student_present = student_attendance.filter(status='present').count()
                student_attendance_rate = (student_present / student_attendance_count * 100) if student_attendance_count > 0 else 0
                
                if student_avg < 75 or student_attendance_rate < 70:
                    at_risk_count += 1
            
            statistics.append({
                'subject_id': subject.id,
                'subject_code': subject.code,
                'subject_name': subject.name,
                'section_name': subject.section.name if subject.section else 'N/A',
                'student_count': students.count(),
                'average_grade': round(float(avg_grade), 2),
                'attendance_rate': round(attendance_rate, 2),
                'at_risk_students': at_risk_count
            })
        
        return {
            'teacher_id': teacher.teacher_id,
            'teacher_name': teacher.user.get_full_name(),
            'statistics': statistics
        }
    except TeacherProfile.DoesNotExist:
        return {'error': 'Teacher not found'}
    except Exception as e:
        return {'error': str(e)}


def check_consecutive_absences_stored(student_id, subject_id, threshold=3):
    """
    Check for consecutive absences (acts like a stored procedure).
    Uses window functions concept via Django ORM.
    
    Args:
        student_id: StudentProfile ID
        subject_id: Subject ID
        threshold: Number of consecutive absences to trigger alert
    
    Returns:
        dict with consecutive absence information
    """
    try:
        student = StudentProfile.objects.get(id=student_id)
        subject = Subject.objects.get(id=subject_id)
        
        # Get recent attendance records ordered by date
        attendance_records = Attendance.objects.filter(
            student=student,
            subject=subject,
            status='absent'
        ).order_by('-date')[:threshold]
        
        if attendance_records.count() < threshold:
            return {
                'has_consecutive_absences': False,
                'consecutive_count': attendance_records.count()
            }
        
        # Check if dates are consecutive
        dates = [record.date for record in attendance_records]
        dates.sort()
        
        consecutive = True
        for i in range(len(dates) - 1):
            if (dates[i+1] - dates[i]).days != 1:
                consecutive = False
                break
        
        return {
            'has_consecutive_absences': consecutive,
            'consecutive_count': threshold if consecutive else attendance_records.count(),
            'dates': [d.isoformat() for d in dates] if consecutive else []
        }
    except (StudentProfile.DoesNotExist, Subject.DoesNotExist):
        return {'error': 'Student or Subject not found'}
    except Exception as e:
        return {'error': str(e)}

