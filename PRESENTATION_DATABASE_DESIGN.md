# II. Database Design (ERD & Schema)
**Time Allocation: 5-7 minutes (20% of presentation)**

---

## 1. Conceptual Design

### Entity-Relationship Diagram (ERD) Overview

**Core Entities (13 Models):**

1. **User** - Central authentication entity
2. **TeacherProfile** - Teacher-specific information
3. **StudentProfile** - Student-specific information
4. **ParentProfile** - Parent-specific information
5. **ClassSection** - Class/section organization
6. **Subject** - Course subjects
7. **Attendance** - Student attendance records
8. **Grade** - Student grades per term
9. **Assessment** - Assessment items (Activities, Quizzes, Projects, Exams)
10. **AssessmentScore** - Individual student scores for assessments
11. **CategoryWeights** - Weight distribution for assessment categories
12. **Notification** - System notifications
13. **AuditLog** - Audit trail for grade/assessment changes
14. **Feedback** - User feedback system

### Key Relationships:

#### One-to-One Relationships:
- **User ↔ TeacherProfile** (One user = One teacher profile)
- **User ↔ StudentProfile** (One user = One student profile)
- **User ↔ ParentProfile** (One user = One parent profile)
- **Subject ↔ CategoryWeights** (One subject = One weight configuration)

#### One-to-Many Relationships:
- **TeacherProfile → ClassSection** (One teacher can advise multiple sections)
- **ParentProfile → StudentProfile** (One parent can have multiple children)
- **ClassSection → StudentProfile** (One section has many students)
- **ClassSection → Subject** (One section has many subjects)
- **TeacherProfile → Subject** (One teacher teaches many subjects)
- **StudentProfile → Attendance** (One student has many attendance records)
- **StudentProfile → Grade** (One student has many grades)
- **StudentProfile → AssessmentScore** (One student has many assessment scores)
- **Subject → Assessment** (One subject has many assessments)
- **Assessment → AssessmentScore** (One assessment has many scores)
- **User → Notification** (One user receives many notifications)
- **User → AuditLog** (One user generates many audit logs)

#### Many-to-Many (Implemented via Foreign Keys):
- **Student ↔ Subject** (via Attendance, Grade, AssessmentScore)
- **Teacher ↔ Subject** (via Subject.teacher)

### Entity Attributes Summary:

**User Entity:**
- Primary Key: `id` (auto-generated)
- Attributes: `username`, `email`, `password`, `first_name`, `last_name`, `role`, `is_active`, `is_staff`, `is_superuser`
- Indexes: `role`, `is_active`, `email`

**TeacherProfile Entity:**
- Primary Key: `id`
- Foreign Key: `user_id` → User
- Attributes: `teacher_id` (unique, auto-generated), `department`
- Indexes: `teacher_id`, `department`

**StudentProfile Entity:**
- Primary Key: `id`
- Foreign Keys: `user_id` → User, `parent_id` → ParentProfile, `section_id` → ClassSection
- Attributes: `student_id` (unique, auto-generated), `course`, `year_level`
- Indexes: `student_id`, `(section, course)`, `(section, year_level)`

**Subject Entity:**
- Primary Key: `id`
- Foreign Keys: `teacher_id` → TeacherProfile, `section_id` → ClassSection
- Attributes: `code`, `name`
- Indexes: `code`, `(teacher, section)`, `(section, code)`

**Attendance Entity:**
- Primary Key: `id`
- Foreign Keys: `student_id` → StudentProfile, `subject_id` → Subject
- Attributes: `date`, `status` (Present/Absent/Late)
- Unique Constraint: `(student, subject, date)` - One attendance record per student per subject per day
- Indexes: `(student, date)`, `(subject, date)`, `(student, subject, date)`, `(date, status)`

**Grade Entity:**
- Primary Key: `id`
- Foreign Keys: `student_id` → StudentProfile, `subject_id` → Subject
- Attributes: `term`, `grade` (Decimal)
- Unique Constraint: `(student, subject, term)` - One grade per student per subject per term
- Indexes: `(student, subject)`, `(student, term)`, `(subject, term)`

