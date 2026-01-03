# Semester Management System - Complete Guide

## 📚 Overview

The Semester Management System provides a comprehensive way to organize academic data by semester, ensuring data integrity, proper lifecycle management, and automatic filtering of academic records.

---

## 🏗️ Semester Model Structure

### Core Fields

```python
class Semester(models.Model):
    name = CharField              # e.g., "1st Semester", "2nd Semester"
    academic_year = CharField     # e.g., "2025-2026"
    start_date = DateField        # Semester start date
    end_date = DateField          # Semester end date
    status = CharField            # Status: upcoming, active, closed, archived
    is_current = BooleanField     # Only one can be True at a time
    created_at = DateTimeField    # Auto-generated
    updated_at = DateTimeField    # Auto-updated
```

### Key Properties

- **Only ONE current semester** can exist at a time
- **Status lifecycle** is enforced: `Upcoming → Active → Closed → Archived`
- **Protected deletion** - cannot delete if related records exist

---

## 🔄 Semester Lifecycle & Statuses

### Status Flow

```
┌──────────┐
│ Upcoming │  ← New semester created
└────┬─────┘
     │ Set as Active
     ▼
┌──────────┐
│  Active  │  ← Current working semester
└────┬─────┘
     │ Close Semester
     ▼
┌──────────┐
│  Closed  │  ← Read-only, no new records
└────┬─────┘
     │ Archive
     ▼
┌──────────┐
│ Archived │  ← Permanent read-only
└──────────┘
```

### Status Meanings

| Status | Description | Permissions |
|--------|-------------|-------------|
| **Upcoming** | Future semester, not yet active | Can view, cannot enroll/record |
| **Active** | Current working semester | ✅ Enroll students<br>✅ Record attendance<br>✅ Edit grades<br>✅ Create assessments |
| **Closed** | Semester ended, locked | ❌ No new enrollments<br>❌ No new attendance<br>❌ No grade editing<br>✅ View only |
| **Archived** | Permanently archived | ❌ All operations disabled<br>✅ Historical view only |

---

## 🔗 Semester Relationships

### Direct Relationships

Semesters are directly linked to:

1. **TeacherSubjectAssignment** (Subject Offerings)
   ```python
   assignment.semester  # Which semester this subject is offered
   ```

2. **StudentEnrollment** (Student Enrollments)
   ```python
   enrollment.semester  # Which semester student is enrolled
   ```

### Derived Relationships

Semesters are **derived** from enrollment for:

3. **Attendance** (via enrollment)
   ```python
   attendance.enrollment.semester  # Derived, not stored
   # Access: attendance.semester (property)
   ```

4. **Grade** (via enrollment)
   ```python
   grade.enrollment.semester  # Derived, not stored
   # Access: grade.semester (property)
   ```

5. **Assessment** (via assignment)
   ```python
   assessment.assignment.semester  # Derived, not stored
   # Access: assessment.semester (property)
   ```

### Why This Design?

- **Normalized data** - No redundancy
- **Consistency** - Semester always matches enrollment/assignment
- **Data integrity** - Cannot have mismatched semesters

---

## 🎯 Getting the Current Semester

### Method 1: Class Method (Recommended)

```python
from core.models import Semester

# Get current active semester
current_semester = Semester.get_current()

if current_semester:
    print(f"Current: {current_semester.name} - {current_semester.academic_year}")
else:
    print("No active semester set")
```

### Method 2: Backward Compatible Function

```python
from core.models import get_current_semester

current_semester = get_current_semester()  # Wrapper for Semester.get_current()
```

### Method 3: Middleware (Optional)

If `SemesterMiddleware` is enabled in `settings.py`:

```python
# In views
def my_view(request):
    current_semester = request.semester  # Automatically injected
```

---

## 📝 Auto-Assignment Logic

### When Creating Records

**TeacherSubjectAssignment:**
```python
assignment = TeacherSubjectAssignment(
    teacher=teacher,
    subject=subject,
    section=section
    # semester not specified
)
assignment.save()  # Automatically assigns current semester
```

**StudentEnrollment:**
```python
enrollment = StudentEnrollment(
    student=student,
    assignment=assignment
    # semester not specified
)
enrollment.save()  
# 1. Tries to use assignment.semester
# 2. Falls back to current semester
# 3. Validates: enrollment.semester == assignment.semester
```

