from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Avg
from datetime import datetime
from .models import TeacherProfile, StudentProfile, ParentProfile, User, Subject, Attendance, Grade, Notification, ClassSection, Feedback, Semester
from .permissions import validate_input, role_required

def check_password_with_plaintext(user, password):
    """
    Check password - handles both hashed and plain text passwords.
    If password is plain text and matches, it will be hashed and saved.
    """
    # First try Django's check_password (for hashed passwords)
    if user.check_password(password):
        return True
    
    # If check_password fails, check if password is stored as plain text
    # Django hashed passwords start with algorithm identifiers like 'pbkdf2_sha256$', 'bcrypt$', etc.
    stored_password = user.password
    if not stored_password.startswith('pbkdf2_') and not stored_password.startswith('bcrypt$') and not stored_password.startswith('argon2'):
        # Password appears to be stored as plain text
        if stored_password == password:
            # Password matches plain text, hash it and save for future use
            user.set_password(password)
            user.save()
            return True
    
    return False

def index(request):
    # If user is already logged in, redirect to their dashboard
    if request.user.is_authenticated:
        user = request.user
        if user.role == 'teacher':
            return redirect('teachers:dashboard')
        elif user.role == 'student':
            return redirect('students:dashboard')
        elif user.role == 'parent':
            return redirect('parents:dashboard')
        elif user.role == 'admin':
            return redirect('admin_dashboard')
        else:
            return redirect('dashboard')  # fallback to general dashboard
    
    return render(request, 'index.html')

def about(request):
    return render(request, 'about.html')

def user_manual(request):
    return render(request, 'user_manual.html')

@login_required
def dashboard(request):
    user = request.user

    if user.role == 'teacher':
        return redirect('teachers:dashboard')
    elif user.role == 'student':
        return redirect('students:dashboard')
    elif user.role == 'parent':
        return redirect('parents:dashboard')
    elif user.role == 'admin':
        return redirect('admin_dashboard')
    else:
        return redirect('login')  # fallback


@login_required
@role_required('admin')
def admin_dashboard(request):
    """Admin dashboard with feedback management and system overview"""
    from django.db.models import Count, Q
    
    # Get current semester
    current_semester = Semester.get_current()
    
    # Feedback statistics
    total_feedbacks = Feedback.objects.count()
    unread_feedbacks = Feedback.objects.filter(is_read=False, is_archived=False).count()
    avg_rating = Feedback.objects.exclude(rating__isnull=True).aggregate(
        avg_rating=Avg('rating')
    )['avg_rating'] or 0
    
    # User statistics
    total_users = User.objects.count()
    teachers_count = User.objects.filter(role='teacher').count()
    students_count = User.objects.filter(role='student').count()
    parents_count = User.objects.filter(role='parent').count()
    admins_count = User.objects.filter(role='admin').count()
    
    # Recent feedback
    recent_feedbacks = Feedback.objects.select_related('user').order_by('-created_at')[:5]
    
    # Feedback by type
    feedback_by_type = Feedback.objects.values('feedback_type').annotate(
        count=Count('id')
    ).order_by('-count')
    
    context = {
        'total_feedbacks': total_feedbacks,
        'unread_feedbacks': unread_feedbacks,
        'avg_rating': round(avg_rating, 2),
        'total_users': total_users,
        'teachers_count': teachers_count,
        'students_count': students_count,
        'parents_count': parents_count,
        'admins_count': admins_count,
        'recent_feedbacks': recent_feedbacks,
        'feedback_by_type': feedback_by_type,
        'current_semester': current_semester,
    }
    return render(request, 'admin_dashboard.html', context)

def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('login')

