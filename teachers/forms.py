"""
Forms for Teacher Subject Assignment
"""
from django import forms
from django.db.models import Q
from core.models import TeacherSubjectAssignment, Subject, ClassSection, TeacherProfile, YearLevel


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
    
    subject = forms.ModelChoiceField(
        queryset=Subject.objects.none(),
        widget=forms.Select(attrs={
            'class': 'form-select',
            'required': True,
            'id': 'id_subject',
            'disabled': True
        }),
        empty_label="Select a subject",
        label="Subject",
        help_text="Finally, select a subject available for this year level"
    )
    
    class Meta:
        model = TeacherSubjectAssignment
        fields = ['section', 'subject']  # year_level is not a model field, only used for filtering
    
    def __init__(self, *args, **kwargs):
        self.teacher = kwargs.pop('teacher', None)
        super().__init__(*args, **kwargs)
        
        # If form has data (POST request), populate querysets to allow proper validation
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
                    # Update subject queryset - for now, include all active subjects
                    # (In a real scenario, you might filter by year level if subjects are year-specific)
                    self.fields['subject'].queryset = Subject.objects.filter(
                        is_active=True
                    ).order_by('code')
                except (YearLevel.DoesNotExist, ValueError):
                    pass  # Keep empty querysets if year level is invalid
    
    def clean(self):
        cleaned_data = super().clean()
        year_level = cleaned_data.get('year_level')
        section = cleaned_data.get('section')
        subject = cleaned_data.get('subject')
        teacher = self.teacher
        
        if not year_level or not section or not subject or not teacher:
            return cleaned_data
        
        # Validate that section belongs to the selected year level
        if section.year_level != year_level:
            raise forms.ValidationError(
                f'Section {section.name} does not belong to {year_level.name}.'
            )
        
        # Validate that subject is available for this year level
        # Subjects are organized by year level in the seeder
        # We can check if the subject code matches the year level pattern
        # For now, we'll just check if the subject exists and is active
        if not subject.is_active:
            raise forms.ValidationError(
                f'Subject {subject.code} ({subject.name}) is not active.'
            )
        
        # Check for duplicate assignment
        if TeacherSubjectAssignment.objects.filter(
            teacher=teacher,
            subject=subject,
            section=section
        ).exists():
            raise forms.ValidationError(
                f'You are already assigned to teach {subject.code} ({subject.name}) in section {section.name}.'
            )
        
        return cleaned_data
    
    def save(self, commit=True):
        # Get cleaned data - form must be valid to call save()
        cleaned_data = self.cleaned_data
        subject = cleaned_data.get('subject')
        section = cleaned_data.get('section')
        
        # Validate that we have all required fields
        if not subject or not section or not self.teacher:
            raise ValueError("Cannot save assignment: missing required fields (subject, section, or teacher)")
        
        # Create the assignment instance explicitly
        assignment = TeacherSubjectAssignment(
            teacher=self.teacher,
            subject=subject,
            section=section
        )
        
        if commit:
            assignment.save()
        return assignment

