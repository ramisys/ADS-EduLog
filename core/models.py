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
    
    class Meta:
        indexes = [
            models.Index(fields=['role', 'is_active']),
            models.Index(fields=['email']),
        ]

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
    
    class Meta:
        indexes = [
            models.Index(fields=['parent_id']),
        ]

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
    
    class Meta:
        indexes = [
            models.Index(fields=['teacher_id']),
            models.Index(fields=['department']),
        ]

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
    
    class Meta:
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['adviser']),
        ]

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
    
    class Meta:
        indexes = [
            models.Index(fields=['student_id']),
            models.Index(fields=['section', 'course']),
            models.Index(fields=['section', 'year_level']),
        ]

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
    
    class Meta:
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['teacher', 'section']),
            models.Index(fields=['section', 'code']),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"


# ===== TEACHER SUBJECT ASSIGNMENT =====
class TeacherSubjectAssignment(models.Model):
    """
    Links teachers to subjects and sections, allowing teachers to assign themselves
    to teach specific subjects in specific class sections.
    """
    teacher = models.ForeignKey(TeacherProfile, on_delete=models.CASCADE, related_name='subject_assignments')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='teacher_assignments')
    section = models.ForeignKey(ClassSection, on_delete=models.CASCADE, related_name='teacher_subject_assignments')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Teacher Subject Assignment'
        verbose_name_plural = 'Teacher Subject Assignments'
        unique_together = [['teacher', 'subject', 'section']]
        indexes = [
            models.Index(fields=['teacher', 'section']),
            models.Index(fields=['subject', 'section']),
            models.Index(fields=['teacher', 'subject']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.teacher.user.get_full_name()} - {self.subject.code} ({self.section.name})"


# ===== ATTENDANCE =====
class Attendance(models.Model):
    STATUS_CHOICES = [
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('late', 'Late'),
    ]
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    
    class Meta:
        indexes = [
            models.Index(fields=['student', 'date']),
            models.Index(fields=['subject', 'date']),
            models.Index(fields=['student', 'subject', 'date']),
            models.Index(fields=['date', 'status']),
        ]
        constraints = [
            models.UniqueConstraint(fields=['student', 'subject', 'date'], name='unique_attendance_per_day'),
        ]
        ordering = ['-date', 'student']

    def __str__(self):
        return f"{self.student.student_id} - {self.subject.code} ({self.status})"


# ===== GRADE =====
class Grade(models.Model):
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    term = models.CharField(max_length=20, default="Midterm")
    grade = models.DecimalField(max_digits=5, decimal_places=2)
    
    class Meta:
        indexes = [
            models.Index(fields=['student', 'subject']),
            models.Index(fields=['student', 'term']),
            models.Index(fields=['subject', 'term']),
        ]
        constraints = [
            models.UniqueConstraint(fields=['student', 'subject', 'term'], name='unique_grade_per_term'),
        ]
        ordering = ['-term', 'subject']

    def __str__(self):
        return f"{self.student.student_id} - {self.subject.code}: {self.grade}"


# ===== NOTIFICATION =====
class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('attendance_absent', 'Attendance - Absent'),
        ('attendance_late', 'Attendance - Late'),
        ('performance_at_risk', 'Performance - At Risk'),
        ('performance_improved', 'Performance - Improved'),
        ('performance_warning_attendance', 'Performance Warning - Low Attendance'),
        ('performance_warning_gpa', 'Performance Warning - Low GPA'),
        ('consecutive_absences', 'Consecutive Absences'),
        ('teacher_student_at_risk', 'Teacher - Student At Risk'),
        ('teacher_consecutive_absences', 'Teacher - Consecutive Absences'),
        ('general', 'General'),
    ]
    
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    message = models.TextField()
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES, default='general')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    # Track related objects for deduplication
    related_student = models.ForeignKey('StudentProfile', on_delete=models.CASCADE, null=True, blank=True, related_name='related_notifications')
    related_subject = models.ForeignKey('Subject', on_delete=models.CASCADE, null=True, blank=True, related_name='related_notifications')
    # Track notification key for deduplication (e.g., "performance_at_risk_student_123")
    notification_key = models.CharField(max_length=200, blank=True, null=True, db_index=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read', '-created_at']),
            models.Index(fields=['notification_key']),
        ]
    
    def __str__(self):
        return f"To: {self.recipient.username} - {self.message[:30]}..."


