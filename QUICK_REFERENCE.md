# Quick Reference: Using the Refactored Models

## 🔑 Key Relationships

```
Subject (Master Catalog)
    ↓
TeacherSubjectAssignment (Subject + Teacher + Section)
    ↓
StudentEnrollment (Student + Assignment)
    ↓
Attendance, Grades, AssessmentScores
```

## 📝 Common Operations

### 1. Teacher Views Their Assignments
```python
teacher_profile = TeacherProfile.objects.get(user=request.user)
assignments = TeacherSubjectAssignment.objects.filter(
    teacher=teacher_profile
).select_related('subject', 'section')
```

### 2. Teacher Views Enrolled Students for an Assignment
```python
assignment = TeacherSubjectAssignment.objects.get(id=assignment_id)
enrolled_students = assignment.get_enrolled_students()
# Or:
enrollments = StudentEnrollment.objects.filter(
    assignment=assignment,
    is_active=True
).select_related('student', 'student__user')
```

### 3. Teacher Adds Student to Assignment
```python
assignment = TeacherSubjectAssignment.objects.get(id=assignment_id)
student = StudentProfile.objects.get(id=student_id)

# System will validate:
# - student.section == assignment.section
# - student.year_level == assignment.section.year_level
# - No duplicate enrollment

enrollment = StudentEnrollment.objects.create(
    student=student,
    assignment=assignment
)
```

### 4. Get Students Available for Enrollment (Same Section)
```python
assignment = TeacherSubjectAssignment.objects.get(id=assignment_id)
available_students = StudentProfile.objects.filter(
    section=assignment.section,
    year_level=assignment.section.year_level
).exclude(
    enrollments__assignment=assignment,
    enrollments__is_active=True
)
```

### 5. Check Teacher Permission
```python
assignment = TeacherSubjectAssignment.objects.get(id=assignment_id)
teacher_profile = TeacherProfile.objects.get(user=request.user)

if assignment.can_teacher_manage(teacher_profile):
    # Teacher can manage this assignment
    pass
```

### 6. Record Attendance
```python
enrollment = StudentEnrollment.objects.get(id=enrollment_id)
attendance = Attendance.objects.create(
    enrollment=enrollment,
    date=date.today(),
    status='present'
)
```

### 7. Record Grade
```python
enrollment = StudentEnrollment.objects.get(id=enrollment_id)
grade = Grade.objects.create(
    enrollment=enrollment,
    term='Midterm',
    grade=85.5
)
```

### 8. Create Assessment
```python
assignment = TeacherSubjectAssignment.objects.get(id=assignment_id)
assessment = Assessment.objects.create(
    name='Quiz 1',
    category='Quizzes',
    assignment=assignment,
    max_score=100,
    date=date.today(),
    term='Midterm',
    created_by=teacher_profile
)
```

### 9. Record Assessment Score
```python
enrollment = StudentEnrollment.objects.get(id=enrollment_id)
assessment = Assessment.objects.get(id=assessment_id)

# System will validate:
# - enrollment.assignment == assessment.assignment

score = AssessmentScore.objects.create(
    enrollment=enrollment,
    assessment=assessment,
    score=85,
    recorded_by=teacher_profile
)
```

### 10. Get Student's Enrollments
```python
student = StudentProfile.objects.get(id=student_id)
enrollments = StudentEnrollment.objects.filter(
    student=student,
    is_active=True
).select_related('assignment', 'assignment__subject', 'assignment__section', 'assignment__teacher')
```

### 11. Get Student's Attendance for an Enrollment
```python
enrollment = StudentEnrollment.objects.get(id=enrollment_id)
attendances = Attendance.objects.filter(
    enrollment=enrollment
).order_by('-date')
```

### 12. Get Student's Grades for an Enrollment
```python
enrollment = StudentEnrollment.objects.get(id=enrollment_id)
grades = Grade.objects.filter(
    enrollment=enrollment
).order_by('term')
```

## 🔄 Backward Compatibility Properties

All models maintain backward compatibility through properties:

### StudentEnrollment
```python
enrollment.subject  # Returns assignment.subject
enrollment.section  # Returns assignment.section
enrollment.teacher  # Returns assignment.teacher
```

### Attendance
```python
attendance.student   # Returns enrollment.student
attendance.subject   # Returns enrollment.assignment.subject
attendance.assignment # Returns enrollment.assignment
```

### Grade
```python
grade.student   # Returns enrollment.student
grade.subject   # Returns enrollment.assignment.subject
grade.assignment # Returns enrollment.assignment
```

### Assessment
```python
assessment.subject  # Returns assignment.subject
assessment.section  # Returns assignment.section
```

### AssessmentScore
```python
score.student  # Returns enrollment.student
```

### CategoryWeights
```python
weights.subject  # Returns assignment.subject
```

## ⚠️ Important Notes

1. **Always use `assignment` not `subject`** when working with enrollments
2. **Validate section match** - Students can only enroll in assignments from their section
3. **Validate year level match** - Student's year level must match section's year level
4. **Use convenience properties** for backward compatibility in views/templates
5. **Check permissions** using `can_teacher_manage()` before allowing modifications

## 🎯 Query Patterns

### Get all subjects a teacher teaches
```python
assignments = TeacherSubjectAssignment.objects.filter(teacher=teacher_profile)
subjects = [a.subject for a in assignments]  # Or use distinct()
```

### Get all students in a teacher's assignment
```python
assignment = TeacherSubjectAssignment.objects.get(id=assignment_id)
students = StudentEnrollment.objects.filter(
    assignment=assignment,
    is_active=True
).values_list('student', flat=True)
```

### Get all assessments for a teacher's assignment
```python
assignment = TeacherSubjectAssignment.objects.get(id=assignment_id)
assessments = Assessment.objects.filter(assignment=assignment)
```

### Get all grades for a teacher's assignment
```python
assignment = TeacherSubjectAssignment.objects.get(id=assignment_id)
enrollments = StudentEnrollment.objects.filter(assignment=assignment)
grades = Grade.objects.filter(enrollment__in=enrollments)
```

