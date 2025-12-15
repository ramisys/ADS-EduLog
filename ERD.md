# Entity Relationship Diagram (ERD)
## ADS-EduLog System

This document contains the Entity Relationship Diagram for the ADS-EduLog educational management system.

```mermaid
erDiagram
    User ||--o| ParentProfile : "has (1:1)"
    User ||--o| TeacherProfile : "has (1:1)"
    User ||--o| StudentProfile : "has (1:1)"
    User ||--o{ Notification : "receives (1:N)"
    User ||--o{ AuditLog : "creates (1:N)"
    User ||--o{ Feedback : "submits (1:N)"
    User ||--o{ Feedback : "responds_to (1:N)"
    
    ParentProfile ||--o{ StudentProfile : "has_children (1:N)"
    
    TeacherProfile ||--o{ ClassSection : "advises (1:N)"
    TeacherProfile ||--o{ Subject : "teaches (1:N)"
    TeacherProfile ||--o{ Assessment : "creates (1:N)"
    TeacherProfile ||--o{ AssessmentScore : "records (1:N)"
    
    ClassSection ||--o{ StudentProfile : "contains (1:N)"
    ClassSection ||--o{ Subject : "has (1:N)"
    
    StudentProfile ||--o{ Attendance : "has (1:N)"
    StudentProfile ||--o{ Grade : "has (1:N)"
    StudentProfile ||--o{ AssessmentScore : "has (1:N)"
    StudentProfile ||--o{ Notification : "related_to (1:N)"
    StudentProfile ||--o{ AuditLog : "related_to (1:N)"
    
    Subject ||--o{ Attendance : "has (1:N)"
    Subject ||--o{ Grade : "has (1:N)"
    Subject ||--o{ Assessment : "has (1:N)"
    Subject ||--|| CategoryWeights : "has (1:1)"
    Subject ||--o{ Notification : "related_to (1:N)"
    
    Assessment ||--o{ AssessmentScore : "has (1:N)"
    Assessment ||--o{ AuditLog : "related_to (1:N)"
    
    User {
        int id PK
        string username UK
        string email
        string password
        string role "admin, teacher, student, parent"
        boolean is_active
        boolean is_staff
        boolean is_superuser
        datetime date_joined
        string first_name
        string last_name
    }
    
    ParentProfile {
        int id PK
        int user_id FK
        string parent_id UK "PRT-YYYY-NNNNN"
        string contact_number
    }
    
    TeacherProfile {
        int id PK
        int user_id FK
        string teacher_id UK "TCH-YYYY-NNNNN"
        string department
    }
    
    StudentProfile {
        int id PK
        int user_id FK
        string student_id UK "STD-YYYY-NNNNN"
        int parent_id FK "nullable"
        string course
        string year_level
        int section_id FK "nullable"
    }
    
    ClassSection {
        int id PK
        string name
        int adviser_id FK "nullable"
    }
    
    Subject {
        int id PK
        string code
        string name
        int teacher_id FK "nullable"
        int section_id FK
    }
    
    Attendance {
        int id PK
        int student_id FK
        int subject_id FK
        date date
        string status "present, absent, late"
    }
    
    Grade {
        int id PK
        int student_id FK
        int subject_id FK
        string term "Midterm, Final"
        decimal grade "max_digits=5, decimal_places=2"
    }
    
    Assessment {
        int id PK
        string name
        string category "Activities, Quizzes, Projects, Exams"
        int subject_id FK
        decimal max_score "max_digits=5, decimal_places=2"
        date date
        string term "Midterm, Final"
        int created_by_id FK "nullable"
        datetime created_at
        datetime updated_at
    }
    
    AssessmentScore {
        int id PK
        int student_id FK
        int assessment_id FK
        decimal score "max_digits=5, decimal_places=2"
        int recorded_by_id FK "nullable"
        datetime created_at
        datetime updated_at
    }
    
    CategoryWeights {
        int id PK
        int subject_id FK
        int activities_weight "default=20"
        int quizzes_weight "default=20"
        int projects_weight "default=30"
        int exams_weight "default=30"
        datetime created_at
        datetime updated_at
    }
    
    Notification {
        int id PK
        int recipient_id FK
        text message
        string notification_type
        boolean is_read "default=False"
        datetime created_at
        int related_student_id FK "nullable"
        int related_subject_id FK "nullable"
        string notification_key "nullable, indexed"
    }
    
    AuditLog {
        int id PK
        int user_id FK "nullable"
        string action
        text details
        int student_id FK "nullable"
        int assessment_id FK "nullable"
        datetime timestamp
    }
    
    Feedback {
        int id PK
        int user_id FK "nullable"
        string feedback_type "general, bug_report, feature_request, etc."
        int rating "1-5, nullable"
        string subject
        text message
        boolean is_anonymous "default=False"
        boolean is_read "default=False"
        boolean is_archived "default=False"
        text admin_response
        datetime responded_at "nullable"
        int responded_by_id FK "nullable"
        datetime created_at
        datetime updated_at
    }
```

