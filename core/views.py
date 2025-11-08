from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from datetime import datetime
from .models import TeacherProfile, StudentProfile, ParentProfile, User, Subject, Attendance, Grade, Notification

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
    return HttpResponse(f"EduLog system is working successfully in {datetime.now()}.")

@login_required
def dashboard(request):
    user = request.user
    context = {
        'user': user,
    }
    
    if user.role == 'teacher':
        try:
            teacher_profile = TeacherProfile.objects.get(user=user)
            context['teacher_profile'] = teacher_profile
            # Get subjects taught by this teacher
            subjects = Subject.objects.filter(teacher=teacher_profile)
            context['subjects'] = subjects
            # Get sections where teacher is adviser
            sections = teacher_profile.classsection_set.all()
            context['sections'] = sections
        except TeacherProfile.DoesNotExist:
            pass
            
    elif user.role == 'student':
        try:
            student_profile = StudentProfile.objects.get(user=user)
            context['student_profile'] = student_profile
            # Get attendance records
            attendance_records = Attendance.objects.filter(student=student_profile).order_by('-date')[:10]
            context['attendance_records'] = attendance_records
            # Get grades
            grades = Grade.objects.filter(student=student_profile).order_by('-id')[:10]
            context['grades'] = grades
            # Get subjects for the student's section
            if student_profile.section:
                subjects = Subject.objects.filter(section=student_profile.section)
                context['subjects'] = subjects
        except StudentProfile.DoesNotExist:
            pass
            
    elif user.role == 'parent':
        try:
            parent_profile = ParentProfile.objects.get(user=user)
            context['parent_profile'] = parent_profile
            # Get children (students)
            children = StudentProfile.objects.filter(parent=parent_profile)
            context['children'] = children
        except ParentProfile.DoesNotExist:
            pass
    
    # Get unread notifications for all users
    notifications = Notification.objects.filter(recipient=user, is_read=False).order_by('-created_at')[:10]
    context['notifications'] = notifications
    
    return render(request, 'dashboard.html', context)

def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('login')

def login_view(request):
    if request.method == 'POST':
        identifier = request.POST.get('identifier', '').strip()
        password = request.POST.get('password', '')
        role = request.POST.get('role')
        
        if not identifier or not password or not role:
            messages.error(request, 'Please fill in all fields.')
            return render(request, 'login.html')
        
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
        
        if user is not None and user.is_active:
            if user.role == role:
                # Set backend attribute for login() when multiple backends are configured
                user.backend = 'core.backends.PlainTextPasswordBackend'
                login(request, user)
                messages.success(request, f'Welcome, {user.username}!')
                return redirect('dashboard')
            else:
                messages.error(request, f'Invalid role. You are registered as {user.get_role_display()}.')
        else:
            if role == 'parent':
                messages.error(request, 'Invalid email or password.')
            else:
                messages.error(request, 'Invalid username, ID, email or password.')
    
    return render(request, 'login.html')
   
