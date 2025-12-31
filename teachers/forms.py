"""
Forms for Teacher Subject Assignment
"""
from django import forms
from django.db.models import Q
from core.models import TeacherSubjectAssignment, Subject, ClassSection, TeacherProfile


class TeacherSubjectAssignmentForm(forms.ModelForm):
    """
    Form for teachers to assign subjects to sections.
    Shows unique subjects by base code/name, then allows section selection.
    """
    # Use ChoiceField for subject selection to handle base codes
    subject_code = forms.ChoiceField(
        widget=forms.Select(attrs={
            'class': 'form-select',
            'required': True
        }),
        label="Subject",
        help_text="Select a subject from the available subjects list"
    )
    
    section = forms.ModelChoiceField(
        queryset=ClassSection.objects.all().order_by('name'),
        widget=forms.Select(attrs={
            'class': 'form-select',
            'required': True
        }),
        empty_label="Select a section",
        label="Section",
        help_text="Select a class section for this subject"
    )
    
    class Meta:
        model = TeacherSubjectAssignment
        fields = ['section']  # subject will be handled separately
    
    def __init__(self, *args, **kwargs):
        self.teacher = kwargs.pop('teacher', None)
        super().__init__(*args, **kwargs)
        
        # Get unique subjects by extracting base code and name
        # Subjects may have codes like "IT101-BSIT1A" - we want to show "IT101 - Intro to IT"
        all_subjects = Subject.objects.all().order_by('code', 'name')
        
        # Create a mapping of base_code -> (name, first_subject_id)
        # Base code is everything before the last hyphen (if it contains section info)
        unique_subjects = {}
        for subject in all_subjects:
            # Extract base code (remove section suffix if present)
            code = subject.code
            # Check if code contains a section-like suffix (e.g., "-BSIT1A")
            # We'll use the code as-is but group by the base part
            base_code = code
            # Try to extract base code (everything before last hyphen if it looks like a section)
            if '-' in code:
                parts = code.rsplit('-', 1)
                if len(parts) == 2 and len(parts[1]) <= 10:  # Section codes are usually short
                    base_code = parts[0]
            
            # Use base_code + name as unique key
            key = f"{base_code}|{subject.name}"
            if key not in unique_subjects:
                unique_subjects[key] = {
                    'code': base_code,
                    'name': subject.name,
                    'display': f"{base_code} - {subject.name}",
                    'first_subject': subject  # Keep reference to first subject for this base code
                }
        
        # Create choices for the dropdown
        subject_choices = [('', 'Select a subject')]
        for key, info in sorted(unique_subjects.items(), key=lambda x: (x[1]['code'], x[1]['name'])):
            subject_choices.append((key, info['display']))
        
        self.fields['subject_code'].choices = subject_choices
        self.fields['section'].queryset = ClassSection.objects.all().order_by('name')
        
        # Store unique_subjects for use in clean method
        self._unique_subjects = unique_subjects
    
    def clean(self):
        cleaned_data = super().clean()
        subject_code_key = cleaned_data.get('subject_code')
        section = cleaned_data.get('section')
        teacher = self.teacher
        
        if not subject_code_key or not section or not teacher:
            return cleaned_data
        
        # Extract base code and name from the key
        if '|' in subject_code_key:
            base_code, subject_name = subject_code_key.split('|', 1)
        else:
            raise forms.ValidationError('Invalid subject selection.')
        
        # Find the Subject for this base_code + section combination
        # Subjects have codes like "IT101-BSIT1A" where "IT101" is base and "BSIT1A" is section
        section_code = section.name.replace(' ', '')
        full_code = f"{base_code}-{section_code}"
        
        # Try to find subject with exact code match first
        subject = Subject.objects.filter(
            code=full_code,
            name=subject_name,
            section=section
        ).first()
        
        # If not found, try to find by base code pattern and section
        if not subject:
            subject = Subject.objects.filter(
                section=section,
                name=subject_name
            ).filter(
                Q(code__startswith=base_code + '-') | Q(code=base_code)
            ).first()
        
        # If still not found, subjects are predefined by admin, so this is an error
        if not subject:
            raise forms.ValidationError(
                f'Subject "{base_code} - {subject_name}" is not available for section {section.name}. '
                'Please contact the administrator to add this subject for this section.'
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
        
        # Store the subject in cleaned_data for use in save
        cleaned_data['subject'] = subject
        
        return cleaned_data
    
    def save(self, commit=True):
        assignment = super().save(commit=False)
        assignment.subject = self.cleaned_data['subject']
        assignment.teacher = self.teacher
        if commit:
            assignment.save()
        return assignment