def login_view(request):
    context = {}
    
    if request.method == 'POST':
        identifier = request.POST.get('identifier', '').strip()
        password = request.POST.get('password', '')
        role = request.POST.get('role')
        
        # Preserve form data in context
        context['identifier'] = identifier
        context['role'] = role
        
        if not identifier or not password or not role:
            messages.error(request, 'Please fill in all fields.')
            return render(request, 'login.html', context)
        
        user = None
        
        if role == 'teacher':
            # Try login with username, teacher_id, or email
            user = None
            # Try username first
            try:
                user = User.objects.get(username=identifier, role='teacher')
                if not check_password_with_plaintext(user, password):
                    user = None
            except User.DoesNotExist:
                user = None
            
            # If username didn't work, try teacher_id
            if user is None:
                try:
                    teacher_profile = TeacherProfile.objects.get(teacher_id=identifier)
                    user = teacher_profile.user
                    if user.role != 'teacher':
                        user = None
                    elif not check_password_with_plaintext(user, password):
                        user = None
                except TeacherProfile.DoesNotExist:
                    user = None
                except Exception as e:
                    user = None
            
            # If teacher_id didn't work, try email
            if user is None:
                try:
                    user = User.objects.get(email=identifier, role='teacher')
                    if not check_password_with_plaintext(user, password):
                        user = None
                except User.DoesNotExist:
                    user = None
                except Exception as e:
                    user = None
                
        elif role == 'student':
            # Try login with username, student_id, or email
            user = None
            # Try username first
            try:
                user = User.objects.get(username=identifier, role='student')
                if not check_password_with_plaintext(user, password):
                    user = None
            except User.DoesNotExist:
                user = None
            
            # If username didn't work, try student_id
            if user is None:
                try:
                    student_profile = StudentProfile.objects.get(student_id=identifier)
                    user = student_profile.user
                    if user.role != 'student':
                        user = None
                    elif not check_password_with_plaintext(user, password):
                        user = None
                except StudentProfile.DoesNotExist:
                    user = None
                except Exception as e:
                    user = None
            
            # If student_id didn't work, try email
            if user is None:
                try:
                    user = User.objects.get(email=identifier, role='student')
                    if not check_password_with_plaintext(user, password):
                        user = None
                except User.DoesNotExist:
                    user = None
                except Exception as e:
                    user = None
                
        elif role == 'parent':
            # Login with email
            try:
                user = User.objects.get(email=identifier, role='parent')
                # Check password - handles both hashed and plain text
                if not check_password_with_plaintext(user, password):
                    user = None
            except User.DoesNotExist:
                user = None
            except Exception as e:
                user = None
        
        elif role == 'admin':
            # Admin login with username or email
            try:
                user = User.objects.get(username=identifier, role='admin')
                if not check_password_with_plaintext(user, password):
                    user = None
            except User.DoesNotExist:
                user = None
                # Try email if username didn't work
                if user is None:
                    try:
                        user = User.objects.get(email=identifier, role='admin')
                        if not check_password_with_plaintext(user, password):
                            user = None
                    except User.DoesNotExist:
                        user = None
                    except Exception as e:
                        user = None
        
        if user is not None and user.is_active:
            if user.role == role:
                # Set backend attribute for login() when multiple backends are configured
                user.backend = 'core.backends.PlainTextPasswordBackend'
                login(request, user)
                return redirect('dashboard')
            else:
                messages.error(request, f'Invalid role. You are registered as {user.get_role_display()}.')
        else:
            if role == 'parent':
                messages.error(request, 'Invalid email or password.')
            elif role == 'admin':
                messages.error(request, 'Invalid username, email or password.')
            else:
                messages.error(request, 'Invalid username, ID, email or password.')
    
    return render(request, 'login.html', context)

def signup_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        password_confirm = request.POST.get('password_confirm', '')
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        role = request.POST.get('role')
        
        # Validate required fields
        if not username or not email or not password or not password_confirm or not role:
            messages.error(request, 'Please fill in all required fields.')
            return render(request, 'signup.html')
        
        # Check password length
        if len(password) < 8:
            messages.error(request, 'Password must be at least 8 characters long.')
            return render(request, 'signup.html')
        
        # Check if passwords match
        if password != password_confirm:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'signup.html')
        
        # Check if username already exists
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists.')
            return render(request, 'signup.html')
        
        # Check if email already exists
        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email already exists.')
            return render(request, 'signup.html')
        
        # Create user
        try:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                role=role
            )
            
            # Create profile based on role
            if role == 'teacher':
                department = request.POST.get('department', '').strip()
                if not department:
                    user.delete()
                    messages.error(request, 'Department is required for teachers.')
                    return render(request, 'signup.html')
                TeacherProfile.objects.create(user=user, department=department)
                
            elif role == 'student':
                from core.models import YearLevel
                course = request.POST.get('course', '').strip()
                year_level_id = request.POST.get('year_level', '').strip()
                section_id = request.POST.get('section', '').strip()
                
                if not course or not year_level_id:
                    user.delete()
                    messages.error(request, 'Course and year level are required for students.')
                    return render(request, 'signup.html')
                
                try:
                    year_level = YearLevel.objects.get(id=year_level_id)
                    section = None
                    if section_id:
                        from core.models import ClassSection
                        section = ClassSection.objects.get(id=section_id)
                        # Validate that section's year level matches selected year level
                        if section.year_level != year_level:
                            user.delete()
                            messages.error(request, 'Selected section does not match the selected year level.')
                            return render(request, 'signup.html')
                    
                    StudentProfile.objects.create(
                        user=user, 
                        course=course, 
                        year_level=year_level,
                        section=section
                    )
                except YearLevel.DoesNotExist:
                    user.delete()
                    messages.error(request, 'Invalid year level selected.')
                    return render(request, 'signup.html')
                except ClassSection.DoesNotExist:
                    user.delete()
                    messages.error(request, 'Invalid section selected.')
                    return render(request, 'signup.html')
                
            elif role == 'parent':
                contact_number = request.POST.get('contact_number', '').strip()
                ParentProfile.objects.create(user=user, contact_number=contact_number)
            
            messages.success(request, 'Account created successfully! Please login.')
            return redirect('login')
            
        except Exception as e:
            messages.error(request, f'An error occurred: {str(e)}')
            return render(request, 'signup.html')
    
    # Get sections and year levels for student signup
    from core.models import YearLevel, ClassSection
    sections = ClassSection.objects.select_related('year_level').all()
    year_levels = YearLevel.objects.filter(is_active=True).order_by('order')
    return render(request, 'signup.html', {
        'sections': sections,
        'year_levels': year_levels
    })

