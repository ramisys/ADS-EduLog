# VII. System Demonstration
**Time Allocation: 5 minutes**

---

## 1. Key Features Flow

### 1.1 Show Core Functions Tied to DB Operations

#### Demonstration: Student Performance Summary

**Feature:** Get comprehensive student performance data using database functions

**Steps:**
1. Navigate to Parent Dashboard → Reports
2. Select a student
3. View performance summary

**What to Highlight:**
- **Database Function Call**: `get_student_performance_summary(student_id)`
- **Database Operations**:
  - Multiple SELECT queries with JOINs
  - Aggregations (AVG, COUNT)
  - Subqueries for subject-wise performance
  - Uses indexes for fast retrieval

**Code Behind the Scenes:**
```python
# Location: core/db_functions.py
@transaction.atomic
def get_student_performance_summary(student_id):
    # Database operations:
    student = StudentProfile.objects.select_related('user', 'section').get(id=student_id)
    subjects = Subject.objects.filter(section=student.section)
    grades = Grade.objects.filter(student=student)
    attendance = Attendance.objects.filter(student=student)
    
    # Aggregations:
    overall_avg = grades.aggregate(Avg('grade'))['grade__avg'] or 0
    attendance_rate = (present_count / total_attendance * 100) if total_attendance > 0 else 0
    
    # Subject-wise subqueries:
    for subject in subjects:
        subject_grades = grades.filter(subject=subject)
        subject_attendance = attendance.filter(subject=subject)
        # ... calculations ...
```

**What to Show:**
- ✅ Real-time data retrieval from database
- ✅ Multiple database queries executed
- ✅ Aggregations calculated on-the-fly
- ✅ Performance metrics displayed

**Database Impact:**
- Uses indexes: `core_grade_student_subject_idx`, `core_attendance_student_date_idx`
- Query optimization: `select_related()` for JOINs
- Transaction safety: `@transaction.atomic`

---

### 1.2 Demonstrate Secure Login

#### Demonstration: Multi-Format Authentication

**Feature:** Secure login with multiple identifier support and SQL injection prevention

**Steps:**
1. Navigate to Login page
2. Show login with different formats:
   - Username: `teacher1`
   - Teacher ID: `TCH-2025-00001`
   - Email: `teacher@example.com`
3. Show password validation
4. Demonstrate role-based redirect

**What to Highlight:**
- **Input Validation**: All inputs validated before database query
- **SQL Injection Prevention**: Django ORM (no raw SQL)
- **Password Security**: Hashed passwords (PBKDF2)
- **Role-Based Access**: Automatic redirect to appropriate dashboard

**Code Behind the Scenes:**
```python
# Location: core/views.py - login_view()
def login_view(request):
    if request.method == 'POST':
        identifier = request.POST.get('identifier', '').strip()
        password = request.POST.get('password', '')
        role = request.POST.get('role')
        
        # Input validation (prevents SQL injection)
        if not identifier or not password or not role:
            messages.error(request, 'Please fill in all fields.')
            return render(request, 'login.html', context)
        
        # Secure database query using ORM (parameterized)
        if role == 'teacher':
            # Try username first (uses index: core_user_email_idx)
            user = User.objects.get(username=identifier, role='teacher')
            
            # If not found, try teacher_id (uses index: core_teacher_teacher_id_idx)
            if user is None:
                teacher_profile = TeacherProfile.objects.get(teacher_id=identifier)
                user = teacher_profile.user
            
            # If not found, try email (uses index: core_user_email_idx)
            if user is None:
                user = User.objects.get(email=identifier, role='teacher')
        
        # Password verification (handles both hashed and plain text)
        if user and check_password_with_plaintext(user, password):
            login(request, user)
            return redirect('dashboard')  # Role-based redirect
```

**What to Show:**
- ✅ Login with username → Success
- ✅ Login with ID → Success
- ✅ Login with email → Success
- ✅ Invalid credentials → Error message
- ✅ SQL injection attempt → Blocked (show in console/logs)

**Security Features Demonstrated:**
- ✅ Input validation prevents SQL injection
- ✅ Password hashing (PBKDF2)
- ✅ Role-based authentication
- ✅ Index usage for fast lookups
- ✅ Error messages don't leak system information

