from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from datetime import datetime

# ===== CUSTOM USER MANAGER =====
class UserManager(BaseUserManager):
    def create_user(self, username, email=None, password=None, **extra_fields):
        if not username:
            raise ValueError('The Username field must be set')
        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'admin')  # Set role to admin for superusers

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(username, email, password, **extra_fields)

# ===== CUSTOM USER =====
class User(AbstractUser):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('teacher', 'Teacher'),
        ('student', 'Student'),
        ('parent', 'Parent'),
    ]
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='student')
    
    objects = UserManager()

    def __str__(self):
        return f"{self.username} ({self.role})"

# ===== FIXED ID GENERATOR =====
def generate_custom_id(prefix):
    from datetime import datetime
    year = datetime.now().year

    # Map model and field name per prefix
    model_map = {
        'STD': ('StudentProfile', 'student_id'),
        'TCH': ('TeacherProfile', 'teacher_id'),
        'PRT': ('ParentProfile', 'parent_id'),
    }

    model_name, field_name = model_map.get(prefix, (None, None))
    if not model_name:
        return None

    # Dynamically import model
    from core.models import StudentProfile, TeacherProfile, ParentProfile
    model = eval(model_name)

    # Get last record with same year prefix
    last_entry = model.objects.filter(**{f"{field_name}__startswith": f"{prefix}-{year}"}).order_by('id').last()

    if last_entry:
        last_number = int(getattr(last_entry, field_name).split('-')[-1])
        new_number = last_number + 1
    else:
        new_number = 1

    return f"{prefix}-{year}-{new_number:05d}"

# ===== PARENT PROFILE =====
class ParentProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    parent_id = models.CharField(max_length=20, unique=True, editable=False, null=True, blank=True)
    contact_number = models.CharField(max_length=15, blank=True)

    def save(self, *args, **kwargs):
        if not self.parent_id:  # <-- fixed reference
            self.parent_id = generate_custom_id('PRT')
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.parent_id} - {self.user.get_full_name()}"


# ===== TEACHER PROFILE =====
class TeacherProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    teacher_id = models.CharField(max_length=20, unique=True, editable=False, null=True, blank=True)
    department = models.CharField(max_length=100)

    def save(self, *args, **kwargs):
        if not self.teacher_id:  # <-- fixed reference
            self.teacher_id = generate_custom_id('TCH')
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.teacher_id} - {self.user.get_full_name()}"



# ===== CLASS SECTION =====
class ClassSection(models.Model):
    name = models.CharField(max_length=50)
    adviser = models.ForeignKey(TeacherProfile, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return self.name


# ===== STUDENT PROFILE =====
class StudentProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    student_id = models.CharField(max_length=20, unique=True, editable=False)
    parent = models.ForeignKey(ParentProfile, on_delete=models.SET_NULL, null=True, blank=True)
    course = models.CharField(max_length=100)
    year_level = models.CharField(max_length=20)
    section = models.ForeignKey('ClassSection', on_delete=models.SET_NULL, null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.student_id:  # ✅ Fixed reference
            self.student_id = generate_custom_id('STD')
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student_id} - {self.user.get_full_name()}"



# ===== SUBJECT =====
class Subject(models.Model):
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=100)
    teacher = models.ForeignKey(TeacherProfile, on_delete=models.SET_NULL, null=True)
    section = models.ForeignKey(ClassSection, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.code} - {self.name}"


# ===== ATTENDANCE =====
class Attendance(models.Model):
    STATUS_CHOICES = [
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('late', 'Late'),
    ]
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    date = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)

    def __str__(self):
        return f"{self.student.student_id} - {self.subject.code} ({self.status})"


# ===== GRADE =====
class Grade(models.Model):
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    term = models.CharField(max_length=20, default="Midterm")
    grade = models.DecimalField(max_digits=5, decimal_places=2)

    def __str__(self):
        return f"{self.student.student_id} - {self.subject.code}: {self.grade}"


# ===== NOTIFICATION =====
class Notification(models.Model):
    recipient = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"To: {self.recipient.username} - {self.message[:30]}..."