**Assessment Entity:**
- Primary Key: `id`
- Foreign Keys: `subject_id` → Subject, `created_by_id` → TeacherProfile
- Attributes: `name`, `category` (Activities/Quizzes/Projects/Exams), `max_score`, `date`, `term`, `created_at`, `updated_at`
- Indexes: `(subject, date)`, `(subject, term)`, `(category, date)`, `(created_by, date)`

**AssessmentScore Entity:**
- Primary Key: `id`
- Foreign Keys: `student_id` → StudentProfile, `assessment_id` → Assessment, `recorded_by_id` → TeacherProfile
- Attributes: `score` (Decimal), `created_at`, `updated_at`
- Unique Constraint: `(student, assessment)` - One score per student per assessment
- Indexes: `(student, assessment)`, `(assessment, score)`, `(recorded_by, created_at)`

---

## 2. Logical & Physical Design

### Normalization Process

#### First Normal Form (1NF) ✅
**Requirement:** All attributes are atomic (indivisible)

**Implementation:**
- All fields contain single, atomic values
- No multi-valued attributes
- No repeating groups
- Examples:
  - `student_id` = "STD-2025-00001" (single value)
  - `grade` = 85.50 (single decimal value)
  - `status` = "present" (single choice value)

#### Second Normal Form (2NF) ✅
**Requirement:** All non-key attributes fully dependent on primary key

**Implementation:**
- All tables have proper primary keys
- Composite keys used where appropriate (Attendance, Grade, AssessmentScore)
- No partial dependencies
- Examples:
  - **Attendance**: `(student, subject, date)` as unique constraint ensures full dependency
  - **Grade**: `(student, subject, term)` ensures grade depends on all three attributes
  - **AssessmentScore**: `(student, assessment)` ensures score depends on both

#### Third Normal Form (3NF) ✅
**Requirement:** No transitive dependencies (non-key attributes depend only on primary key)

**Implementation:**
- Proper separation of concerns
- User → Profile relationship (one-to-one) prevents transitive dependencies
- No derived/redundant data stored
- Examples:
  - Student's name stored in User, not duplicated in StudentProfile
  - Teacher's name in User, referenced via foreign key in TeacherProfile
  - Section name in ClassSection, referenced via foreign key in Subject

### Key Definitions

#### Primary Keys:
- **Auto-incrementing integers** (`id`) for all tables
- **Composite unique constraints** for business logic:
  - Attendance: `(student, subject, date)`
  - Grade: `(student, subject, term)`
  - AssessmentScore: `(student, assessment)`
  - CategoryWeights: `(subject)`

#### Foreign Keys:
- **CASCADE**: When parent deleted, child deleted
  - User → Profiles (CASCADE)
  - Subject → Assessment (CASCADE)
  - Assessment → AssessmentScore (CASCADE)
  
- **SET_NULL**: When parent deleted, child's FK set to NULL
  - TeacherProfile → ClassSection.adviser (SET_NULL)
  - TeacherProfile → Subject.teacher (SET_NULL)
  - ParentProfile → StudentProfile.parent (SET_NULL)
  - ClassSection → StudentProfile.section (SET_NULL)

#### Constraints:

**Unique Constraints:**
```sql
-- Attendance: One record per student per subject per day
UNIQUE(student_id, subject_id, date)

-- Grade: One grade per student per subject per term
UNIQUE(student_id, subject_id, term)

-- AssessmentScore: One score per student per assessment
UNIQUE(student_id, assessment_id)

-- CategoryWeights: One weight configuration per subject
UNIQUE(subject_id)
```

**Check Constraints (Application Level):**
- CategoryWeights: `activities_weight + quizzes_weight + projects_weight + exams_weight = 100`
- AssessmentScore: `score >= 0 AND score <= max_score` (enforced via triggers)
- Grade: `grade >= 0 AND grade <= 100` (enforced via application logic)