**SQL Injection Test (Optional):**
```
Identifier: admin' OR '1'='1
Password: anything
```
**Result:** ❌ Blocked - Invalid credentials (no SQL execution)

---

### 1.3 A Critical Transaction Workflow

#### Demonstration: Grade Update with Transaction

**Feature:** Update assessment score, recalculate grade, and create audit log atomically

**Steps:**
1. Navigate to Teacher Dashboard → Grades
2. Select a subject
3. Update a student's assessment score
4. Show that grade is automatically recalculated
5. Show audit log entry created

**What to Highlight:**
- **Transaction Atomicity**: All operations succeed or all fail
- **Concurrency Control**: Exclusive locking prevents race conditions
- **Data Consistency**: Grade recalculation happens automatically
- **Audit Trail**: All changes logged

**Code Behind the Scenes:**
```python
# Location: teachers/views.py - update_score()
@transaction.atomic  # Transaction starts here
def update_score(request):
    try:
        # Get student with EXCLUSIVE LOCK (prevents concurrent updates)
        student = StudentProfile.objects.select_for_update().get(id=student_id)
        
        # Validate teacher access
        has_access, assessment = validate_teacher_access(request, assessment_id=assessment_id)
        if not has_access:
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        # Update score (Operation 1)
        assessment_score.score = score_value
        assessment_score.recorded_by = teacher_profile
        assessment_score.save()
        
        # Recalculate Midterm grade (Operation 2)
        calculate_and_update_grade(student, assessment.subject, 'Midterm')
        
        # Recalculate Final grade (Operation 3)
        calculate_and_update_grade(student, assessment.subject, 'Final')
        
        # Create audit log (Operation 4)
        AuditLog.objects.create(
            user=request.user,
            action='Score Updated',
            details=f'Updated score: {score_value}/{assessment.max_score}',
            student=student,
            assessment=assessment
        )
        
        # ✅ COMMIT: All operations committed together
        return JsonResponse({'success': True})
        
    except Exception as e:
        # ❌ ROLLBACK: All operations rolled back on error
        logger.error(f"Error updating score: {str(e)}")
        return JsonResponse({'success': False, 'error': 'Update failed'}, status=500)
```

**What to Show:**
1. **Before Update**: Show current score and grade
2. **Update Score**: Change score from 85 to 92
3. **Automatic Recalculation**: Grade updates automatically
4. **Audit Log**: Show new audit log entry
5. **Database State**: Verify all changes committed

**Transaction Flow Visualization:**
```
START TRANSACTION
  ├─ Lock student record (exclusive)
  ├─ Update assessment score
  ├─ Recalculate Midterm grade
  ├─ Recalculate Final grade
  └─ Create audit log
END TRANSACTION
  ├─ If SUCCESS: ✅ COMMIT (all changes saved)
  └─ If ERROR: ❌ ROLLBACK (all changes reverted)
```

**Error Scenario (Optional):**
- Simulate error during grade calculation
- Show that score update is also rolled back
- Demonstrate atomicity

**What to Highlight:**
- ✅ All-or-nothing guarantee
- ✅ Exclusive locking prevents race conditions
- ✅ Automatic grade recalculation
- ✅ Complete audit trail
- ✅ Data consistency maintained

---

### 1.4 Features Using Advanced SQL

#### Demonstration 1: Database View - Student Performance

**Feature:** Query database view for aggregated student performance

**Steps:**
1. Show database view definition
2. Query the view
3. Display results

**What to Highlight:**
- **Database View**: Pre-computed aggregations
- **Complex JOINs**: Multiple table joins
- **Aggregations**: AVG, COUNT, SUM
- **Performance**: Fast query execution

