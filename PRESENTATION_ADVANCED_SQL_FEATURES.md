# IV. Advanced SQL Features
**Time Allocation: 4-5 minutes (15% of presentation)**

**Objective:** Present and explain real examples used in the system

---

## 1. Subqueries

### Definition
A subquery is a query nested inside another query, used to retrieve data that will be used in the main query as a condition or to compute values.

### Real Examples in EduLog System

#### Example 1: Subquery in Trigger (Grade Audit)
**Location:** `core/migrations/0009_database_enhancements.py` (lines 252-268)

**Purpose:** Automatically create audit log when a grade is inserted, using subquery to get teacher information.

```sql
CREATE TRIGGER IF NOT EXISTS trg_grade_audit
AFTER INSERT ON core_grade
BEGIN
    INSERT INTO core_auditlog (user_id, action, details, student_id, timestamp)
    VALUES (
        -- SUBQUERY: Get teacher's user_id from subject
        (SELECT user_id 
         FROM core_teacherprofile 
         WHERE id = (SELECT teacher_id 
                     FROM core_subject 
                     WHERE id = NEW.subject_id)),
        'Grade Updated',
        'Grade recorded: ' || NEW.grade || ' for student ID ' || 
        -- SUBQUERY: Get student_id string
        (SELECT student_id 
         FROM core_studentprofile 
         WHERE id = NEW.student_id) || ' in term ' || NEW.term,
        NEW.student_id,
        datetime('now')
    );
END;
```

**Explanation:**
- **Nested subqueries** retrieve teacher's user_id and student's student_id
- Executes automatically when a grade is inserted
- Ensures audit trail is created with correct user information

#### Example 2: Subquery in Trigger (Score Validation)
**Location:** `core/migrations/0009_database_enhancements.py` (lines 270-285)

**Purpose:** Validate that assessment score doesn't exceed maximum score using subquery.

```sql
CREATE TRIGGER IF NOT EXISTS trg_validate_assessment_score
BEFORE INSERT ON core_assessmentscore
BEGIN
    SELECT CASE
        WHEN NEW.score < 0 THEN
            RAISE(ABORT, 'Score cannot be negative')
        WHEN NEW.score > (
            -- SUBQUERY: Get max_score from related assessment
            SELECT max_score 
            FROM core_assessment 
            WHERE id = NEW.assessment_id
        ) THEN
            RAISE(ABORT, 'Score cannot exceed maximum score')
    END;
END;
```

**Explanation:**
- **Subquery** retrieves `max_score` from the related assessment
- Validates score range before insertion
- Prevents invalid data at database level

#### Example 3: Subquery in Python Function (Django ORM Equivalent)
**Location:** `core/db_functions.py` - `get_student_performance_summary()`

**Purpose:** Calculate student performance using subqueries for aggregations.

```python
def get_student_performance_summary(student_id):
    student = StudentProfile.objects.select_related('user', 'section').get(id=student_id)
    
    # Get all subjects for the student's section
    subjects = Subject.objects.filter(section=student.section)
    
    # Calculate overall GPA (subquery-like aggregation)
    grades = Grade.objects.filter(student=student)
    overall_avg = grades.aggregate(Avg('grade'))['grade__avg'] or 0
    
    # Calculate overall attendance (subquery-like aggregation)
    attendance = Attendance.objects.filter(student=student)
    total_attendance = attendance.count()
    present_count = attendance.filter(status='present').count()
    
    # Subject-wise performance (nested subqueries)
    for subject in subjects:
        subject_grades = grades.filter(subject=subject)  # Subquery
        subject_attendance = attendance.filter(subject=subject)  # Subquery
        subject_avg = subject_grades.aggregate(Avg('grade'))['grade__avg'] or 0
```

**SQL Equivalent:**
```sql
-- Subquery to get average grade per subject
SELECT 
    s.id,
    s.code,
    (SELECT AVG(grade) 
     FROM core_grade 
     WHERE student_id = ? AND subject_id = s.id) AS avg_grade,
    (SELECT COUNT(*) 
     FROM core_attendance 
     WHERE student_id = ? AND subject_id = s.id) AS attendance_count
FROM core_subject s
WHERE s.section_id = ?
```

