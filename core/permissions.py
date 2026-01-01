"""
Security and Permission Decorators
Provides role-based access control and input validation to prevent SQL injection
"""
from functools import wraps
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import redirect
from django.contrib import messages
import re


def role_required(*allowed_roles):
    """
    Decorator to ensure user has one of the required roles.
    Prevents unauthorized access to views.
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                messages.error(request, 'Please login to access this page.')
                return redirect('login')
            
            if request.user.role not in allowed_roles:
                messages.error(request, 'You do not have permission to access this page.')
                return redirect('dashboard')
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def validate_input(input_value, input_type='string', max_length=None, allow_none=False):
    """
    Validate and sanitize user input to prevent SQL injection and XSS attacks.
    
    Args:
        input_value: The input to validate
        input_type: Type of input ('string', 'integer', 'decimal', 'email', 'date')
        max_length: Maximum length for string inputs
        allow_none: Whether None values are allowed
    
    Returns:
        Validated and sanitized value or None if invalid
    """
    if input_value is None:
        return None if allow_none else False
    
    if input_type == 'string':
        # Remove potentially dangerous characters
        if not isinstance(input_value, str):
            return False
        # Remove SQL injection patterns
        dangerous_patterns = [
            r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|EXECUTE|UNION|SCRIPT)\b)",
            r"(--|;|/\*|\*/|xp_|sp_)",
            r"(\bor\b|\band\b)\s+\d+\s*=\s*\d+",
        ]
        for pattern in dangerous_patterns:
            if re.search(pattern, input_value, re.IGNORECASE):
                return False
        # Check length
        if max_length and len(input_value) > max_length:
            return False
        return input_value.strip()
    
    elif input_type == 'integer':
        try:
            value = int(input_value)
            return value
        except (ValueError, TypeError):
            return False
    
    elif input_type == 'decimal':
        try:
            value = float(input_value)
            if value < 0:
                return False
            return round(value, 2)
        except (ValueError, TypeError):
            return False
    
    elif input_type == 'email':
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if isinstance(input_value, str) and re.match(email_pattern, input_value):
            return input_value.strip().lower()
        return False
    
    elif input_type == 'date':
        # Validate date format (YYYY-MM-DD)
        date_pattern = r'^\d{4}-\d{2}-\d{2}$'
        if isinstance(input_value, str) and re.match(date_pattern, input_value):
            return input_value
        return False
    
    return False


def sanitize_string(value):
    """
    Sanitize string input to prevent XSS and SQL injection.
    Uses Django's built-in escaping when rendered in templates.
    """
    if not isinstance(value, str):
        return str(value) if value is not None else ''
    
    # Remove null bytes and control characters
    value = value.replace('\x00', '')
    value = ''.join(char for char in value if ord(char) >= 32 or char in '\n\r\t')
    
    return value.strip()


def validate_teacher_access(request, subject_id=None, assessment_id=None):
    """
    Validate that a teacher has access to a specific subject or assessment.
    Prevents teachers from accessing other teachers' data.
    """
    from core.models import TeacherProfile, Subject, Assessment, TeacherSubjectAssignment
    
    if not request.user.is_authenticated or request.user.role != 'teacher':
        return False, 'Unauthorized access'
    
    try:
        teacher_profile = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        return False, 'Teacher profile not found'
    
    if subject_id:
        try:
            # Check if teacher has an assignment for this subject
            assignment = TeacherSubjectAssignment.objects.filter(
                teacher=teacher_profile,
                subject_id=subject_id
            ).first()
            if assignment:
                # Return the subject from the assignment
                return True, assignment.subject
            else:
                return False, 'Subject not found or access denied'
        except Exception:
            return False, 'Subject not found or access denied'
    
    if assessment_id:
        try:
            # Check if teacher owns the assignment for this assessment
            assessment = Assessment.objects.get(id=assessment_id)
            if assessment.assignment and assessment.assignment.teacher == teacher_profile:
                return True, assessment
            else:
                return False, 'Assessment not found or access denied'
        except Assessment.DoesNotExist:
            return False, 'Assessment not found or access denied'
    
    return True, None


def validate_student_access(request, student_id=None):
    """
    Validate that a student can only access their own data.
    Prevents students from accessing other students' data.
    """
    from core.models import StudentProfile
    
    if not request.user.is_authenticated or request.user.role != 'student':
        return False, 'Unauthorized access'
    
    try:
        student_profile = StudentProfile.objects.get(user=request.user)
    except StudentProfile.DoesNotExist:
        return False, 'Student profile not found'
    
    if student_id and student_id != student_profile.id:
        # Students can only access their own data
        return False, 'Access denied'
    
    return True, student_profile

