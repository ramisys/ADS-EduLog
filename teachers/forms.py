"""
Forms for Teacher Subject Assignment
"""
from django import forms
from django.db.models import Q
import logging
from core.models import TeacherSubjectAssignment, Subject, ClassSection, TeacherProfile, YearLevel, StudentProfile, StudentEnrollment

logger = logging.getLogger(__name__)


class TeacherSubjectAssignmentForm(forms.ModelForm):
    """
    Form for teachers to assign subjects to sections.
    Flow: Year Level → Section → Subjects
    """
    year_level = forms.ModelChoiceField(
        queryset=YearLevel.objects.filter(is_active=True).order_by('order'),
        widget=forms.Select(attrs={
            'class': 'form-select',
            'required': True,
            'id': 'id_year_level'
        }),
        empty_label="Select a year level",
        label="Year Level",
        help_text="First, select the year level"
    )
    
    section = forms.ModelChoiceField(
        queryset=ClassSection.objects.none(),
        widget=forms.Select(attrs={
            'class': 'form-select',
            'required': True,
            'id': 'id_section',
            'disabled': True
        }),
        empty_label="Select a section",
        label="Section",
        help_text="Then, select a section for this year level"
    )
    
    subjects = forms.ModelMultipleChoiceField(
        queryset=Subject.objects.none(),
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input',
            'id': 'id_subjects'
        }),
        label="Subjects",
        help_text="Select one or more subjects to assign"
    )
    
    class Meta:
        model = TeacherSubjectAssignment
        fields = ['section']  # year_level is not a model field, only used for filtering
        # Exclude model validation since we handle it in form's clean() method
        exclude = []
    
    def __init__(self, *args, **kwargs):
        self.teacher = kwargs.pop('teacher', None)
        super().__init__(*args, **kwargs)
        
        # Always populate subjects queryset with all active subjects for validation
        # This ensures ModelMultipleChoiceField can validate selected subject IDs
        self.fields['subjects'].queryset = Subject.objects.filter(
            is_active=True
        ).order_by('code')
        
        # If form has data (POST request), populate section queryset based on year level
        if self.data:
            # Get year level from POST data if available
            year_level_id = self.data.get('year_level')
            if year_level_id:
                try:
                    year_level = YearLevel.objects.get(id=year_level_id, is_active=True)
                    # Update section queryset to include sections for this year level
                    self.fields['section'].queryset = ClassSection.objects.filter(
                        year_level=year_level
                    ).order_by('name')
                except (YearLevel.DoesNotExist, ValueError):
                    pass  # Keep empty queryset if year level is invalid
    
    def _post_clean(self):
        """
        Override to handle model validation properly.
        Since 'subjects' is not a model field, we need to set a temporary
        subject_id on the instance to pass model validation, then validate
        properly in form.clean().
        """
        # Set a temporary subject_id on the instance if we have subjects in cleaned_data
        # This allows the model's clean() to pass validation
        if hasattr(self, 'cleaned_data') and 'subjects' in self.cleaned_data:
            subjects = self.cleaned_data.get('subjects', [])
            if subjects and isinstance(subjects, (list, tuple)) and len(subjects) > 0:
                # Use the first subject's ID as a temporary value for model validation
                first_subject = subjects[0] if isinstance(subjects[0], Subject) else None
                if first_subject and hasattr(first_subject, 'pk'):
                    self.instance.subject_id = first_subject.pk
        
        # Now call the parent's _post_clean which will validate the instance
        # The model's clean() will now pass because subject_id is set
        try:
            super()._post_clean()
        except Exception as e:
            # If validation fails, it's okay - we'll validate properly in form.clean()
            # Just log it and continue
            logger.debug(f"Model validation warning (expected): {str(e)}")
    
    def clean(self):
        cleaned_data = super().clean()
        year_level = cleaned_data.get('year_level')
        section = cleaned_data.get('section')
        subjects = cleaned_data.get('subjects', [])
        teacher = self.teacher
        
        # Ensure subjects is a list/queryset
        if subjects and not isinstance(subjects, (list, tuple)):
            subjects = list(subjects) if hasattr(subjects, '__iter__') else []
        
        # Validate that we have all required fields
        if not year_level or not section or not subjects or not teacher:
            if not subjects:
                raise forms.ValidationError("Please select at least one subject.")
            return cleaned_data
        
        # Ensure all subjects are Subject instances
        valid_subjects = []
        for subject in subjects:
            if not isinstance(subject, Subject):
                logger.warning(f"Invalid subject in cleaned_data: {type(subject)}")
                continue
            if not subject.pk:
                logger.warning(f"Subject {subject} has no primary key")
                continue
            valid_subjects.append(subject)
        
        if not valid_subjects:
            raise forms.ValidationError("No valid subjects were selected.")
        
        # Update cleaned_data with valid subjects
        cleaned_data['subjects'] = valid_subjects
        
        # Validate that section belongs to the selected year level
        if section.year_level != year_level:
            raise forms.ValidationError(
                f'Section {section.name} does not belong to {year_level.name}.'
            )
        
        # Validate all subjects and check for duplicates
        duplicate_subjects = []
        inactive_subjects = []
        
        for subject in subjects:
            # Check if subject is active
            if not subject.is_active:
                inactive_subjects.append(f"{subject.code} ({subject.name})")
            
            # Check for duplicate assignment
            if TeacherSubjectAssignment.objects.filter(
                teacher=teacher,
                subject=subject,
                section=section
            ).exists():
                duplicate_subjects.append(f"{subject.code} ({subject.name})")
        
        # Collect all errors
        errors = []
        if inactive_subjects:
            errors.append(f"The following subjects are not active: {', '.join(inactive_subjects)}")
        if duplicate_subjects:
            errors.append(f"You are already assigned to teach the following subjects in section {section.name}: {', '.join(duplicate_subjects)}")
        
        if errors:
            raise forms.ValidationError(errors)
        
        return cleaned_data
    
    def save(self, commit=True):
        # Get cleaned data - form must be valid to call save()
        cleaned_data = self.cleaned_data
        subjects = cleaned_data.get('subjects', [])
        section = cleaned_data.get('section')
        
        # Validate that we have all required fields
        if not subjects or not section or not self.teacher:
            raise ValueError("Cannot save assignment: missing required fields (subjects, section, or teacher)")
        
        # Create assignments for all selected subjects
        assignments = []
        for subject in subjects:
            # Double-check for duplicates (in case of race condition)
            if not TeacherSubjectAssignment.objects.filter(
                teacher=self.teacher,
                subject=subject,
                section=section
            ).exists():
                assignment = TeacherSubjectAssignment(
                    teacher=self.teacher,
                    subject=subject,
                    section=section
                )
                if commit:
                    assignment.save()
                assignments.append(assignment)
        
        # Return the first assignment for backward compatibility, or all if needed
        return assignments[0] if assignments else None
    
    def save_many(self, commit=True):
        """
        Save method that returns all created assignments.
        Use this when you need all assignments, not just the first one.
        """
        cleaned_data = self.cleaned_data
        subjects = cleaned_data.get('subjects', [])
        section = cleaned_data.get('section')
        
        logger.info(f"save_many called: subjects={subjects}, section={section}, teacher={self.teacher}")
        
        if not subjects:
            logger.error("No subjects in cleaned_data")
            raise ValueError("Cannot save assignment: no subjects selected")
        if not section:
            logger.error("No section in cleaned_data")
            raise ValueError("Cannot save assignment: no section selected")
        if not self.teacher:
            logger.error("No teacher set")
            raise ValueError("Cannot save assignment: no teacher set")
        
        # Ensure subjects is a list/queryset
        if not isinstance(subjects, (list, tuple)):
            subjects = list(subjects) if hasattr(subjects, '__iter__') else [subjects]
        
        logger.info(f"Processing {len(subjects)} subjects")
        assignments = []
        for subject in subjects:
            # Validate subject is a Subject instance
            if not subject or not hasattr(subject, 'id'):
                continue
                
            # Check for duplicates
            if TeacherSubjectAssignment.objects.filter(
                teacher=self.teacher,
                subject=subject,
                section=section
            ).exists():
                continue
            
            # Create assignment with explicit field setting
            # Ensure subject is a valid Subject instance with an ID
            if not isinstance(subject, Subject):
                logger.error(f"Subject is not a Subject instance: {type(subject)}")
                continue
            
            # Ensure subject has a valid primary key
            subject_pk = getattr(subject, 'pk', None) or getattr(subject, 'id', None)
            if not subject_pk:
                logger.error(f"Subject {subject} has no primary key")
                continue
            
            # Ensure section has a valid primary key
            section_pk = getattr(section, 'pk', None) or getattr(section, 'id', None)
            if not section_pk:
                logger.error(f"Section {section} has no primary key")
                continue
            
            assignment = TeacherSubjectAssignment()
            assignment.teacher = self.teacher
            assignment.subject_id = subject_pk  # Set foreign key directly
            assignment.section_id = section_pk   # Set foreign key directly
            
            # Verify subject_id is set before validation
            if not assignment.subject_id:
                logger.error(f"Failed to set subject_id: subject_pk={subject_pk}")
                continue
            
            logger.info(f"Creating assignment: teacher_id={self.teacher.pk}, subject_id={subject_pk}, section_id={section_pk}")
            
            # Validate before saving
            try:
                assignment.full_clean()
            except Exception as e:
                logger.error(f"Validation error creating assignment: {str(e)}")
                continue
            
            if commit:
                try:
                    assignment.save()
                    logger.info(f"Assignment saved with id={assignment.pk}, subject_id={assignment.subject_id}")
                    
                    # Verify assignment was saved correctly by checking subject_id
                    assignment.refresh_from_db()
                    if not assignment.subject_id:
                        logger.error(f"Assignment {assignment.id} was saved without subject_id")
                        if assignment.pk:
                            assignment.delete()
                        continue
                    
                    # Verify the assignment exists in DB with correct subject_id
                    db_assignment = TeacherSubjectAssignment.objects.filter(pk=assignment.pk).values('subject_id').first()
                    if not db_assignment or not db_assignment.get('subject_id'):
                        logger.error(f"Assignment {assignment.id} not found in DB or has no subject_id")
                        if assignment.pk:
                            assignment.delete()
                        continue
                    
                    logger.info(f"Assignment {assignment.pk} verified: subject_id={assignment.subject_id}")
                except Exception as e:
                    logger.error(f"Error saving assignment: {str(e)}", exc_info=True)
                    continue
            else:
                # Even if not committing, verify subject_id is set
                if not assignment.subject_id:
                    logger.error(f"Assignment would be saved without subject_id")
                    continue
            
            assignments.append(assignment)
        
        # Final validation: ensure all returned assignments have subject_id
        valid_assignments = [a for a in assignments if a.subject_id is not None]
        if len(valid_assignments) != len(assignments):
            logger.warning(f"Filtered out {len(assignments) - len(valid_assignments)} invalid assignments")
        
        return valid_assignments


