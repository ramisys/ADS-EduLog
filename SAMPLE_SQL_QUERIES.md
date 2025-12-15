# Sample SQL Queries for Each Advanced SQL Feature

This document contains sample queries for each SQL feature based on your current EduLog database.

---

## 1. SUBQUERIES

### Example 1: Subquery in SELECT - Get Student Average Grade with Subject Details
**Purpose:** Get student grades along with subject information using subqueries.

```sql
-- Get student performance with subject details using subqueries
SELECT 
    sp.student_id,
    (SELECT u.first_name || ' ' || u.last_name 
     FROM core_user u 
     WHERE u.id = sp.user_id) AS student_name,
    s.code AS subject_code,
    s.name AS subject_name,
    (SELECT AVG(grade) 
     FROM core_grade g 
     WHERE g.student_id = sp.id 
     AND g.subject_id = s.id) AS average_grade,
    (SELECT COUNT(*) 
     FROM core_grade g 
     WHERE g.student_id = sp.id 
     AND g.subject_id = s.id) AS grade_count
FROM core_studentprofile sp
CROSS JOIN core_subject s
WHERE sp.section_id = s.section_id
AND sp.student_id = 'STD-2025-00001';
```

### Example 2: Subquery in WHERE - Find Students Above Class Average
**Purpose:** Find students whose average grade is above the class average.

```sql
-- Find students with grades above class average
SELECT 
    sp.student_id,
    u.first_name || ' ' || u.last_name AS student_name,
    AVG(g.grade) AS student_avg_grade
FROM core_studentprofile sp
INNER JOIN core_user u ON sp.user_id = u.id
INNER JOIN core_grade g ON sp.id = g.student_id
WHERE g.subject_id = 133  -- Example: Intro to IT
GROUP BY sp.id, sp.student_id, u.first_name, u.last_name
HAVING AVG(g.grade) > (
    -- Subquery: Calculate class average for this subject
    SELECT AVG(grade) 
    FROM core_grade 
    WHERE subject_id = 133
)
ORDER BY student_avg_grade DESC;
```

### Example 3: Subquery in FROM (Derived Table) - Student Performance Ranking
**Purpose:** Rank students by their overall performance using a derived table subquery.

```sql
-- Rank students by overall GPA
SELECT 
    student_id,
    student_name,
    overall_avg,
    RANK() OVER (ORDER BY overall_avg DESC) AS rank
FROM (
    -- Subquery: Calculate average grade per student
    SELECT 
        sp.student_id,
        u.first_name || ' ' || u.last_name AS student_name,
        AVG(g.grade) AS overall_avg
    FROM core_studentprofile sp
    INNER JOIN core_user u ON sp.user_id = u.id
    INNER JOIN core_grade g ON sp.id = g.student_id
    GROUP BY sp.id, sp.student_id, u.first_name, u.last_name
) AS student_averages
ORDER BY overall_avg DESC;
```

### Example 4: Correlated Subquery - Attendance Rate per Subject
**Purpose:** Calculate attendance rate for each student per subject using correlated subquery.

```sql
-- Calculate attendance rate per student per subject
SELECT 
    sp.student_id,
    u.first_name || ' ' || u.last_name AS student_name,
    s.code AS subject_code,
    s.name AS subject_name,
    (SELECT COUNT(*) 
     FROM core_attendance a 
     WHERE a.student_id = sp.id 
     AND a.subject_id = s.id) AS total_attendance,
    (SELECT COUNT(*) 
     FROM core_attendance a 
     WHERE a.student_id = sp.id 
     AND a.subject_id = s.id 
     AND a.status = 'present') AS present_count,
    ROUND(
        (SELECT COUNT(*) 
         FROM core_attendance a 
         WHERE a.student_id = sp.id 
         AND a.subject_id = s.id 
         AND a.status = 'present') * 100.0 / 
        NULLIF((SELECT COUNT(*) 
                FROM core_attendance a 
                WHERE a.student_id = sp.id 
                AND a.subject_id = s.id), 0),
        2
    ) AS attendance_rate
FROM core_studentprofile sp
INNER JOIN core_user u ON sp.user_id = u.id
INNER JOIN core_subject s ON sp.section_id = s.section_id
WHERE sp.student_id = 'STD-2025-00001';
```