---

## 2. Views

### Definition
A view is a virtual table based on the result of a SQL statement. It contains rows and columns like a real table, but doesn't store data physically.

### Real Examples in EduLog System

#### View 1: Student Performance View
**Location:** `core/migrations/0009_database_enhancements.py` (lines 166-196)

**Purpose:** Aggregate student grades and attendance by subject for quick performance analysis.

```sql
CREATE VIEW IF NOT EXISTS vw_student_performance AS
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
    SUM(CASE WHEN a.status = 'absent' THEN 1 ELSE 0 END) AS absent_count,
    SUM(CASE WHEN a.status = 'late' THEN 1 ELSE 0 END) AS late_count,
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

**Usage:**
```sql
-- Query the view like a regular table
SELECT * FROM vw_student_performance 
WHERE student_id = 'STD-2025-00001';
```

**Benefits:**
- Pre-computed aggregations (AVG, COUNT, SUM)
- Complex JOINs simplified into single view
- Reusable across multiple queries
- Performance optimization

#### View 2: Teacher Subject Statistics View
**Location:** `core/migrations/0009_database_enhancements.py` (lines 198-226)

**Purpose:** Provide comprehensive statistics for each teacher's subjects.

```sql
CREATE VIEW IF NOT EXISTS vw_teacher_subject_stats AS
SELECT 
    tp.id AS teacher_id,
    tp.teacher_id,
    u.first_name || ' ' || u.last_name AS teacher_name,
    s.id AS subject_id,
    s.code AS subject_code,
    s.name AS subject_name,
    cs.name AS section_name,
    COUNT(DISTINCT sp.id) AS student_count,
    COUNT(DISTINCT g.id) AS grade_count,
    COALESCE(AVG(g.grade), 0) AS average_grade,
    COUNT(DISTINCT a.id) AS attendance_count,
    SUM(CASE WHEN a.status = 'present' THEN 1 ELSE 0 END) AS present_count,
    SUM(CASE WHEN a.status = 'absent' THEN 1 ELSE 0 END) AS absent_count