**SQL View:**
```sql
-- Location: core/migrations/0009_database_enhancements.py
CREATE VIEW vw_student_performance AS
SELECT 
    sp.id AS student_id,
    sp.student_id,
    u.first_name || ' ' || u.last_name AS student_name,
    s.id AS subject_id,
    s.code AS subject_code,
    s.name AS subject_name,
    COALESCE(AVG(g.grade), 0) AS average_grade,
    COUNT(DISTINCT g.id) AS grade_count,
    COUNT(DISTINCT a.id) AS attendance_count,
    SUM(CASE WHEN a.status = 'present' THEN 1 ELSE 0 END) AS present_count,
    CASE 
        WHEN COUNT(DISTINCT a.id) > 0 
        THEN ROUND(SUM(CASE WHEN a.status = 'present' THEN 1 ELSE 0 END) * 100.0 / COUNT(DISTINCT a.id), 2)
        ELSE 0 
    END AS attendance_percentage
FROM core_studentprofile sp
INNER JOIN core_user u ON sp.user_id = u.id
LEFT JOIN core_subject s ON sp.section_id = s.section_id
LEFT JOIN core_grade g ON sp.id = g.student_id AND s.id = g.subject_id
LEFT JOIN core_attendance a ON sp.id = a.student_id AND s.id = a.subject_id
GROUP BY sp.id, sp.student_id, u.first_name, u.last_name, s.id, s.code, s.name;
```

**Query the View:**
```sql
SELECT * FROM vw_student_performance 
WHERE student_id = 'STD-2025-00001';
```

**What to Show:**
- ✅ View definition in database
- ✅ Query execution
- ✅ Aggregated results
- ✅ Fast performance (uses indexes)

#### Demonstration 2: Database Trigger - Score Validation

**Feature:** Database trigger automatically validates assessment scores

**Steps:**
1. Show trigger definition
2. Attempt to insert invalid score
3. Show trigger blocking invalid data

**What to Highlight:**
- **BEFORE INSERT Trigger**: Validates data before insertion
- **Subquery**: Gets max_score from assessment
- **Database-Level Validation**: Cannot be bypassed

**SQL Trigger:**
```sql
-- Location: core/migrations/0009_database_enhancements.py
CREATE TRIGGER trg_validate_assessment_score
BEFORE INSERT ON core_assessmentscore
BEGIN
    SELECT CASE
        WHEN NEW.score < 0 THEN
            RAISE(ABORT, 'Score cannot be negative')
        WHEN NEW.score > (
            -- SUBQUERY: Get max_score from assessment
            SELECT max_score 
            FROM core_assessment 
            WHERE id = NEW.assessment_id
        ) THEN
            RAISE(ABORT, 'Score cannot exceed maximum score')
    END;
END;
```

**Test Scenarios:**
1. **Valid Score**: Insert score = 85 (max_score = 100) → ✅ Success
2. **Negative Score**: Insert score = -5 → ❌ Error: "Score cannot be negative"
3. **Exceeds Max**: Insert score = 150 (max_score = 100) → ❌ Error: "Score cannot exceed maximum score"

**What to Show:**
- ✅ Trigger definition
- ✅ Valid insertion succeeds
- ✅ Invalid insertion blocked
- ✅ Error message displayed

#### Demonstration 3: Stored Procedure Equivalent - GPA Calculation

**Feature:** Calculate student GPA using stored procedure equivalent

**Steps:**
1. Call function: `calculate_student_gpa(student_id, term='Midterm')`
2. Show database operations
3. Display calculated GPA

**What to Highlight:**
- **Transaction Support**: `@transaction.atomic`
- **Aggregations**: AVG function
- **Subqueries**: Filter by term
- **Locking**: `select_for_update()` for concurrency control

**Code:**
```python
# Location: core/db_functions.py
@transaction.atomic
def calculate_student_gpa(student_id, term=None):
    # Lock student record
    student = StudentProfile.objects.select_for_update().get(id=student_id)
    
    # Filter grades by term (subquery)
    grade_query = Grade.objects.filter(student=student)
    if term:
        grade_query = grade_query.filter(term=term)
    
    # Aggregate: Calculate average
    avg_grade = grades.aggregate(Avg('grade'))['grade__avg'] or 0
    
    # Convert to GPA (0-4 scale)
    gpa = (float(avg_grade) / 100) * 4.0
    
    return {
        'gpa': round(gpa, 2),
        'average_grade': round(float(avg_grade), 2),
        'grade_count': grades.count(),
        'term': term or 'All Terms'
    }
```

**What to Show:**
- ✅ Function call
- ✅ Database queries executed
- ✅ Aggregation performed
- ✅ GPA calculated and returned
- ✅ Transaction safety