class AddStudentToAssignmentForm(forms.Form):
    """
    Form for teachers to add students to a subject assignment.
    Shows available students from the assignment's section who are not yet enrolled.
    """
    students = forms.ModelMultipleChoiceField(
        queryset=StudentProfile.objects.none(),
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input',
            'id': 'id_students'
        }),
        label="Select Students",
        help_text="Select one or more students to enroll in this subject",
        required=True
    )
    
    def __init__(self, *args, **kwargs):
        self.assignment = kwargs.pop('assignment', None)
        super().__init__(*args, **kwargs)
        
        if self.assignment:
            # Get students from the assignment's section who are not yet enrolled
            enrolled_student_ids = StudentEnrollment.objects.filter(
                assignment=self.assignment,
                is_active=True
            ).values_list('student_id', flat=True)
            
            # Get available students (same section, not enrolled)
            available_students = StudentProfile.objects.filter(
                section=self.assignment.section,
                year_level=self.assignment.section.year_level
            ).exclude(
                id__in=enrolled_student_ids
            ).select_related('user').order_by('user__last_name', 'user__first_name')
            
            self.fields['students'].queryset = available_students
        else:
            self.fields['students'].queryset = StudentProfile.objects.none()
    
    def clean(self):
        cleaned_data = super().clean()
        students = cleaned_data.get('students', [])
        assignment = self.assignment
        
        if not assignment:
            raise forms.ValidationError("Assignment is required.")
        
        # Check if there are any available students
        if not self.fields['students'].queryset.exists():
            raise forms.ValidationError("No students are available to enroll in this subject.")
        
        if not students:
            raise forms.ValidationError("Please select at least one student to enroll.")
        
        # Validate that all selected students belong to the assignment's section
        invalid_students = []
        for student in students:
            if student.section != assignment.section:
                invalid_students.append(f"{student.user.get_full_name()} ({student.student_id})")
            elif student.year_level != assignment.section.year_level:
                invalid_students.append(f"{student.user.get_full_name()} ({student.student_id})")
        
        if invalid_students:
            raise forms.ValidationError(
                f"The following students do not belong to section {assignment.section.name}: "
                f"{', '.join(invalid_students)}"
            )
        
        # Check for already enrolled students (race condition check)
        already_enrolled = []
        for student in students:
            if StudentEnrollment.objects.filter(
                student=student,
                assignment=assignment,
                is_active=True
            ).exists():
                already_enrolled.append(f"{student.user.get_full_name()} ({student.student_id})")
        
        if already_enrolled:
            raise forms.ValidationError(
                f"The following students are already enrolled: {', '.join(already_enrolled)}"
            )
        
        return cleaned_data
    
    def save(self, commit=True):
        """
        Create StudentEnrollment records for selected students.
        Returns list of created enrollments.
        """
        if not self.is_valid():
            raise ValueError("Form must be valid before saving.")
        
        students = self.cleaned_data.get('students', [])
        assignment = self.assignment
        
        if not assignment:
            raise ValueError("Assignment is required.")
        
        enrollments = []
        for student in students:
            # Double-check for duplicates (race condition)
            if StudentEnrollment.objects.filter(
                student=student,
                assignment=assignment,
                is_active=True
            ).exists():
                continue
            
            enrollment = StudentEnrollment(
                student=student,
                assignment=assignment
            )
            
            if commit:
                try:
                    enrollment.save()
                    enrollments.append(enrollment)
                except Exception as e:
                    logger.error(f"Error creating enrollment for student {student.id}: {str(e)}")
                    continue
            else:
                enrollments.append(enrollment)
        
        return enrollments