# ===== ASSESSMENT =====
class Assessment(models.Model):
    CATEGORY_CHOICES = [
        ('Activities', 'Activities'),
        ('Quizzes', 'Quizzes'),
        ('Projects', 'Projects'),
        ('Exams', 'Exams'),
    ]
    
    TERM_CHOICES = [
        ('Midterm', 'Midterm'),
        ('Final', 'Final'),
    ]
    
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='assessments')
    max_score = models.DecimalField(max_digits=5, decimal_places=2)
    date = models.DateField()
    term = models.CharField(max_length=20, choices=TERM_CHOICES, default='Midterm')
    created_by = models.ForeignKey(TeacherProfile, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-date', 'name']
        indexes = [
            models.Index(fields=['subject', 'date']),
            models.Index(fields=['subject', 'term']),
            models.Index(fields=['category', 'date']),
            models.Index(fields=['created_by', 'date']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.category}) - {self.subject.code}"


# ===== ASSESSMENT SCORE =====
class AssessmentScore(models.Model):
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='assessment_scores')
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name='scores')
    score = models.DecimalField(max_digits=5, decimal_places=2)
    recorded_by = models.ForeignKey(TeacherProfile, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['student', 'assessment']
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['student', 'assessment']),
            models.Index(fields=['assessment', 'score']),
            models.Index(fields=['recorded_by', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.student.student_id} - {self.assessment.name}: {self.score}/{self.assessment.max_score}"
    
    @property
    def percentage(self):
        """Calculate percentage score"""
        if self.assessment.max_score > 0:
            return round((self.score / self.assessment.max_score) * 100, 2)
        return 0


# ===== CATEGORY WEIGHTS =====
class CategoryWeights(models.Model):
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='category_weights')
    activities_weight = models.IntegerField(default=20, help_text="Weight percentage for Activities")
    quizzes_weight = models.IntegerField(default=20, help_text="Weight percentage for Quizzes")
    projects_weight = models.IntegerField(default=30, help_text="Weight percentage for Projects")
    exams_weight = models.IntegerField(default=30, help_text="Weight percentage for Exams")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['subject']
        verbose_name = 'Category Weight'
        verbose_name_plural = 'Category Weights'
    
    def __str__(self):
        return f"{self.subject.code} - Weights"
    
    def clean(self):
        """Validate that weights sum to 100"""
        from django.core.exceptions import ValidationError
        total = (self.activities_weight + self.quizzes_weight + 
                self.projects_weight + self.exams_weight)
        if total != 100:
            raise ValidationError(f'Category weights must sum to 100%. Current total: {total}%')
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
    
    def get_weight(self, category):
        """Get weight for a specific category"""
        weight_map = {
            'Activities': self.activities_weight,
            'Quizzes': self.quizzes_weight,
            'Projects': self.projects_weight,
            'Exams': self.exams_weight,
        }
        return weight_map.get(category, 0)


# ===== AUDIT LOG =====
class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('Grade Updated', 'Grade Updated'),
        ('Assessment Added', 'Assessment Added'),
        ('Assessment Updated', 'Assessment Updated'),
        ('Assessment Deleted', 'Assessment Deleted'),
        ('Category Weight Changed', 'Category Weight Changed'),
        ('Score Added', 'Score Added'),
        ('Score Updated', 'Score Updated'),
        ('Score Deleted', 'Score Deleted'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='audit_logs')
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    details = models.TextField()
    student = models.ForeignKey(StudentProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    assessment = models.ForeignKey(Assessment, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['action', 'timestamp']),
            models.Index(fields=['student', 'timestamp']),
        ]
    
    def __str__(self):
        return f"{self.action} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"


# ===== FEEDBACK =====
class Feedback(models.Model):
    FEEDBACK_TYPE_CHOICES = [
        ('general', 'General Feedback'),
        ('bug_report', 'Bug Report'),
        ('feature_request', 'Feature Request'),
        ('improvement', 'Improvement Suggestion'),
        ('compliment', 'Compliment'),
    ]
    
    RATING_CHOICES = [
        (1, '1 - Poor'),
        (2, '2 - Fair'),
        (3, '3 - Good'),
        (4, '4 - Very Good'),
        (5, '5 - Excellent'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='feedbacks')
    feedback_type = models.CharField(max_length=20, choices=FEEDBACK_TYPE_CHOICES, default='general')
    rating = models.IntegerField(choices=RATING_CHOICES, null=True, blank=True, help_text='Overall system rating (1-5)')
    subject = models.CharField(max_length=200, blank=True, help_text='Brief subject/title of feedback')
    message = models.TextField(help_text='Detailed feedback message')
    is_anonymous = models.BooleanField(default=False, help_text='Submit feedback anonymously')
    is_read = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)
    admin_response = models.TextField(blank=True, help_text='Admin response to feedback')
    responded_at = models.DateTimeField(null=True, blank=True)
    responded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='feedback_responses')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Feedback'
        verbose_name_plural = 'Feedbacks'
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['feedback_type', 'created_at']),
            models.Index(fields=['is_read', 'created_at']),
            models.Index(fields=['rating', 'created_at']),
        ]
    
    def __str__(self):
        user_display = 'Anonymous' if self.is_anonymous else (self.user.get_full_name() if self.user else 'Unknown')
        return f"Feedback from {user_display} - {self.get_feedback_type_display()} ({self.created_at.strftime('%Y-%m-%d')})"