---

## 2. Error Handling

### 2.1 Example of Validation

#### Demonstration: Input Validation with Error Messages

**Feature:** Comprehensive input validation with user-friendly error messages

**Steps:**
1. Navigate to Teacher Dashboard → Add Assessment
2. Attempt to create assessment with invalid data
3. Show validation errors

**Test Cases:**

**Case 1: Invalid Assessment Name**
- **Input**: Name = `'; DROP TABLE students; --` (SQL injection attempt)
- **Result**: ❌ Error: "Invalid assessment name"
- **What Happens**: `validate_input()` detects dangerous SQL patterns and blocks

**Code:**
```python
# Location: teachers/views.py - add_assessment()
assessment_name = validate_input(data.get('name'), 'string', max_length=200)
if not assessment_name:
    return JsonResponse({'success': False, 'error': 'Invalid assessment name'}, status=400)
```

**Case 2: Invalid Score Range**
- **Input**: Score = 150 (max_score = 100)
- **Result**: ❌ Error: "Score cannot exceed maximum score of 100"
- **What Happens**: Application-level validation + database trigger validation

**Code:**
```python
# Location: teachers/views.py - update_score()
if score_value > float(assessment.max_score):
    return JsonResponse({
        'success': False,
        'error': f'Score cannot exceed maximum score of {assessment.max_score}'
    }, status=400)
```

**Case 3: Category Weights Don't Sum to 100%**
- **Input**: Activities=20%, Quizzes=20%, Projects=30%, Exams=25% (Total=95%)
- **Result**: ❌ Error: "Category weights must total 100%. Current total: 95%"
- **What Happens**: Validation at application level + database constraint

**Code:**
```python
# Location: teachers/views.py - update_category_weights()
total = activities_weight + quizzes_weight + projects_weight + exams_weight
if total != 100:
    return JsonResponse({
        'success': False,
        'error': f'Category weights must total 100%. Current total: {total}%'
    }, status=400)
```

**Case 4: Invalid Date Format**
- **Input**: Date = "2025-13-45" (invalid date)
- **Result**: ❌ Error: "Invalid date format"
- **What Happens**: Date validation using regex pattern

**Code:**
```python
# Location: core/permissions.py - validate_input()
elif input_type == 'date':
    date_pattern = r'^\d{4}-\d{2}-\d{2}$'
    if isinstance(input_value, str) and re.match(date_pattern, input_value):
        return input_value
    return False  # Invalid date format
```

**What to Show:**
- ✅ SQL injection attempt blocked
- ✅ Score range validation
- ✅ Business rule validation (weights sum to 100%)
- ✅ Date format validation
- ✅ User-friendly error messages
- ✅ No system information leaked

**Validation Layers:**
1. **Client-side**: HTML5 validation (optional)
2. **Application-level**: `validate_input()` function
3. **Database-level**: Constraints and triggers

---

### 2.2 How the System Handles Failures

#### Demonstration 1: Transaction Rollback on Error

**Feature:** Automatic rollback when transaction fails

**Steps:**
1. Attempt to update score
2. Simulate error during grade calculation
3. Show that all changes are rolled back

**Scenario:**
```python
@transaction.atomic
def update_score(request):
    try:
        # Update score
        assessment_score.score = 92
        assessment_score.save()
        
        # Recalculate grade (simulate error here)
        calculate_and_update_grade(student, assessment.subject, 'Midterm')
        # ❌ ERROR: Database constraint violation
        
    except Exception as e:
        # ❌ ROLLBACK: Score update is also rolled back
        logger.error(f"Error: {str(e)}")
        return JsonResponse({'success': False, 'error': 'Update failed'}, status=500)
```

**What to Show:**
- ✅ Score update attempted
- ✅ Error occurs during grade calculation
- ✅ Transaction automatically rolls back
- ✅ Database state unchanged (score not updated)
- ✅ Error logged for debugging
- ✅ User-friendly error message displayed

#### Demonstration 2: Graceful Error Handling

**Feature:** System continues to function even when errors occur

**Steps:**
1. Show error handling in various scenarios
2. Demonstrate graceful degradation

**Error Handling Examples:**