### Example 5: Subquery with EXISTS - Find Students with All Assessments Completed
**Purpose:** Find students who have completed all assessments for a subject.

```sql
-- Find students who have scores for all assessments in a subject
SELECT 
    sp.student_id,
    u.first_name || ' ' || u.last_name AS student_name,
    s.code AS subject_code
FROM core_studentprofile sp
INNER JOIN core_user u ON sp.user_id = u.id
INNER JOIN core_subject s ON sp.section_id = s.section_id
WHERE s.id = 131  -- Example: Data Structures
AND NOT EXISTS (
    -- Subquery: Check if there's an assessment without a score
    SELECT 1 
    FROM core_assessment a
    WHERE a.subject_id = s.id
    AND NOT EXISTS (
        SELECT 1 
        FROM core_assessmentscore as2
        WHERE as2.assessment_id = a.id
        AND as2.student_id = sp.id
    )
);
```

---

## 2. VIEWS

### Example 1: Query Student Performance View
**Purpose:** Use the existing `vw_student_performance` view to get student data.

```sql
-- Query the student performance view
SELECT 
    student_id,
    student_name,
    subject_code,
    subject_name,
    average_grade,
    grade_count,
    attendance_count,
    present_count,
    absent_count,
    attendance_percentage
FROM vw_student_performance
WHERE student_id = 'STD-2025-00001'
ORDER BY average_grade DESC;
```

### Example 2: Query Teacher Subject Statistics View
**Purpose:** Use the existing `vw_teacher_subject_stats` view to get teacher statistics.

```sql
-- Get statistics for a specific teacher
SELECT 
    teacher_id,
    teacher_name,
    subject_code,
    subject_name,
    section_name,
    student_count,
    grade_count,
    average_grade,
    attendance_count,
    present_count,
    absent_count
FROM vw_teacher_subject_stats
WHERE teacher_id = 'TCH-2025-00001'
ORDER BY average_grade DESC;
```

### Example 3: Query Attendance Summary View
**Purpose:** Use the existing `vw_attendance_summary` view for daily attendance reports.

```sql
-- Get attendance summary for a specific date
SELECT 
    attendance_date,
    subject_code,
    subject_name,
    section_name,
    total_students,
    present_count,
    absent_count,
    late_count,
    attendance_rate
FROM vw_attendance_summary
WHERE attendance_date = DATE('now', '-7 days')  -- Last week
ORDER BY attendance_rate DESC;
```

### Example 4: Complex Query Using View - Top Performing Students
**Purpose:** Use view in a complex query to find top performing students.

```sql
-- Find top 5 students across all subjects using the view
SELECT 
    student_id,
    student_name,
    COUNT(DISTINCT subject_id) AS subjects_count,
    AVG(average_grade) AS overall_average,
    SUM(grade_count) AS total_grades,
    AVG(attendance_percentage) AS avg_attendance_rate
FROM vw_student_performance
GROUP BY student_id, student_name
HAVING COUNT(DISTINCT subject_id) >= 2
ORDER BY overall_average DESC
LIMIT 5;
```

### Example 5: View with Filtering and Aggregation
**Purpose:** Use view to get subject-wise statistics.

```sql
-- Get subject-wise statistics using the view
SELECT 
    subject_code,
    subject_name,
    COUNT(DISTINCT student_id) AS total_students,
    AVG(average_grade) AS class_average,
    AVG(attendance_percentage) AS avg_attendance_rate,
    MIN(average_grade) AS lowest_grade,
    MAX(average_grade) AS highest_grade
FROM vw_student_performance
GROUP BY subject_code, subject_name
ORDER BY class_average DESC;
```

---

## 3. STORED PROCEDURES (Python Functions)

**Note:** Since SQLite doesn't support stored procedures, these are Python functions that act as stored procedures. Here are SQL equivalents that demonstrate the logic:

