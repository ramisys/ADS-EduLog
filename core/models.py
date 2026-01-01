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



# ===== YEAR LEVEL =====
class YearLevel(models.Model):
    """
    Represents academic year levels (1st Year, 2nd Year, 3rd Year, 4th Year).
    Normalized model to ensure consistency across sections, students, and subjects.
    """
    LEVEL_CHOICES = [
        (1, '1st Year'),
        (2, '2nd Year'),
        (3, '3rd Year'),
        (4, '4th Year'),
    ]
    
    level = models.IntegerField(unique=True, choices=LEVEL_CHOICES, help_text="Academic year level (1-4)")
    name = models.CharField(max_length=20, unique=True, help_text="Display name (e.g., '1st Year')")
    order = models.IntegerField(unique=True, help_text="Ordering for display purposes")
    is_active = models.BooleanField(default=True, help_text="Whether this year level is currently active")
    
    class Meta:
        verbose_name = 'Year Level'
        verbose_name_plural = 'Year Levels'
        ordering = ['order']
        indexes = [
            models.Index(fields=['level']),
            models.Index(fields=['is_active', 'order']),
        ]
    
    def __str__(self):
        return self.name
    
    def clean(self):
        """Validate that level and order are consistent"""
        from django.core.exceptions import ValidationError
        if self.level and self.order:
            if self.level != self.order:
                raise ValidationError('Level and order must match.')
    
    def save(self, *args, **kwargs):
        """Auto-set order based on level if not provided"""
        if not self.order and self.level:
            self.order = self.level
        self.full_clean()
        super().save(*args, **kwargs)


# ===== CLASS SECTION =====
class ClassSection(models.Model):
    """
    Represents a class section (e.g., BSIT1A, BSIT2B).
    Each section is associated with exactly one year level.
    """
    name = models.CharField(max_length=50)
    year_level = models.ForeignKey('YearLevel', on_delete=models.PROTECT, related_name='sections', 
                                    help_text="Academic year level for this section")
    adviser = models.ForeignKey(TeacherProfile, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='advised_sections')
    
    class Meta:
        verbose_name = 'Class Section'
        verbose_name_plural = 'Class Sections'
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['year_level']),
            models.Index(fields=['adviser']),
            models.Index(fields=['year_level', 'name']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.year_level.name if self.year_level else 'No Year Level'})"
    
    def clean(self):
        """Validate section data"""
        from django.core.exceptions import ValidationError
        if not self.year_level:
            raise ValidationError('Year level is required for class sections.')