**Indexes (17+ indexes for optimization):**
- Single column indexes on frequently queried fields
- Composite indexes on common query patterns
- Examples:
  - `(student, subject, date)` on Attendance
  - `(student, subject, term)` on Grade
  - `(recipient, is_read, created_at)` on Notification

---

## 3. Database Schema

### Tables and Relationships (As Implemented in DBMS)

#### Sample CREATE TABLE Statements (SQLite/Django ORM Equivalent)

**1. User Table**
```sql
CREATE TABLE core_user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(150) UNIQUE NOT NULL,
    email VARCHAR(254),
    password VARCHAR(128) NOT NULL,
    first_name VARCHAR(150),
    last_name VARCHAR(150),
    role VARCHAR(10) NOT NULL DEFAULT 'student',
    is_active BOOLEAN NOT NULL DEFAULT 1,
    is_staff BOOLEAN NOT NULL DEFAULT 0,
    is_superuser BOOLEAN NOT NULL DEFAULT 0,
    date_joined DATETIME NOT NULL,
    last_login DATETIME
);

CREATE INDEX idx_user_role_active ON core_user(role, is_active);
CREATE INDEX idx_user_email ON core_user(email);
```

**2. StudentProfile Table**
```sql
CREATE TABLE core_studentprofile (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id VARCHAR(20) UNIQUE NOT NULL,
    user_id INTEGER UNIQUE NOT NULL,
    parent_id INTEGER,
    course VARCHAR(100) NOT NULL,
    year_level VARCHAR(20) NOT NULL,
    section_id INTEGER,
    FOREIGN KEY (user_id) REFERENCES core_user(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_id) REFERENCES core_parentprofile(id) ON DELETE SET NULL,
    FOREIGN KEY (section_id) REFERENCES core_classsection(id) ON DELETE SET NULL
);

CREATE INDEX idx_student_id ON core_studentprofile(student_id);
CREATE INDEX idx_student_section_course ON core_studentprofile(section_id, course);
CREATE INDEX idx_student_section_year ON core_studentprofile(section_id, year_level);
```

**3. Attendance Table (Highlighting Constraints)**
```sql
CREATE TABLE core_attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    subject_id INTEGER NOT NULL,
    date DATE NOT NULL,
    status VARCHAR(10) NOT NULL CHECK(status IN ('present', 'absent', 'late')),
    FOREIGN KEY (student_id) REFERENCES core_studentprofile(id) ON DELETE CASCADE,
    FOREIGN KEY (subject_id) REFERENCES core_subject(id) ON DELETE CASCADE,
    -- UNIQUE CONSTRAINT: Prevents duplicate attendance per day
    UNIQUE(student_id, subject_id, date)
);

-- Composite indexes for common queries
CREATE INDEX idx_attendance_student_date ON core_attendance(student_id, date);
CREATE INDEX idx_attendance_subject_date ON core_attendance(subject_id, date);
CREATE INDEX idx_attendance_student_subject_date ON core_attendance(student_id, subject_id, date);
CREATE INDEX idx_attendance_date_status ON core_attendance(date, status);
```

**4. Grade Table (Highlighting Constraints)**
```sql
CREATE TABLE core_grade (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    subject_id INTEGER NOT NULL,
    term VARCHAR(20) NOT NULL DEFAULT 'Midterm',
    grade DECIMAL(5,2) NOT NULL CHECK(grade >= 0 AND grade <= 100),
    FOREIGN KEY (student_id) REFERENCES core_studentprofile(id) ON DELETE CASCADE,
    FOREIGN KEY (subject_id) REFERENCES core_subject(id) ON DELETE CASCADE,
    -- UNIQUE CONSTRAINT: One grade per student per subject per term
    UNIQUE(student_id, subject_id, term)
);

-- Composite indexes
CREATE INDEX idx_grade_student_subject ON core_grade(student_id, subject_id);
CREATE INDEX idx_grade_student_term ON core_grade(student_id, term);
CREATE INDEX idx_grade_subject_term ON core_grade(subject_id, term);
```