### Example 1: Calculate Student GPA (SQL Equivalent)
**Purpose:** Calculate GPA for a student (equivalent to `calculate_student_gpa()` function).

```sql
-- Calculate GPA for a specific student
SELECT 
    sp.student_id,
    u.first_name || ' ' || u.last_name AS student_name,
    COUNT(g.id) AS grade_count,
    AVG(g.grade) AS average_grade,
    ROUND((AVG(g.grade) / 100.0) * 4.0, 2) AS gpa,
    GROUP_CONCAT(g.term) AS terms
FROM core_studentprofile sp
INNER JOIN core_user u ON sp.user_id = u.id
LEFT JOIN core_grade g ON sp.id = g.student_id
WHERE sp.student_id = 'STD-2025-00001'
GROUP BY sp.id, sp.student_id, u.first_name, u.last_name;
```

### Example 2: Calculate Attendance Rate (SQL Equivalent)
**Purpose:** Calculate attendance statistics (equivalent to `calculate_attendance_rate()` function).

```sql
-- Calculate attendance rate for a student
SELECT 
    sp.student_id,
    u.first_name || ' ' || u.last_name AS student_name,
    s.code AS subject_code,
    COUNT(a.id) AS total_count,
    SUM(CASE WHEN a.status = 'present' THEN 1 ELSE 0 END) AS present_count,
    SUM(CASE WHEN a.status = 'absent' THEN 1 ELSE 0 END) AS absent_count,
    SUM(CASE WHEN a.status = 'late' THEN 1 ELSE 0 END) AS late_count,
    ROUND(
        SUM(CASE WHEN a.status = 'present' THEN 1 ELSE 0 END) * 100.0 / 
        NULLIF(COUNT(a.id), 0),
        2
    ) AS attendance_rate
FROM core_studentprofile sp
INNER JOIN core_user u ON sp.user_id = u.id
INNER JOIN core_subject s ON sp.section_id = s.section_id
LEFT JOIN core_attendance a ON sp.id = a.student_id AND s.id = a.subject_id
WHERE sp.student_id = 'STD-2025-00001'
AND a.date >= DATE('now', '-30 days')  -- Last 30 days
GROUP BY sp.id, sp.student_id, u.first_name, u.last_name, s.id, s.code;
```

### Example 3: Get Student Performance Summary (SQL Equivalent)
**Purpose:** Comprehensive performance data (equivalent to `get_student_performance_summary()` function).

```sql
-- Get comprehensive student performance summary
SELECT 
    sp.student_id,
    u.first_name || ' ' || u.last_name AS student_name,
    s.code AS subject_code,
    s.name AS subject_name,
    AVG(g.grade) AS subject_average,
    COUNT(DISTINCT g.id) AS grade_count,
    COUNT(DISTINCT a.id) AS attendance_count,
    ROUND(
        SUM(CASE WHEN a.status = 'present' THEN 1 ELSE 0 END) * 100.0 / 
        NULLIF(COUNT(DISTINCT a.id), 0),
        2
    ) AS attendance_rate,
    (SELECT AVG(grade) 
     FROM core_grade g2 
     WHERE g2.student_id = sp.id) AS overall_average
FROM core_studentprofile sp
INNER JOIN core_user u ON sp.user_id = u.id
INNER JOIN core_subject s ON sp.section_id = s.section_id
LEFT JOIN core_grade g ON sp.id = g.student_id AND s.id = g.subject_id
LEFT JOIN core_attendance a ON sp.id = a.student_id AND s.id = a.subject_id
WHERE sp.student_id = 'STD-2025-00001'
GROUP BY sp.id, sp.student_id, u.first_name, u.last_name, s.id, s.code, s.name
ORDER BY subject_average DESC;
```

### Example 4: Get Teacher Class Statistics (SQL Equivalent)
**Purpose:** Teacher statistics with at-risk student detection (equivalent to `get_teacher_class_statistics()` function).