FROM core_teacherprofile tp
INNER JOIN core_user u ON tp.user_id = u.id
INNER JOIN core_subject s ON tp.id = s.teacher_id
INNER JOIN core_classsection cs ON s.section_id = cs.id
LEFT JOIN core_studentprofile sp ON s.section_id = sp.section_id
LEFT JOIN core_grade g ON s.id = g.subject_id AND sp.id = g.student_id
LEFT JOIN core_attendance a ON s.id = a.subject_id AND sp.id = a.student_id
GROUP BY tp.id, tp.teacher_id, u.first_name, u.last_name, s.id, s.code, s.name, cs.name;
```

**Usage:**
```sql
-- Get statistics for a specific teacher
SELECT * FROM vw_teacher_subject_stats 
WHERE teacher_id = 'TCH-2025-00001';
```

**Features:**
- Multiple JOINs (INNER and LEFT)
- GROUP BY aggregations
- CASE statements for conditional counting
- COALESCE for handling NULL values

#### View 3: Attendance Summary View
**Location:** `core/migrations/0009_database_enhancements.py` (lines 228-248)

**Purpose:** Daily attendance summary by subject and section.

```sql
CREATE VIEW IF NOT EXISTS vw_attendance_summary AS
SELECT 
    DATE(a.date) AS attendance_date,
    s.id AS subject_id,
    s.code AS subject_code,
    s.name AS subject_name,
    cs.name AS section_name,
    COUNT(DISTINCT a.student_id) AS total_students,
    SUM(CASE WHEN a.status = 'present' THEN 1 ELSE 0 END) AS present_count,
    SUM(CASE WHEN a.status = 'absent' THEN 1 ELSE 0 END) AS absent_count,
    SUM(CASE WHEN a.status = 'late' THEN 1 ELSE 0 END) AS late_count,
    ROUND(SUM(CASE WHEN a.status = 'present' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS attendance_rate
FROM core_attendance a
INNER JOIN core_subject s ON a.subject_id = s.id
INNER JOIN core_classsection cs ON s.section_id = cs.id
GROUP BY DATE(a.date), s.id, s.code, s.name, cs.name;
```

**Usage:**
```sql
-- Get attendance summary for a specific date
SELECT * FROM vw_attendance_summary 
WHERE attendance_date = '2025-01-15';
```

**Features:**
- DATE() function for date grouping
- Calculated attendance rate percentage
- Multiple aggregate functions (COUNT, SUM, ROUND)

---

## 3. Stored Procedures (SPs)

### Definition
A stored procedure is a prepared SQL code that can be saved and reused. Since SQLite doesn't support stored procedures, we use Python functions that act as stored procedures with transaction support.

### Real Examples in EduLog System

#### Stored Procedure 1: Calculate Student GPA
**Location:** `core/db_functions.py` (lines 17-60)

**Purpose:** Calculate GPA for a student with transaction support.

```python
@transaction.atomic
def calculate_student_gpa(student_id, term=None):
    """
    Calculate GPA for a student (acts like a stored procedure).
    Uses transaction to ensure data consistency.
    """
    try:
        student = StudentProfile.objects.select_for_update().get(id=student_id)
        
        grade_query = Grade.objects.filter(student=student)
        if term:
            grade_query = grade_query.filter(term=term)
        
        grades = grade_query.select_related('subject')
        
        if not grades.exists():
            return {
                'gpa': 0.0,
                'average_grade': 0.0,
                'grade_count': 0,
                'term': term or 'All Terms'
            }
        
        avg_grade = grades.aggregate(Avg('grade'))['grade__avg'] or 0
        gpa = (float(avg_grade) / 100) * 4.0
        
        return {
            'gpa': round(gpa, 2),
            'average_grade': round(float(avg_grade), 2),
            'grade_count': grades.count(),
            'term': term or 'All Terms',
            'grades': list(grades.values('subject__code', 'subject__name', 'grade', 'term'))
        }
    except StudentProfile.DoesNotExist:
        return {'error': 'Student not found'}
```

**SQL Equivalent (if stored procedures were supported):**
```sql
CREATE PROCEDURE calculate_student_gpa(
    IN p_student_id INT,
    IN p_term VARCHAR(20)
)
BEGIN
    DECLARE v_avg_grade DECIMAL(5,2);
    DECLARE v_gpa DECIMAL(3,2);
    
    SELECT AVG(grade) INTO v_avg_grade
    FROM core_grade
    WHERE student_id = p_student_id
    AND (p_term IS NULL OR term = p_term);
    
    SET v_gpa = (v_avg_grade / 100) * 4.0;
    
    SELECT v_gpa AS gpa, v_avg_grade AS average_grade;
END;
```

**Usage:**
```python
result = calculate_student_gpa(student_id=1, term='Midterm')
# Returns: {'gpa': 3.5, 'average_grade': 87.5, 'grade_count': 5, ...}
```

#### Stored Procedure 2: Calculate Attendance Rate
**Location:** `core/db_functions.py` (lines 63-119)

**Purpose:** Calculate attendance statistics with date filtering.

```python
@transaction.atomic
def calculate_attendance_rate(student_id, subject_id=None, start_date=None, end_date=None):
    """
    Calculate attendance rate for a student (acts like a stored procedure).
    Uses transaction and proper date filtering.
    """
    try:
        student = StudentProfile.objects.select_for_update().get(id=student_id)
        
        attendance_query = Attendance.objects.filter(student=student)
        
        if subject_id:
            attendance_query = attendance_query.filter(subject_id=subject_id)
        
        if start_date:
            attendance_query = attendance_query.filter(date__gte=start_date)
        
        if end_date:
            attendance_query = attendance_query.filter(date__lte=end_date)
        
        total = attendance_query.count()
        
        if total == 0:
            return {
                'attendance_rate': 0.0,
                'present_count': 0,
                'absent_count': 0,
                'late_count': 0,
                'total_count': 0
            }
        
        present_count = attendance_query.filter(status='present').count()
        absent_count = attendance_query.filter(status='absent').count()
        late_count = attendance_query.filter(status='late').count()
        
        attendance_rate = (present_count / total) * 100
        
        return {
            'attendance_rate': round(attendance_rate, 2),
            'present_count': present_count,
            'absent_count': absent_count,
            'late_count': late_count,
            'total_count': total
        }
    except StudentProfile.DoesNotExist:
        return {'error': 'Student not found'}
```

**Features:**
- Transaction support (`@transaction.atomic`)
- Parameter filtering (subject_id, date range)
- Multiple aggregations (COUNT with filters)
- Percentage calculation

#### Stored Procedure 3: Get Student Performance Summary
**Location:** `core/db_functions.py` (lines 122-184)

**Purpose:** Comprehensive performance data using subqueries and aggregations.

```python
@transaction.atomic
def get_student_performance_summary(student_id):
    """
    Get comprehensive performance summary for a student.
    Uses subqueries and aggregations for efficient data retrieval.
    """
    student = StudentProfile.objects.select_related('user', 'section').get(id=student_id)
    
    # Get all subjects for the student's section
    subjects = Subject.objects.filter(section=student.section)
    
    # Calculate overall GPA (subquery-like)
    grades = Grade.objects.filter(student=student)
    overall_avg = grades.aggregate(Avg('grade'))['grade__avg'] or 0
    overall_gpa = (float(overall_avg) / 100) * 4.0 if overall_avg > 0 else 0.0
    
    # Calculate overall attendance (subquery-like)
    attendance = Attendance.objects.filter(student=student)
    total_attendance = attendance.count()
    present_count = attendance.filter(status='present').count()
    attendance_rate = (present_count / total_attendance * 100) if total_attendance > 0 else 0
    
    # Subject-wise performance (nested subqueries)
    subject_performance = []
    for subject in subjects:
        subject_grades = grades.filter(subject=subject)
        subject_attendance = attendance.filter(subject=subject)
        
        subject_avg = subject_grades.aggregate(Avg('grade'))['grade__avg'] or 0
        subject_attendance_count = subject_attendance.count()
        subject_present = subject_attendance.filter(status='present').count()
        subject_attendance_rate = (subject_present / subject_attendance_count * 100) if subject_attendance_count > 0 else 0
        
        subject_performance.append({
            'subject_id': subject.id,
            'subject_code': subject.code,
            'subject_name': subject.name,
            'average_grade': round(float(subject_avg), 2),
            'attendance_rate': round(subject_attendance_rate, 2),
            'grade_count': subject_grades.count(),
            'attendance_count': subject_attendance_count
        })
    
    return {
        'student_id': student.student_id,
        'student_name': student.user.get_full_name(),
        'overall_gpa': round(overall_gpa, 2),
        'overall_average_grade': round(float(overall_avg), 2),
        'overall_attendance_rate': round(attendance_rate, 2),
        'total_subjects': subjects.count(),
        'subject_performance': subject_performance
    }
```

**Features:**
- Multiple subqueries for different aggregations
- Nested loops with subqueries
- Complex data structure returned
- Transaction safety

#### Stored Procedure 4: Get Teacher Class Statistics
**Location:** `core/db_functions.py` (lines 187-261)

**Purpose:** Teacher statistics with complex aggregations and at-risk student detection.

```python
@transaction.atomic
def get_teacher_class_statistics(teacher_id, subject_id=None):
    """
    Get statistics for a teacher's class.
    Uses complex aggregations and subqueries.
    """
    teacher = TeacherProfile.objects.select_related('user').get(id=teacher_id)
    
    subjects_query = Subject.objects.filter(teacher=teacher)
    if subject_id:
        subjects_query = subjects_query.filter(id=subject_id)
    
    subjects = subjects_query.select_related('section')
    
    statistics = []
    for subject in subjects:
        # Get students in this subject's section
        students = StudentProfile.objects.filter(section=subject.section)
        
        # Calculate average grade for this subject
        grades = Grade.objects.filter(subject=subject, student__in=students)
        avg_grade = grades.aggregate(Avg('grade'))['grade__avg'] or 0
        
        # Calculate attendance statistics
        attendance = Attendance.objects.filter(subject=subject, student__in=students)
        total_attendance = attendance.count()
        present_count = attendance.filter(status='present').count()
        attendance_rate = (present_count / total_attendance * 100) if total_attendance > 0 else 0
        
        # Count students at risk (GPA < 75 or attendance < 70%)
        at_risk_count = 0
        for student in students:
            student_grades = grades.filter(student=student)
            student_attendance = attendance.filter(student=student)
            
            if student_grades.exists():
                student_avg = student_grades.aggregate(Avg('grade'))['grade__avg'] or 0
            else:
                student_avg = 0
            
            student_attendance_count = student_attendance.count()
            student_present = student_attendance.filter(status='present').count()
            student_attendance_rate = (student_present / student_attendance_count * 100) if student_attendance_count > 0 else 0
            
            if student_avg < 75 or student_attendance_rate < 70:
                at_risk_count += 1
        
        statistics.append({
            'subject_id': subject.id,
            'subject_code': subject.code,
            'subject_name': subject.name,
            'section_name': subject.section.name if subject.section else 'N/A',
            'student_count': students.count(),
            'average_grade': round(float(avg_grade), 2),
            'attendance_rate': round(attendance_rate, 2),
            'at_risk_students': at_risk_count
        })
    
    return {
        'teacher_id': teacher.teacher_id,
        'teacher_name': teacher.user.get_full_name(),
        'statistics': statistics
    }
```

**Features:**
- Complex nested subqueries
- Business logic (at-risk student detection)
- Multiple aggregations per subject
- Transaction support

#### Stored Procedure 5: Check Consecutive Absences
**Location:** `core/db_functions.py` (lines 264-312)

**Purpose:** Check for consecutive absences using date logic.

```python
def check_consecutive_absences_stored(student_id, subject_id, threshold=3):
    """
    Check for consecutive absences (acts like a stored procedure).
    Uses window functions concept via Django ORM.
    """
    try:
        student = StudentProfile.objects.get(id=student_id)
        subject = Subject.objects.get(id=subject_id)
        
        # Get recent attendance records ordered by date
        attendance_records = Attendance.objects.filter(
            student=student,
            subject=subject,
            status='absent'
        ).order_by('-date')[:threshold]
        
        if attendance_records.count() < threshold:
            return {
                'has_consecutive_absences': False,
                'consecutive_count': attendance_records.count()
            }
        
        # Check if dates are consecutive
        dates = [record.date for record in attendance_records]
        dates.sort()
        
        consecutive = True
        for i in range(len(dates) - 1):
            if (dates[i+1] - dates[i]).days != 1:
                consecutive = False
                break
        
        return {
            'has_consecutive_absences': consecutive,
            'consecutive_count': threshold if consecutive else attendance_records.count(),
            'dates': [d.isoformat() for d in dates] if consecutive else []
        }
    except (StudentProfile.DoesNotExist, Subject.DoesNotExist):
        return {'error': 'Student or Subject not found'}
```

**Features:**
- Date-based logic
- Consecutive date checking
- Threshold-based detection
- Returns structured data

---

## 4. Triggers

### Definition
A trigger is a stored procedure that automatically executes when a specific event occurs in the database (INSERT, UPDATE, DELETE).

### Real Examples in EduLog System

#### Trigger 1: Grade Audit Trigger (AFTER INSERT)
**Location:** `core/migrations/0009_database_enhancements.py` (lines 252-268)

**Purpose:** Automatically create audit log entry when a grade is inserted.

```sql
CREATE TRIGGER IF NOT EXISTS trg_grade_audit
AFTER INSERT ON core_grade
BEGIN
    INSERT INTO core_auditlog (user_id, action, details, student_id, timestamp)
    VALUES (
        (SELECT user_id 
         FROM core_teacherprofile 
         WHERE id = (SELECT teacher_id 
                     FROM core_subject 
                     WHERE id = NEW.subject_id)),
        'Grade Updated',
        'Grade recorded: ' || NEW.grade || ' for student ID ' || 
        (SELECT student_id 
         FROM core_studentprofile 
         WHERE id = NEW.student_id) || ' in term ' || NEW.term,
        NEW.student_id,
        datetime('now')
    );
END;
```

**How it works:**
1. **Trigger Event:** AFTER INSERT on `core_grade` table
2. **Action:** Automatically inserts audit log entry
3. **Uses:** Subqueries to get teacher and student information
4. **Result:** Every grade insertion is automatically logged

**Demonstration:**
```sql
-- When this INSERT happens:
INSERT INTO core_grade (student_id, subject_id, term, grade)
VALUES (1, 5, 'Midterm', 85.5);

-- Trigger automatically executes:
-- Creates audit log entry with teacher info, student info, and timestamp
```

#### Trigger 2: Assessment Score Validation (BEFORE INSERT)
**Location:** `core/migrations/0009_database_enhancements.py` (lines 270-285)

**Purpose:** Validate score range before insertion to prevent invalid data.

```sql
CREATE TRIGGER IF NOT EXISTS trg_validate_assessment_score
BEFORE INSERT ON core_assessmentscore
BEGIN
    SELECT CASE
        WHEN NEW.score < 0 THEN
            RAISE(ABORT, 'Score cannot be negative')
        WHEN NEW.score > (SELECT max_score 
                          FROM core_assessment 
                          WHERE id = NEW.assessment_id) THEN
            RAISE(ABORT, 'Score cannot exceed maximum score')
    END;
END;
```

**How it works:**
1. **Trigger Event:** BEFORE INSERT on `core_assessmentscore` table
2. **Action:** Validates score before insertion
3. **Uses:** Subquery to get max_score from assessment
4. **Result:** Invalid scores are rejected at database level

**Demonstration:**
```sql
-- Valid insertion (score = 85, max_score = 100):
INSERT INTO core_assessmentscore (student_id, assessment_id, score)
VALUES (1, 10, 85);
-- ✅ SUCCESS: Insertion proceeds

-- Invalid insertion (score = 150, max_score = 100):
INSERT INTO core_assessmentscore (student_id, assessment_id, score)
VALUES (1, 10, 150);
-- ❌ ERROR: "Score cannot exceed maximum score" - Insertion aborted
```

#### Trigger 3: Assessment Score Update Validation (BEFORE UPDATE)
**Location:** `core/migrations/0009_database_enhancements.py` (lines 287-302)

**Purpose:** Validate score range before update to ensure data integrity.

```sql
CREATE TRIGGER IF NOT EXISTS trg_validate_assessment_score_update
BEFORE UPDATE ON core_assessmentscore
BEGIN
    SELECT CASE
        WHEN NEW.score < 0 THEN
            RAISE(ABORT, 'Score cannot be negative')
        WHEN NEW.score > (SELECT max_score 
                          FROM core_assessment 
                          WHERE id = NEW.assessment_id) THEN
            RAISE(ABORT, 'Score cannot exceed maximum score')
    END;
END;
```

**How it works:**
1. **Trigger Event:** BEFORE UPDATE on `core_assessmentscore` table
2. **Action:** Validates score before update
3. **Uses:** Same validation logic as INSERT trigger
4. **Result:** Ensures data integrity on updates

**Demonstration:**
```sql
-- Valid update:
UPDATE core_assessmentscore 
SET score = 90 
WHERE id = 1;
-- ✅ SUCCESS: Update proceeds

-- Invalid update (score = -5):
UPDATE core_assessmentscore 
SET score = -5 
WHERE id = 1;
-- ❌ ERROR: "Score cannot be negative" - Update aborted
```

**Trigger Summary:**
- **3 Triggers** implemented
- **2 BEFORE triggers** for data validation
- **1 AFTER trigger** for audit logging
- **Automatic execution** - no manual intervention needed
- **Database-level enforcement** - cannot be bypassed

---

## 5. Functions

### Definition
Database functions are reusable code blocks that perform calculations or operations. In SQLite, we use Python functions that act as database functions with ORM.

### Real Examples in EduLog System

**Note:** Since SQLite doesn't support user-defined SQL functions, we use Python functions that are called like database functions. These functions use Django ORM and support transactions.

#### Function 1: Calculate Student GPA
**Location:** `core/db_functions.py` - `calculate_student_gpa()`

**Purpose:** Calculate GPA with grade-to-GPA conversion formula.

**Key Features:**
- Transaction support
- Aggregation functions (AVG)
- Conditional logic (term filtering)
- Error handling

#### Function 2: Calculate Attendance Rate
**Location:** `core/db_functions.py` - `calculate_attendance_rate()`

**Purpose:** Calculate attendance percentage with date range filtering.

**Key Features:**
- Date filtering
- Percentage calculation
- Multiple status counting
- Transaction safety

#### Function 3: Get Student Performance Summary
**Location:** `core/db_functions.py` - `get_student_performance_summary()`

**Purpose:** Comprehensive performance data aggregation.

**Key Features:**
- Multiple subqueries
- Nested aggregations
- Complex data structure
- Performance optimization

#### Function 4: Get Teacher Class Statistics
**Location:** `core/db_functions.py` - `get_teacher_class_statistics()`

**Purpose:** Teacher statistics with at-risk student detection.

**Key Features:**
- Business logic implementation
- Complex filtering
- Multiple aggregations
- At-risk student calculation

#### Function 5: Check Consecutive Absences
**Location:** `core/db_functions.py` - `check_consecutive_absences_stored()`

**Purpose:** Detect consecutive absences using date logic.

**Key Features:**
- Date-based calculations
- Consecutive date detection
- Threshold-based logic
- Structured return values

**Function Usage Pattern:**
```python
# All functions follow this pattern:
@transaction.atomic  # Ensures ACID properties
def function_name(parameters):
    try:
        # Database operations using ORM
        # Aggregations and calculations
        # Return structured data
    except Exception as e:
        return {'error': str(e)}
```

---

## Summary

### Advanced SQL Features Implemented:

1. **Subqueries** ✅
   - Nested subqueries in triggers
   - Subqueries for data retrieval
   - Subqueries in validation logic

2. **Views** ✅ (3 views)
   - `vw_student_performance` - Student performance aggregation
   - `vw_teacher_subject_stats` - Teacher statistics
   - `vw_attendance_summary` - Daily attendance summary

3. **Stored Procedures** ✅ (5 functions)
   - `calculate_student_gpa()` - GPA calculation
   - `calculate_attendance_rate()` - Attendance statistics
   - `get_student_performance_summary()` - Performance summary
   - `get_teacher_class_statistics()` - Class statistics
   - `check_consecutive_absences_stored()` - Absence detection

4. **Triggers** ✅ (3 triggers)
   - `trg_grade_audit` - Automatic audit logging
   - `trg_validate_assessment_score` - Score validation (INSERT)
   - `trg_validate_assessment_score_update` - Score validation (UPDATE)

5. **Functions** ✅ (5 functions)
   - All stored procedure equivalents also serve as functions
   - Transaction support
   - Error handling
   - Reusable across the application

### Total Implementation:
- **3 Database Views**
- **3 Database Triggers**
- **5 Stored Procedure Equivalents**
- **Multiple Subquery Examples**
- **All features use real data from the system**

---

## Demonstration Notes

**For Live Demo:**
1. **Views:** Query `vw_student_performance` to show aggregated data
2. **Triggers:** Insert a grade and show automatic audit log creation
3. **Stored Procedures:** Call `calculate_student_gpa()` with real student ID
4. **Subqueries:** Show trigger code with nested subqueries
5. **Functions:** Demonstrate function calls with different parameters

**Screenshots Recommended:**
- View query results
- Trigger execution in database logs
- Function return values
- Subquery execution plans (if available)