def forgot_password_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    is_submitted = False
    email = ''
    
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        resend = request.POST.get('resend', 'false')
        
        if resend == 'true':
            # Resend email logic
            is_submitted = True
            messages.success(request, 'Password reset link has been resent to your email.')
        elif email:
            # Check if user exists
            try:
                user = User.objects.get(email=email)
                # TODO: Send password reset email here
                # For now, just show success message
                is_submitted = True
                messages.success(request, 'Password reset link has been sent to your email.')
            except User.DoesNotExist:
                # Don't reveal if email exists for security
                is_submitted = True
                messages.success(request, 'If an account exists with this email, a password reset link has been sent.')
        else:
            messages.error(request, 'Please enter your email address.')
    
    context = {
        'is_submitted': is_submitted,
        'email': email,
    }
    return render(request, 'forgot_password.html', context)


@login_required
def feedback_submit(request):
    """View for users to submit feedback"""
    if request.method == 'POST':
        feedback_type = request.POST.get('feedback_type', 'general')
        rating = request.POST.get('rating')
        subject = request.POST.get('subject', '').strip()
        message = request.POST.get('message', '').strip()
        is_anonymous = request.POST.get('is_anonymous') == 'on'
        
        # Validate input
        if not message:
            messages.error(request, 'Please provide a feedback message.')
            return render(request, 'feedback_submit.html')
        
        # Validate feedback type
        valid_types = [choice[0] for choice in Feedback.FEEDBACK_TYPE_CHOICES]
        if feedback_type not in valid_types:
            feedback_type = 'general'
        
        # Validate rating if provided
        rating_value = None
        if rating:
            try:
                rating_value = int(rating)
                if rating_value not in [1, 2, 3, 4, 5]:
                    rating_value = None
            except ValueError:
                rating_value = None
        
        # Validate and sanitize subject
        subject = validate_input(subject, 'string', max_length=200) or ''
        message = validate_input(message, 'string') or ''
        
        if not message:
            messages.error(request, 'Invalid feedback message.')
            return render(request, 'feedback_submit.html')
        
        # Create feedback
        try:
            feedback = Feedback.objects.create(
                user=request.user if not is_anonymous else None,
                feedback_type=feedback_type,
                rating=rating_value,
                subject=subject,
                message=message,
                is_anonymous=is_anonymous
            )
            messages.success(request, 'Thank you for your feedback! Your input helps us improve EduLog.')
            return redirect('feedback_submit')
        except Exception as e:
            messages.error(request, f'An error occurred while submitting feedback: {str(e)}')
    
    # GET request - show form
    return render(request, 'feedback_submit.html')


@login_required
@role_required('admin')
def feedback_list(request):
    """View for admins to view and manage feedback"""
    feedbacks = Feedback.objects.all().select_related('user', 'responded_by').order_by('-created_at')
    
    # Filtering
    filter_type = request.GET.get('type', '')
    filter_read = request.GET.get('read', '')
    filter_archived = request.GET.get('archived', 'false')
    
    if filter_type:
        feedbacks = feedbacks.filter(feedback_type=filter_type)
    
    if filter_read == 'read':
        feedbacks = feedbacks.filter(is_read=True)
    elif filter_read == 'unread':
        feedbacks = feedbacks.filter(is_read=False)
    
    if filter_archived == 'false':
        feedbacks = feedbacks.filter(is_archived=False)
    elif filter_archived == 'true':
        feedbacks = feedbacks.filter(is_archived=True)
    
    # Statistics
    total_feedbacks = Feedback.objects.count()
    unread_count = Feedback.objects.filter(is_read=False, is_archived=False).count()
    avg_rating = Feedback.objects.exclude(rating__isnull=True).aggregate(
        avg_rating=Avg('rating')
    )['avg_rating'] or 0
    
    context = {
        'feedbacks': feedbacks,
        'total_feedbacks': total_feedbacks,
        'unread_count': unread_count,
        'avg_rating': round(avg_rating, 2),
        'filter_type': filter_type,
        'filter_read': filter_read,
        'filter_archived': filter_archived,
    }
    return render(request, 'feedback_list.html', context)