```sql
-- Get teacher class statistics
SELECT 
    tp.teacher_id,
    u.first_name || ' ' || u.last_name AS teacher_name,
    s.code AS subject_code,
    s.name AS subject_name,
    cs.name AS section_name,
    COUNT(DISTINCT sp.id) AS student_count,
    COUNT(DISTINCT g.id) AS grade_count,
    AVG(g.grade) AS average_grade,
    COUNT(DISTINCT a.id) AS attendance_count,
    ROUND(
        SUM(CASE WHEN a.status = 'present' THEN 1 ELSE 0 END) * 100.0 / 
        NULLIF(COUNT(DISTINCT a.id), 0),
        2
    ) AS attendance_rate,
    -- Count at-risk students (GPA < 75 or attendance < 70%)
    (SELECT COUNT(DISTINCT sp2.id)
     FROM core_studentprofile sp2
     WHERE sp2.section_id = s.section_id
     AND (
         (SELECT AVG(g2.grade) 
          FROM core_grade g2 
          WHERE g2.student_id = sp2.id 
          AND g2.subject_id = s.id) < 75
         OR
         (SELECT ROUND(
             SUM(CASE WHEN a2.status = 'present' THEN 1 ELSE 0 END) * 100.0 / 
             NULLIF(COUNT(a2.id), 0),
             2
         )
          FROM core_attendance a2
          WHERE a2.student_id = sp2.id 
          AND a2.subject_id = s.id) < 70
     )
    ) AS at_risk_students
FROM core_teacherprofile tp
INNER JOIN core_user u ON tp.user_id = u.id
INNER JOIN core_subject s ON tp.id = s.teacher_id
INNER JOIN core_classsection cs ON s.section_id = cs.id
LEFT JOIN core_studentprofile sp ON s.section_id = sp.section_id
LEFT JOIN core_grade g ON s.id = g.subject_id AND sp.id = g.student_id
LEFT JOIN core_attendance a ON s.id = a.subject_id AND sp.id = a.student_id
WHERE tp.teacher_id = 'TCH-2025-00001'
GROUP BY tp.id, tp.teacher_id, u.first_name, u.last_name, s.id, s.code, s.name, cs.name;
```

---

## 4. TRIGGERS

### Example 1: Test Grade Audit Trigger
**Purpose:** Demonstrate the `trg_grade_audit` trigger by inserting a grade.

```sql
-- Insert a grade to trigger the audit log
INSERT INTO core_grade (student_id, subject_id, term, grade)
VALUES (
    (SELECT id FROM core_studentprofile WHERE student_id = 'STD-2025-00001'),
    133,  -- Intro to IT
    'Final',
    88.5
);

-- Check the audit log to see the trigger result
SELECT 
    al.id,
    u.first_name || ' ' || u.last_name AS user_name,
    al.action,
    al.details,
    sp.student_id,
    al.timestamp
FROM core_auditlog al
LEFT JOIN core_user u ON al.user_id = u.id
LEFT JOIN core_studentprofile sp ON al.student_id = sp.id
ORDER BY al.timestamp DESC
LIMIT 5;
```

### Example 2: Test Assessment Score Validation Trigger (Valid Insert)
**Purpose:** Test the `trg_validate_assessment_score` trigger with a valid score.

```sql
-- Valid insertion (score within range)
-- First, get an assessment ID and max_score
SELECT id, name, max_score 
FROM core_assessment 
WHERE subject_id = 131 
LIMIT 1;

-- Insert a valid score (assuming assessment_id = 605, max_score = 100)
INSERT INTO core_assessmentscore (student_id, assessment_id, score)
VALUES (
    (SELECT id FROM core_studentprofile WHERE student_id = 'STD-2025-00001'),
    605,  -- Assessment ID
    85    -- Valid score (less than max_score = 100)
);
-- This should succeed
```

### Example 3: Test Assessment Score Validation Trigger (Invalid Insert)
**Purpose:** Test the trigger with an invalid score (should fail).

```sql
-- Invalid insertion (score exceeds max_score)
-- This should fail with error: "Score cannot exceed maximum score"
INSERT INTO core_assessmentscore (student_id, assessment_id, score)
VALUES (
    (SELECT id FROM core_studentprofile WHERE student_id = 'STD-2025-00001'),
    605,  -- Assessment ID with max_score = 100
    150   -- Invalid score (exceeds max_score)
);
-- This should raise an error
```