# ===== STUDENT PROFILE =====
class StudentProfile(models.Model):
    """
    Student profile with normalized year level relationship.
    Enforces that student's year level matches their section's year level.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    student_id = models.CharField(max_length=20, unique=True, editable=False)
    parent = models.ForeignKey(ParentProfile, on_delete=models.SET_NULL, null=True, blank=True)
    course = models.CharField(max_length=100)
    year_level = models.ForeignKey('YearLevel', on_delete=models.PROTECT, related_name='students',
                                    help_text="Academic year level of the student")
    section = models.ForeignKey('ClassSection', on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='students')
    
    class Meta:
        verbose_name = 'Student Profile'
        verbose_name_plural = 'Student Profiles'
        indexes = [
            models.Index(fields=['student_id']),
            models.Index(fields=['section', 'course']),
            models.Index(fields=['year_level']),
            models.Index(fields=['year_level', 'section']),
        ]

    def clean(self):
        """Validate that student's year level matches section's year level"""
        from django.core.exceptions import ValidationError
        
        if self.section and self.year_level:
            if self.section.year_level != self.year_level:
                raise ValidationError(
                    f"Student's year level ({self.year_level.name}) must match "
                    f"section's year level ({self.section.year_level.name})."
                )
        
        if not self.year_level:
            raise ValidationError('Year level is required for students.')

    def save(self, *args, **kwargs):
        """Auto-set year level from section if not provided, then validate"""
        # Auto-set year level from section if section is provided and year_level is not
        if self.section and not self.year_level:
            self.year_level = self.section.year_level
        
        # Validate before saving
        self.full_clean()
        
        # Generate student_id if not present
        if not self.student_id:
            self.student_id = generate_custom_id('STD')
        
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student_id} - {self.user.get_full_name()}"



# ===== SUBJECT =====
class Subject(models.Model):
    """
    Master catalog of subjects.
    Acts as a reference only - does NOT contain teacher or section information.
    Actual subject offerings are represented by TeacherSubjectAssignment.
    """
    code = models.CharField(max_length=20, unique=True, help_text="Unique subject code (e.g., CS101)")
    name = models.CharField(max_length=100, help_text="Subject name (e.g., Introduction to Programming)")
    description = models.TextField(blank=True, help_text="Optional subject description")
    is_active = models.BooleanField(default=True, help_text="Whether this subject is currently active")
    
    class Meta:
        verbose_name = 'Subject'
        verbose_name_plural = 'Subjects'
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['is_active']),
        ]
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name}"


# ===== TEACHER SUBJECT ASSIGNMENT =====
class TeacherSubjectAssignment(models.Model):
    """
    Represents a subject offering: Subject + Teacher + Section.
    This is what teachers "own" and manage.
    Each assignment represents a teacher teaching a specific subject to a specific section.
    Students are enrolled into this assignment, not directly into Subject.
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
            models.Index(fields=['teacher', 'section', 'subject']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.teacher.user.get_full_name()} - {self.subject.code} ({self.section.name})"
    
    def clean(self):
        """Validate assignment data"""
        from django.core.exceptions import ValidationError
        if not self.subject or not self.section:
            raise ValidationError('Both subject and section are required.')
    
    def save(self, *args, **kwargs):
        """Validate before saving"""
        self.full_clean()
        super().save(*args, **kwargs)
    
    def get_enrolled_students(self):
        """Get all enrolled students for this assignment"""
        return StudentEnrollment.objects.filter(
            assignment=self,
            is_active=True
        ).select_related('student', 'student__user')
    
    def can_teacher_manage(self, teacher_profile):
        """Check if a teacher can manage this assignment"""
        return self.teacher == teacher_profile


# ===== STUDENT ENROLLMENT =====
class StudentEnrollment(models.Model):
    """
    Tracks which students are enrolled in which subject offerings (TeacherSubjectAssignment).
    Students must be enrolled into a TeacherSubjectAssignment, NOT directly into Subject.
    
    Enforces:
    - Students can only be enrolled in assignments from their section
    - Students' year level must match the section's year level
    - No duplicate enrollments per assignment
    """
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='enrollments')
    assignment = models.ForeignKey('TeacherSubjectAssignment', on_delete=models.CASCADE, related_name='enrollments', null=True, blank=True)
    enrolled_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = 'Student Enrollment'
        verbose_name_plural = 'Student Enrollments'
        unique_together = [['student', 'assignment']]
        indexes = [
            models.Index(fields=['student', 'is_active']),
            models.Index(fields=['assignment', 'is_active']),
            models.Index(fields=['student', 'assignment']),
            models.Index(fields=['assignment', 'is_active', 'student']),
        ]
        ordering = ['-enrolled_at']
    
    def __str__(self):
        return f"{self.student.student_id} - {self.assignment.subject.code} ({self.assignment.section.name})"
    
    def clean(self):
        """Validate enrollment constraints"""
        from django.core.exceptions import ValidationError
        
        if not self.student or not self.assignment:
            return  # Skip validation if objects aren't set yet
        
        # Ensure student's section matches assignment's section
        if self.student.section != self.assignment.section:
            raise ValidationError(
                f"Student's section ({self.student.section.name if self.student.section else 'None'}) "
                f"must match assignment's section ({self.assignment.section.name})."
            )
        
        # Ensure student's year level matches section's year level
        if self.student.year_level != self.assignment.section.year_level:
            raise ValidationError(
                f"Student's year level ({self.student.year_level.name}) must match "
                f"section's year level ({self.assignment.section.year_level.name})."
            )
        
        # Check for duplicate enrollment (excluding current instance if updating)
        existing = StudentEnrollment.objects.filter(
            student=self.student,
            assignment=self.assignment,
            is_active=True
        )
        if self.pk:
            existing = existing.exclude(pk=self.pk)
        if existing.exists():
            raise ValidationError(
                f"Student {self.student.student_id} is already enrolled in "
                f"{self.assignment.subject.code} ({self.assignment.section.name})."
            )
    
    def save(self, *args, **kwargs):
        """Validate before saving"""
        self.full_clean()
        super().save(*args, **kwargs)
    
    @property
    def subject(self):
        """Convenience property to access subject through assignment"""
        return self.assignment.subject
    
    @property
    def section(self):
        """Convenience property to access section through assignment"""
        return self.assignment.section
    
    @property
    def teacher(self):
        """Convenience property to access teacher through assignment"""
        return self.assignment.teacher