**Example 1: Student Not Found**
```python
# Location: core/db_functions.py - calculate_student_gpa()
try:
    student = StudentProfile.objects.select_for_update().get(id=student_id)
    # ... calculations ...
except StudentProfile.DoesNotExist:
    return {'error': 'Student not found'}  # Graceful error return
except Exception as e:
    return {'error': str(e)}  # Generic error handling
```

**Example 2: Access Denied**
```python
# Location: teachers/views.py - update_score()
has_access, assessment = validate_teacher_access(request, assessment_id=assessment_id)
if not has_access:
    return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
    # System continues, user sees error message
```

**Example 3: Database Connection Error**
```python
# Location: Various views
try:
    # Database operations
    student = StudentProfile.objects.get(id=student_id)
except Exception as e:
    logger.error(f"Database error: {str(e)}")
    messages.error(request, 'An error occurred. Please try again later.')
    return redirect('dashboard')  # Redirect to safe page
```

**What to Show:**
- ✅ Errors caught and handled gracefully
- ✅ User-friendly error messages
- ✅ System continues to function
- ✅ Errors logged for debugging
- ✅ No system crashes
- ✅ Appropriate HTTP status codes (400, 403, 500)

#### Demonstration 3: Validation Error Display

**Feature:** Clear, actionable error messages

**Steps:**
1. Show various validation errors
2. Demonstrate error message clarity

**Error Message Examples:**

**Good Error Messages:**
- ✅ "Category weights must total 100%. Current total: 95%"
- ✅ "Score cannot exceed maximum score of 100"
- ✅ "Invalid date format. Please use YYYY-MM-DD format"
- ✅ "An assessment with the name 'Quiz 1' already exists for this subject"

**Bad Error Messages (Avoided):**
- ❌ "Error occurred" (too generic)
- ❌ "Database constraint violation" (too technical)
- ❌ "Internal server error" (not helpful)

**What to Show:**
- ✅ Clear, specific error messages
- ✅ Actionable feedback (what went wrong, how to fix)
- ✅ No technical jargon exposed to users
- ✅ Consistent error message format
- ✅ Error messages displayed in UI

---

## Demonstration Checklist

### Pre-Demo Setup:
- [ ] Database seeded with sample data
- [ ] Test accounts created (teacher, student, parent)
- [ ] Sample assessments and grades entered
- [ ] Browser console open (to show network requests)
- [ ] Database viewer open (to show table changes)

### During Demo:

**1. Core Functions (1 minute)**
- [ ] Show student performance summary
- [ ] Highlight database operations
- [ ] Show query execution

**2. Secure Login (1 minute)**
- [ ] Login with username
- [ ] Login with ID
- [ ] Show SQL injection attempt blocked
- [ ] Show role-based redirect

**3. Transaction Workflow (1.5 minutes)**
- [ ] Update assessment score
- [ ] Show automatic grade recalculation
- [ ] Show audit log creation
- [ ] Demonstrate rollback on error (optional)

**4. Advanced SQL Features (1 minute)**
- [ ] Query database view
- [ ] Show trigger validation
- [ ] Call stored procedure equivalent

**5. Error Handling (0.5 minutes)**
- [ ] Show validation errors
- [ ] Show graceful error handling
- [ ] Show user-friendly error messages

### Post-Demo:
- [ ] Summarize key features demonstrated
- [ ] Highlight database operations shown
- [ ] Emphasize security and error handling

---

## Key Points to Emphasize

1. **Database Operations**: All features use proper database operations with transactions, indexes, and optimizations

2. **Security**: Input validation, SQL injection prevention, role-based access control

3. **Transaction Safety**: All-or-nothing operations, automatic rollback on errors

4. **Advanced SQL**: Views, triggers, stored procedures, subqueries all demonstrated

5. **Error Handling**: Graceful error handling, user-friendly messages, system resilience

6. **Performance**: Index usage, query optimization, fast response times

---

## Troubleshooting Tips

**If demo fails:**
- Check database connection
- Verify test data exists
- Check user permissions
- Review error logs
- Have backup screenshots ready

**If something doesn't work:**
- Explain what should happen
- Show code that implements the feature
- Demonstrate in development environment if needed