### Example 4: Test Assessment Score Update Validation Trigger
**Purpose:** Test the `trg_validate_assessment_score_update` trigger.

```sql
-- Valid update
UPDATE core_assessmentscore 
SET score = 90 
WHERE id = (
    SELECT id 
    FROM core_assessmentscore 
    LIMIT 1
);
-- This should succeed

-- Invalid update (negative score)
UPDATE core_assessmentscore 
SET score = -5 
WHERE id = (
    SELECT id 
    FROM core_assessmentscore 
    LIMIT 1
);
-- This should raise an error: "Score cannot be negative"
```

### Example 5: View All Trigger Definitions
**Purpose:** Check what triggers are defined in the database.

```sql
-- List all triggers in the database
SELECT 
    name AS trigger_name,
    tbl_name AS table_name,
    type,
    sql
FROM sqlite_master
WHERE type = 'trigger'
ORDER BY tbl_name, name;
```

---

## 5. FUNCTIONS (Aggregate and Scalar Functions)

### Example 1: Aggregate Functions - Student Statistics
**Purpose:** Use aggregate functions (COUNT, AVG, SUM, MIN, MAX) for statistics.

```sql
-- Comprehensive student statistics using aggregate functions
SELECT 
    sp.student_id,
    u.first_name || ' ' || u.last_name AS student_name,
    COUNT(DISTINCT g.id) AS total_grades,
    COUNT(DISTINCT g.subject_id) AS subjects_with_grades,
    AVG(g.grade) AS average_grade,
    MIN(g.grade) AS lowest_grade,
    MAX(g.grade) AS highest_grade,
    SUM(CASE WHEN g.grade >= 90 THEN 1 ELSE 0 END) AS excellent_grades,
    SUM(CASE WHEN g.grade < 75 THEN 1 ELSE 0 END) AS failing_grades,
    COUNT(DISTINCT a.id) AS total_attendance,
    SUM(CASE WHEN a.status = 'present' THEN 1 ELSE 0 END) AS present_days,
    ROUND(
        SUM(CASE WHEN a.status = 'present' THEN 1 ELSE 0 END) * 100.0 / 
        NULLIF(COUNT(DISTINCT a.id), 0),
        2
    ) AS attendance_percentage
FROM core_studentprofile sp
INNER JOIN core_user u ON sp.user_id = u.id
LEFT JOIN core_grade g ON sp.id = g.student_id
LEFT JOIN core_attendance a ON sp.id = a.student_id
WHERE sp.student_id = 'STD-2025-00001'
GROUP BY sp.id, sp.student_id, u.first_name, u.last_name;
```

### Example 2: String Functions - Format Student Reports
**Purpose:** Use string functions (CONCAT, SUBSTR, UPPER, LOWER) for formatting.

```sql
-- Format student information using string functions
SELECT 
    sp.student_id,
    UPPER(u.first_name || ' ' || u.last_name) AS student_name_upper,
    LOWER(u.email) AS email_lower,
    SUBSTR(sp.student_id, 1, 3) AS student_prefix,
    SUBSTR(sp.student_id, 9) AS student_number,
    s.code || ' - ' || s.name AS subject_full_name,
    'Grade: ' || CAST(g.grade AS TEXT) || ' (' || g.term || ')' AS grade_display
FROM core_studentprofile sp
INNER JOIN core_user u ON sp.user_id = u.id
INNER JOIN core_grade g ON sp.id = g.student_id
INNER JOIN core_subject s ON g.subject_id = s.id
WHERE sp.student_id = 'STD-2025-00001'
ORDER BY g.term, s.code;
```

### Example 3: Date Functions - Attendance by Date Range
**Purpose:** Use date functions (DATE, DATE(), strftime) for date-based queries.