@login_required
@role_required('admin')
def feedback_detail(request, feedback_id):
    """View for admins to view and respond to specific feedback"""
    try:
        feedback = Feedback.objects.select_related('user', 'responded_by').get(id=feedback_id)
    except Feedback.DoesNotExist:
        messages.error(request, 'Feedback not found.')
        return redirect('feedback_list')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'mark_read':
            feedback.is_read = True
            feedback.save()
            messages.success(request, 'Feedback marked as read.')
        
        elif action == 'mark_unread':
            feedback.is_read = False
            feedback.save()
            messages.success(request, 'Feedback marked as unread.')
        
        elif action == 'archive':
            feedback.is_archived = True
            feedback.save()
            messages.success(request, 'Feedback archived.')
        
        elif action == 'unarchive':
            feedback.is_archived = False
            feedback.save()
            messages.success(request, 'Feedback unarchived.')
        
        elif action == 'respond':
            admin_response = request.POST.get('admin_response', '').strip()
            admin_response = validate_input(admin_response, 'string') or ''
            
            if admin_response:
                feedback.admin_response = admin_response
                feedback.responded_by = request.user
                feedback.responded_at = datetime.now()
                feedback.is_read = True
                feedback.save()
                messages.success(request, 'Response saved successfully.')
            else:
                messages.error(request, 'Please provide a response message.')
        
        return redirect('feedback_detail', feedback_id=feedback_id)
    
    context = {
        'feedback': feedback,
    }
    return render(request, 'feedback_detail.html', context)


@login_required
@role_required('admin')
def semester_management(request):
    """Admin view for managing semesters"""
    semesters = Semester.objects.all().order_by('-academic_year', '-start_date')
    current_semester = get_current_semester()
    
    context = {
        'semesters': semesters,
        'current_semester': current_semester,
    }
    return render(request, 'semester_management.html', context)


@login_required
@role_required('admin')
def semester_set_active(request, semester_id):
    """Set a semester as active (deactivates previous current semester)"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        semester = get_object_or_404(Semester, pk=semester_id)
        
        # Validate semester can be activated
        if semester.status not in ['upcoming', 'active']:
            messages.error(request, f'Cannot activate {semester.get_status_display()} semester.')
            return redirect('semester_management')
        
        # Set as current (this will auto-deactivate others)
        semester.is_current = True
        semester.status = 'active'
        semester.save()
        
        messages.success(request, f'{semester} is now the active semester.')
    except Exception as e:
        messages.error(request, f'Error activating semester: {str(e)}')
    
    return redirect('semester_management')


@login_required
@role_required('admin')
def semester_close(request, semester_id):
    """Close an active semester"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        semester = get_object_or_404(Semester, pk=semester_id)
        
        if semester.status != 'active':
            messages.error(request, f'Only active semesters can be closed.')
            return redirect('semester_management')
        
        semester.status = 'closed'
        semester.is_current = False
        semester.save()
        
        messages.success(request, f'{semester} has been closed.')
    except Exception as e:
        messages.error(request, f'Error closing semester: {str(e)}')
    
    return redirect('semester_management')


@login_required
@role_required('admin')
def semester_archive(request, semester_id):
    """Archive a closed semester"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        semester = get_object_or_404(Semester, pk=semester_id)
        
        if semester.status != 'closed':
            messages.error(request, f'Only closed semesters can be archived.')
            return redirect('semester_management')
        
        semester.status = 'archived'
        semester.save()
        
        messages.success(request, f'{semester} has been archived.')
    except Exception as e:
        messages.error(request, f'Error archiving semester: {str(e)}')
    
    return redirect('semester_management')


@login_required
@role_required('admin')
def semester_create(request):
    """Create a new semester"""
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        academic_year = request.POST.get('academic_year', '').strip()
        start_date = request.POST.get('start_date', '')
        end_date = request.POST.get('end_date', '')
        status = request.POST.get('status', 'upcoming')
        
        # Validate required fields
        if not name or not academic_year or not start_date or not end_date:
            messages.error(request, 'Please fill in all required fields.')
            return redirect('semester_management')
        
        try:
            from datetime import datetime
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            
            semester = Semester.objects.create(
                name=name,
                academic_year=academic_year,
                start_date=start_date_obj,
                end_date=end_date_obj,
                status=status,
                is_current=False  # Don't auto-set as current
            )
            
            messages.success(request, f'Semester "{semester}" created successfully.')
        except ValueError as e:
            messages.error(request, f'Invalid date format: {str(e)}')
        except Exception as e:
            messages.error(request, f'Error creating semester: {str(e)}')
        
        return redirect('semester_management')
    
    # GET request - redirect to management page
    return redirect('semester_management')