## Entity Descriptions

### Core User Management
- **User**: Central authentication and authorization entity. Supports multiple roles (admin, teacher, student, parent).
- **ParentProfile**: Extended profile for parents with contact information.
- **TeacherProfile**: Extended profile for teachers with department information.
- **StudentProfile**: Extended profile for students with academic information (course, year level, section).

### Academic Structure
- **ClassSection**: Represents class sections with an assigned adviser (teacher).
- **Subject**: Course subjects taught by teachers to specific sections.

### Academic Records
- **Attendance**: Daily attendance records for students per subject.
- **Grade**: Term-based grades (Midterm/Final) for students per subject.
- **Assessment**: Assessment items (Activities, Quizzes, Projects, Exams) created by teachers.
- **AssessmentScore**: Individual student scores for each assessment.
- **CategoryWeights**: Weight distribution for assessment categories per subject (must sum to 100%).

### System Features
- **Notification**: System notifications sent to users, with support for deduplication via notification_key.
- **AuditLog**: Audit trail tracking all changes to grades and assessments.
- **Feedback**: User feedback system with support for anonymous submissions and admin responses.

## Key Constraints

1. **Unique Constraints:**
   - One attendance record per student per subject per day
   - One grade per student per subject per term
   - One assessment score per student per assessment
   - One category weight configuration per subject

2. **Business Rules:**
   - Category weights must sum to 100%
   - User can only have one profile type (ParentProfile, TeacherProfile, or StudentProfile)
   - Custom ID generation: PRT-YYYY-NNNNN, TCH-YYYY-NNNNN, STD-YYYY-NNNNN

3. **Cascade Behaviors:**
   - User deletion cascades to profiles
   - Student deletion cascades to attendance, grades, and assessment scores
   - Subject deletion cascades to assessments, attendance, and grades
   - Assessment deletion cascades to assessment scores

## Relationship Cardinalities

- **1:1 Relationships:**
  - User ↔ ParentProfile
  - User ↔ TeacherProfile
  - User ↔ StudentProfile
  - Subject ↔ CategoryWeights

- **1:N Relationships:**
  - Parent → Students (one parent can have multiple children)
  - Teacher → Sections (one teacher can advise multiple sections)
  - Teacher → Subjects (one teacher can teach multiple subjects)
  - Section → Students (one section contains many students)
  - Section → Subjects (one section has many subjects)
  - Student → Attendance, Grades, AssessmentScores
  - Subject → Assessments, Attendance, Grades
  - Assessment → AssessmentScores
  - User → Notifications, AuditLogs, Feedbacks

- **N:M Relationships (via junction entities):**
  - Student ↔ Subject (via Attendance, Grade, AssessmentScore)
  - Student ↔ Assessment (via AssessmentScore)