```sql
-- Attendance analysis using date functions
SELECT 
    DATE(a.date) AS attendance_date,
    strftime('%Y-%m', a.date) AS month,
    strftime('%W', a.date) AS week_number,
    s.code AS subject_code,
    COUNT(DISTINCT a.student_id) AS students_present,
    SUM(CASE WHEN a.status = 'present' THEN 1 ELSE 0 END) AS present_count,
    SUM(CASE WHEN a.status = 'absent' THEN 1 ELSE 0 END) AS absent_count,
    SUM(CASE WHEN a.status = 'late' THEN 1 ELSE 0 END) AS late_count
FROM core_attendance a
INNER JOIN core_subject s ON a.subject_id = s.id
WHERE a.date >= DATE('now', '-30 days')  -- Last 30 days
GROUP BY DATE(a.date), strftime('%Y-%m', a.date), strftime('%W', a.date), s.id, s.code
ORDER BY attendance_date DESC, s.code;
```

### Example 4: Window Functions - Ranking Students
**Purpose:** Use window functions (RANK, DENSE_RANK, ROW_NUMBER) for ranking.

```sql
-- Rank students by performance using window functions
SELECT 
    sp.student_id,
    u.first_name || ' ' || u.last_name AS student_name,
    s.code AS subject_code,
    AVG(g.grade) AS average_grade,
    RANK() OVER (PARTITION BY s.id ORDER BY AVG(g.grade) DESC) AS rank_in_subject,
    DENSE_RANK() OVER (ORDER BY AVG(g.grade) DESC) AS overall_rank,
    ROW_NUMBER() OVER (PARTITION BY s.id ORDER BY AVG(g.grade) DESC) AS row_num
FROM core_studentprofile sp
INNER JOIN core_user u ON sp.user_id = u.id
INNER JOIN core_grade g ON sp.id = g.student_id
INNER JOIN core_subject s ON g.subject_id = s.id
WHERE s.id = 133  -- Example: Intro to IT
GROUP BY sp.id, sp.student_id, u.first_name, u.last_name, s.id, s.code
ORDER BY average_grade DESC;
```

### Example 5: Conditional Functions - Grade Classification
**Purpose:** Use CASE statements and COALESCE for conditional logic.

```sql
-- Classify grades using CASE statements
SELECT 
    sp.student_id,
    u.first_name || ' ' || u.last_name AS student_name,
    s.code AS subject_code,
    g.grade,
    g.term,
    CASE 
        WHEN g.grade >= 90 THEN 'Excellent'
        WHEN g.grade >= 80 THEN 'Very Good'
        WHEN g.grade >= 75 THEN 'Good'
        WHEN g.grade >= 70 THEN 'Satisfactory'
        ELSE 'Needs Improvement'
    END AS grade_classification,
    CASE 
        WHEN g.grade >= 75 THEN 'Pass'
        ELSE 'Fail'
    END AS pass_fail,
    COALESCE(
        (SELECT AVG(g2.grade) 
         FROM core_grade g2 
         WHERE g2.student_id = sp.id 
         AND g2.subject_id = s.id),
        0
    ) AS subject_average
FROM core_studentprofile sp
INNER JOIN core_user u ON sp.user_id = u.id
INNER JOIN core_grade g ON sp.id = g.student_id
INNER JOIN core_subject s ON g.subject_id = s.id
WHERE sp.student_id = 'STD-2025-00001'
ORDER BY s.code, g.term;
```

### Example 6: Mathematical Functions - GPA Calculation
**Purpose:** Use mathematical functions (ROUND, CAST) for calculations.

```sql
-- Calculate GPA using mathematical functions
SELECT 
    sp.student_id,
    u.first_name || ' ' || u.last_name AS student_name,
    COUNT(g.id) AS grade_count,
    ROUND(AVG(g.grade), 2) AS average_grade,
    ROUND((AVG(g.grade) / 100.0) * 4.0, 2) AS gpa,
    ROUND(STDEV(g.grade), 2) AS grade_std_dev,
    ROUND(MIN(g.grade), 2) AS min_grade,
    ROUND(MAX(g.grade), 2) AS max_grade,
    ROUND(MAX(g.grade) - MIN(g.grade), 2) AS grade_range
FROM core_studentprofile sp
INNER JOIN core_user u ON sp.user_id = u.id
INNER JOIN core_grade g ON sp.id = g.student_id
GROUP BY sp.id, sp.student_id, u.first_name, u.last_name
HAVING COUNT(g.id) > 0
ORDER BY gpa DESC;
```