**5. AssessmentScore Table (Highlighting Constraints)**
```sql
CREATE TABLE core_assessmentscore (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    assessment_id INTEGER NOT NULL,
    score DECIMAL(5,2) NOT NULL,
    recorded_by_id INTEGER,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    FOREIGN KEY (student_id) REFERENCES core_studentprofile(id) ON DELETE CASCADE,
    FOREIGN KEY (assessment_id) REFERENCES core_assessment(id) ON DELETE CASCADE,
    FOREIGN KEY (recorded_by_id) REFERENCES core_teacherprofile(id) ON DELETE SET NULL,
    -- UNIQUE CONSTRAINT: One score per student per assessment
    UNIQUE(student_id, assessment_id)
);

-- Indexes for performance
CREATE INDEX idx_score_student_assessment ON core_assessmentscore(student_id, assessment_id);
CREATE INDEX idx_score_assessment_score ON core_assessmentscore(assessment_id, score);
CREATE INDEX idx_score_recorded_by_created ON core_assessmentscore(recorded_by_id, created_at);
```

**6. CategoryWeights Table (Highlighting Constraints)**
```sql
CREATE TABLE core_categoryweights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id INTEGER UNIQUE NOT NULL,
    activities_weight INTEGER NOT NULL DEFAULT 20,
    quizzes_weight INTEGER NOT NULL DEFAULT 20,
    projects_weight INTEGER NOT NULL DEFAULT 30,
    exams_weight INTEGER NOT NULL DEFAULT 30,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    FOREIGN KEY (subject_id) REFERENCES core_subject(id) ON DELETE CASCADE,
    -- Application-level constraint: weights must sum to 100
    CHECK(activities_weight + quizzes_weight + projects_weight + exams_weight = 100)
);
```

### Relationship Summary:

```
User (1) ──< (1) TeacherProfile
User (1) ──< (1) StudentProfile
User (1) ──< (1) ParentProfile

TeacherProfile (1) ──< (*) ClassSection (adviser)
ParentProfile (1) ──< (*) StudentProfile
ClassSection (1) ──< (*) StudentProfile
ClassSection (1) ──< (*) Subject

TeacherProfile (1) ──< (*) Subject
Subject (1) ──< (*) Assessment
Subject (1) ──< (1) CategoryWeights

StudentProfile (1) ──< (*) Attendance
Subject (1) ──< (*) Attendance

StudentProfile (1) ──< (*) Grade
Subject (1) ──< (*) Grade

StudentProfile (1) ──< (*) AssessmentScore
Assessment (1) ──< (*) AssessmentScore

User (1) ──< (*) Notification
User (1) ──< (*) AuditLog
User (1) ──< (*) Feedback
```

### Key Design Decisions:

1. **Separation of User and Profiles**: 
   - User handles authentication
   - Profiles store role-specific data
   - Enables one user to potentially have multiple roles (future extensibility)

2. **Auto-generated IDs**: 
   - Format: `PREFIX-YYYY-XXXXX` (e.g., `STD-2025-00001`)
   - Ensures unique, traceable identifiers

3. **Composite Unique Constraints**: 
   - Prevents data duplication
   - Enforces business rules at database level

4. **Comprehensive Indexing**: 
   - 17+ indexes covering all common query patterns
   - Optimizes performance for frequent operations

5. **Audit Trail**: 
   - AuditLog tracks all grade/assessment changes
   - Ensures data integrity and accountability

6. **Normalized Design**: 
   - Follows 3NF principles
   - Eliminates redundancy
   - Maintains data consistency

---

## Summary

- **13 Core Entities** with well-defined relationships
- **Fully Normalized** (1NF, 2NF, 3NF)
- **17+ Indexes** for query optimization
- **Multiple Constraints** ensuring data integrity
- **Proper Foreign Key Relationships** with appropriate CASCADE/SET_NULL behaviors
- **Composite Unique Constraints** preventing duplicate records
- **Audit Trail** for critical operations