# ===== ATTENDANCE =====
class Attendance(models.Model):
    """
    Tracks student attendance for enrolled subjects.
    References StudentEnrollment to ensure attendance is only recorded for enrolled students.
    """
    STATUS_CHOICES = [
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('late', 'Late'),
    ]
    enrollment = models.ForeignKey('StudentEnrollment', on_delete=models.CASCADE, related_name='attendances', null=True, blank=True)
    date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    
    class Meta:
        verbose_name = 'Attendance'
        verbose_name_plural = 'Attendances'
        indexes = [
            models.Index(fields=['enrollment', 'date']),
            models.Index(fields=['date', 'status']),
            models.Index(fields=['enrollment', 'date', 'status']),
        ]
        constraints = [
            models.UniqueConstraint(fields=['enrollment', 'date'], name='unique_attendance_per_day'),
        ]
        ordering = ['-date', 'enrollment']
    
    def __str__(self):
        return f"{self.enrollment.student.student_id} - {self.enrollment.assignment.subject.code} ({self.status})"
    
    @property
    def student(self):
        """Convenience property to access student through enrollment"""
        return self.enrollment.student
    
    @property
    def subject(self):
        """Convenience property to access subject through enrollment"""
        return self.enrollment.assignment.subject
    
    @property
    def assignment(self):
        """Convenience property to access assignment through enrollment"""
        return self.enrollment.assignment