**Attendance & Grade:**
```python
attendance = Attendance(
    enrollment=enrollment,
    date=today,
    status='present'
)
# Semester automatically derived from enrollment.semester
# Access via: attendance.semester (property)
```

---

## ✅ Business Rules & Validations

### 1. Single Current Semester

```python
# Only one semester can be is_current=True
semester1.is_current = True
semester1.save()  # Automatically sets all others to False
```

### 2. Status Transition Validation

```python
# Valid transitions only
semester.status = 'upcoming'  # Can only go to 'active'
semester.status = 'active'     # Can only go to 'closed'
semester.status = 'closed'    # Can only go to 'archived'
semester.status = 'archived'  # Cannot change (permanent)
```

### 3. Semester Consistency

```python
# Enrollment semester MUST match assignment semester
enrollment.semester == enrollment.assignment.semester  # Enforced
```

### 4. Permission Checks

```python
if semester.can_enroll_students():
    # Allow enrollment
if semester.can_record_attendance():
    # Allow attendance recording
if semester.can_edit_grades():
    # Allow grade editing
if semester.is_read_only():
    # All operations disabled
```

### 5. Protected Deletion

```python
# Cannot delete if related records exist
try:
    semester.delete()
except ProtectedError:
    # Has related assignments, enrollments, etc.
    # Must archive instead
```

---

## 🔍 Filtering by Semester

### In Views

**Teacher Dashboard:**
```python
current_semester = Semester.get_current()

# Filter assignments by current semester
assignments = TeacherSubjectAssignment.objects.filter(
    teacher=teacher_profile
)
if current_semester:
    assignments = assignments.filter(semester=current_semester)
```

**Student Dashboard:**
```python
current_semester = Semester.get_current()

# Filter enrollments by current semester
enrollments = StudentEnrollment.objects.filter(
    student=student_profile,
    is_active=True
)
if current_semester:
    enrollments = enrollments.filter(semester=current_semester)
```

**Attendance & Grades:**
```python
# Filter through enrollment
attendance = Attendance.objects.filter(
    enrollment__student=student,
    enrollment__semester=current_semester
)

grades = Grade.objects.filter(
    enrollment__student=student,
    enrollment__semester=current_semester
)
```

---

## 🎨 Admin Interface

### Access Semester Management

**URL:** `/semesters/`

**Features:**
- View all semesters in table format
- Create new semester
- Set semester as active
- Close active semester
- Archive closed semester
- Color-coded status badges
- Current semester indicator

### Creating a Semester

1. Navigate to **Semester Management** (Admin sidebar)
2. Fill in the form:
   - **Name:** "1st Semester"
   - **Academic Year:** "2025-2026"
   - **Start Date:** Select date
   - **End Date:** Select date
   - **Status:** "Upcoming" or "Active"
3. Click **Create Semester**

### Setting Active Semester

1. Find the semester you want to activate
2. Click **Set as Active**
3. Confirms: "This will deactivate the current semester"
4. Previous current semester is automatically deactivated

### Closing a Semester

1. Find the active semester
2. Click **Close Semester**
3. Confirms: "This will prevent further enrollment, attendance, and grade editing"
4. Status changes to "Closed" (read-only)

### Archiving a Semester

1. Find a closed semester
2. Click **Archive Semester**
3. Confirms: "This is a permanent action"
4. Status changes to "Archived" (permanent read-only)

---

## 💻 Code Examples

### Example 1: Check if Semester Allows Operations

```python
from core.models import Semester

semester = Semester.get_current()

if semester:
    if semester.can_enroll_students():
        # Allow student enrollment
        pass
    
    if semester.can_record_attendance():
        # Allow attendance recording
        pass
    
    if semester.can_edit_grades():
        # Allow grade editing
        pass
    
    if semester.is_read_only():
        # Show read-only message
        pass
else:
    # No active semester - show warning
    pass
```

### Example 2: Get All Data for Current Semester

```python
from core.models import Semester, TeacherSubjectAssignment, StudentEnrollment

current_semester = Semester.get_current()

if current_semester:
    # Get all assignments for current semester
    assignments = TeacherSubjectAssignment.objects.filter(
        semester=current_semester
    )
    
    # Get all enrollments for current semester
    enrollments = StudentEnrollment.objects.filter(
        semester=current_semester,
        is_active=True
    )
    
    # Count students enrolled
    student_count = enrollments.values('student').distinct().count()
```