---

## 6. COMBINED FEATURES - Complex Queries

### Example 1: View + Subquery + Aggregate Functions
**Purpose:** Combine multiple features in one query.

```sql
-- Complex query combining view, subquery, and aggregates
SELECT 
    vsp.student_id,
    vsp.student_name,
    vsp.subject_code,
    vsp.average_grade,
    vsp.attendance_percentage,
    (SELECT COUNT(*) 
     FROM core_grade g 
     WHERE g.student_id = (SELECT id FROM core_studentprofile WHERE student_id = vsp.student_id)
     AND g.grade >= 90) AS excellent_grades_count,
    CASE 
        WHEN vsp.average_grade >= 90 AND vsp.attendance_percentage >= 90 THEN 'Outstanding'
        WHEN vsp.average_grade >= 80 AND vsp.attendance_percentage >= 80 THEN 'Good'
        WHEN vsp.average_grade >= 75 AND vsp.attendance_percentage >= 75 THEN 'Satisfactory'
        ELSE 'Needs Improvement'
    END AS performance_status
FROM vw_student_performance vsp
WHERE vsp.student_id = 'STD-2025-00001'
ORDER BY vsp.average_grade DESC;
```

### Example 2: Subquery + Window Functions + CASE
**Purpose:** Advanced ranking with conditional logic.

```sql
-- Advanced ranking with performance categories
SELECT 
    student_id,
    student_name,
    subject_code,
    average_grade,
    attendance_percentage,
    RANK() OVER (PARTITION BY subject_code ORDER BY average_grade DESC) AS subject_rank,
    CASE 
        WHEN average_grade >= (SELECT AVG(average_grade) FROM vw_student_performance WHERE subject_code = vsp.subject_code)
        THEN 'Above Average'
        ELSE 'Below Average'
    END AS performance_vs_class
FROM vw_student_performance vsp
WHERE subject_code = 'IT101-BSIT1A'
ORDER BY average_grade DESC;
```

---

## Usage Notes

1. **Replace Placeholder Values:**
   - Replace `'STD-2025-00001'` with actual student IDs from your database
   - Replace `'TCH-2025-00001'` with actual teacher IDs
   - Replace subject IDs (131, 132, 133) with actual subject IDs

2. **To Find Actual IDs:**
   ```sql
   -- Get student IDs
   SELECT student_id, id FROM core_studentprofile LIMIT 10;
   
   -- Get teacher IDs
   SELECT teacher_id, id FROM core_teacherprofile LIMIT 10;
   
   -- Get subject IDs
   SELECT id, code, name FROM core_subject LIMIT 10;
   ```

3. **Testing Triggers:**
   - Triggers execute automatically, so insert/update operations will trigger them
   - Check `core_auditlog` table after grade insertions
   - Invalid score insertions will fail with error messages

4. **Views:**
   - Views are already created in your database
   - Query them like regular tables
   - Views automatically update when underlying data changes

5. **Performance:**
   - Use indexes on frequently queried columns
   - Limit result sets with `LIMIT` clause
   - Use `EXPLAIN QUERY PLAN` to analyze query performance

---

## Quick Reference

| Feature | Count | Examples |
|---------|-------|----------|
| **Subqueries** | 5+ | SELECT, WHERE, FROM, EXISTS, Correlated |
| **Views** | 3 | vw_student_performance, vw_teacher_subject_stats, vw_attendance_summary |
| **Triggers** | 3 | Grade audit, Score validation (INSERT/UPDATE) |
| **Functions** | Multiple | Aggregate, String, Date, Window, Conditional |
| **Stored Procedures** | 5 | GPA calculation, Attendance rate, Performance summary, etc. |

---

**Last Updated:** Based on current database schema and data structure.