# ===== GRADE =====
class Grade(models.Model):
    """
    Tracks student grades per term for enrolled subjects.
    References StudentEnrollment to ensure grades are only recorded for enrolled students.
    """
    enrollment = models.ForeignKey('StudentEnrollment', on_delete=models.CASCADE, related_name='grades', null=True, blank=True)
    term = models.CharField(max_length=20, default="Midterm")
    grade = models.DecimalField(max_digits=5, decimal_places=2)
    
    class Meta:
        verbose_name = 'Grade'
        verbose_name_plural = 'Grades'
        indexes = [
            models.Index(fields=['enrollment', 'term']),
            models.Index(fields=['term', 'grade']),
        ]
        constraints = [
            models.UniqueConstraint(fields=['enrollment', 'term'], name='unique_grade_per_term'),
        ]
        ordering = ['-term', 'enrollment']
    
    def __str__(self):
        return f"{self.enrollment.student.student_id} - {self.enrollment.assignment.subject.code} ({self.term}): {self.grade}"
    
    @property
    def student(self):
        """Convenience property to access student through enrollment"""
        return self.enrollment.student
    
    @property
    def subject(self):
        """Convenience property to access subject through enrollment"""
        return self.enrollment.assignment.subject
    
    @property
    def assignment(self):
        """Convenience property to access assignment through enrollment"""
        return self.enrollment.assignment


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
    """
    Represents an assessment (quiz, exam, project, etc.) for a specific subject offering.
    References TeacherSubjectAssignment to ensure assessments are tied to specific teacher-section combinations.
    """
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
    assignment = models.ForeignKey('TeacherSubjectAssignment', on_delete=models.CASCADE, related_name='assessments', null=True, blank=True)
    max_score = models.DecimalField(max_digits=5, decimal_places=2)
    date = models.DateField()
    term = models.CharField(max_length=20, choices=TERM_CHOICES, default='Midterm')
    created_by = models.ForeignKey(TeacherProfile, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Assessment'
        verbose_name_plural = 'Assessments'
        ordering = ['-date', 'name']
        indexes = [
            models.Index(fields=['assignment', 'date']),
            models.Index(fields=['assignment', 'term']),
            models.Index(fields=['category', 'date']),
            models.Index(fields=['created_by', 'date']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.category}) - {self.assignment.subject.code} ({self.assignment.section.name})"
    
    @property
    def subject(self):
        """Convenience property to access subject through assignment"""
        return self.assignment.subject
    
    @property
    def section(self):
        """Convenience property to access section through assignment"""
        return self.assignment.section
    
    def can_teacher_manage(self, teacher_profile):
        """Check if a teacher can manage this assessment"""
        return self.assignment.teacher == teacher_profile


# ===== ASSESSMENT SCORE =====
class AssessmentScore(models.Model):
    """
    Records student scores for assessments.
    References StudentEnrollment to ensure scores are only recorded for enrolled students.
    """
    enrollment = models.ForeignKey('StudentEnrollment', on_delete=models.CASCADE, related_name='assessment_scores', null=True, blank=True)
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name='scores')
    score = models.DecimalField(max_digits=5, decimal_places=2)
    recorded_by = models.ForeignKey(TeacherProfile, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Assessment Score'
        verbose_name_plural = 'Assessment Scores'
        unique_together = ['enrollment', 'assessment']
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['enrollment', 'assessment']),
            models.Index(fields=['assessment', 'score']),
            models.Index(fields=['recorded_by', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.enrollment.student.student_id} - {self.assessment.name}: {self.score}/{self.assessment.max_score}"
    
    def clean(self):
        """Validate that enrollment matches assessment's assignment"""
        from django.core.exceptions import ValidationError
        if self.enrollment and self.assessment:
            if self.enrollment.assignment != self.assessment.assignment:
                raise ValidationError(
                    f"Enrollment assignment ({self.enrollment.assignment}) must match "
                    f"assessment assignment ({self.assessment.assignment})."
                )
    
    def save(self, *args, **kwargs):
        """Validate before saving"""
        self.full_clean()
        super().save(*args, **kwargs)
    
    @property
    def student(self):
        """Convenience property to access student through enrollment"""
        return self.enrollment.student
    
    @property
    def percentage(self):
        """Calculate percentage score"""
        if self.assessment.max_score > 0:
            return round((self.score / self.assessment.max_score) * 100, 2)
        return 0


# ===== CATEGORY WEIGHTS =====
class CategoryWeights(models.Model):
    """
    Defines weight percentages for assessment categories per subject offering.
    Each TeacherSubjectAssignment can have its own category weights.
    """
    assignment = models.ForeignKey('TeacherSubjectAssignment', on_delete=models.CASCADE, related_name='category_weights', null=True, blank=True)
    activities_weight = models.IntegerField(default=20, help_text="Weight percentage for Activities")
    quizzes_weight = models.IntegerField(default=20, help_text="Weight percentage for Quizzes")
    projects_weight = models.IntegerField(default=30, help_text="Weight percentage for Projects")
    exams_weight = models.IntegerField(default=30, help_text="Weight percentage for Exams")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['assignment']
        verbose_name = 'Category Weight'
        verbose_name_plural = 'Category Weights'
    
    def __str__(self):
        return f"{self.assignment.subject.code} ({self.assignment.section.name}) - Weights"
    
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
    
    @property
    def subject(self):
        """Convenience property to access subject through assignment"""
        return self.assignment.subject
    
    def can_teacher_manage(self, teacher_profile):
        """Check if a teacher can manage these weights"""
        return self.assignment.teacher == teacher_profile


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