### Example 3: Validate Before Creating Record

```python
from core.models import Semester, StudentEnrollment
from django.core.exceptions import ValidationError

def enroll_student(student, assignment):
    current_semester = Semester.get_current()
    
    if not current_semester:
        raise ValidationError("No active semester. Please set an active semester first.")
    
    if not current_semester.can_enroll_students():
        raise ValidationError(
            f"Cannot enroll students in {current_semester.get_status_display()} semester."
        )
    
    enrollment = StudentEnrollment(
        student=student,
        assignment=assignment
        # semester will be auto-assigned
    )
    enrollment.save()
    return enrollment
```

### Example 4: Access Semester from Related Objects

```python
# From enrollment
enrollment = StudentEnrollment.objects.get(id=1)
semester = enrollment.semester  # Direct access

# From attendance (derived)
attendance = Attendance.objects.get(id=1)
semester = attendance.semester  # Property: enrollment.semester

# From grade (derived)
grade = Grade.objects.get(id=1)
semester = grade.semester  # Property: enrollment.semester

# From assessment (derived)
assessment = Assessment.objects.get(id=1)
semester = assessment.semester  # Property: assignment.semester
```

---

## 🚨 Common Scenarios

### Scenario 1: No Active Semester

**Problem:** System shows warning, no operations allowed

**Solution:**
```python
# Admin must create and activate a semester
semester = Semester.objects.create(
    name="1st Semester",
    academic_year="2025-2026",
    start_date=date(2025, 1, 1),
    end_date=date(2025, 5, 31),
    status='active',
    is_current=True
)
```

### Scenario 2: Semester Mismatch

**Problem:** Enrollment semester doesn't match assignment semester

**Solution:**
```python
# System automatically syncs on save
enrollment.assignment.semester = semester1
enrollment.semester = semester2  # Different!
enrollment.save()  # Automatically syncs to semester1
```

### Scenario 3: Trying to Edit Closed Semester

**Problem:** Cannot edit grades for closed semester

**Solution:**
```python
if grade.semester.can_edit_grades():
    grade.grade = new_grade
    grade.save()
else:
    raise ValidationError("Cannot edit grades for closed semester")
```

---

## 📊 Dashboard Integration

### Admin Dashboard

- Shows current semester banner
- Warning if no active semester
- Quick link to semester management

### Teacher Dashboard

- Filters all data by current semester
- Shows subjects for current semester only
- Disables actions if semester is closed

### Student Dashboard

- Shows enrollments for current semester
- Filters grades by current semester
- Filters attendance by current semester

---

## 🔐 Security & Data Integrity

### Protection Mechanisms

1. **Single Current Semester** - Enforced at model level
2. **Status Transitions** - Validated in `clean()`
3. **Semester Consistency** - Validated in `StudentEnrollment.clean()`
4. **Protected Deletion** - Cannot delete if related records exist
5. **Permission Checks** - Status-based operation restrictions

### Data Integrity

- Semester always matches between assignment and enrollment
- Attendance/Grade semester derived from enrollment (no redundancy)
- Historical data preserved (archived semesters)

---

## 📝 Summary

**Key Points:**

1. ✅ **One current semester** at a time
2. ✅ **Status lifecycle** enforced (Upcoming → Active → Closed → Archived)
3. ✅ **Auto-assignment** of current semester to new records
4. ✅ **Derived relationships** for Attendance/Grade (no redundancy)
5. ✅ **Consistency validation** between assignment and enrollment
6. ✅ **Permission checks** based on semester status
7. ✅ **Protected deletion** prevents data loss
8. ✅ **Admin interface** for full semester management

**Best Practices:**

- Always use `Semester.get_current()` to get current semester
- Check `semester.can_*()` methods before operations
- Filter queries by current semester for dashboards
- Use properties (`attendance.semester`) for derived relationships
- Archive semesters instead of deleting them

---

**For more details, see:**
- `SEMESTER_MANAGEMENT_IMPLEMENTATION.md` - Implementation details
- `MODEL_REFACTORING_SUMMARY.md` - Recent refactoring changes

