# Generated manually for database enhancements
# This migration adds indexes, constraints, views, and triggers compatible with SQLite

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_remove_notification_core_notifi_recipie_idx_and_more'),
    ]

    operations = [
        # Add indexes to User model
        migrations.AddIndex(
            model_name='user',
            index=models.Index(fields=['role', 'is_active'], name='core_user_role_active_idx'),
        ),
        migrations.AddIndex(
            model_name='user',
            index=models.Index(fields=['email'], name='core_user_email_idx'),
        ),
        
        # Add indexes to ParentProfile
        migrations.AddIndex(
            model_name='parentprofile',
            index=models.Index(fields=['parent_id'], name='core_parent_parent_id_idx'),
        ),
        
        # Add indexes to TeacherProfile
        migrations.AddIndex(
            model_name='teacherprofile',
            index=models.Index(fields=['teacher_id'], name='core_teacher_teacher_id_idx'),
        ),
        migrations.AddIndex(
            model_name='teacherprofile',
            index=models.Index(fields=['department'], name='core_teacher_department_idx'),
        ),
        
        # Add indexes to ClassSection
        migrations.AddIndex(
            model_name='classsection',
            index=models.Index(fields=['name'], name='core_section_name_idx'),
        ),
        migrations.AddIndex(
            model_name='classsection',
            index=models.Index(fields=['adviser'], name='core_section_adviser_idx'),
        ),
        
        # Add indexes to StudentProfile
        migrations.AddIndex(
            model_name='studentprofile',
            index=models.Index(fields=['student_id'], name='core_student_student_id_idx'),
        ),
        migrations.AddIndex(
            model_name='studentprofile',
            index=models.Index(fields=['section', 'course'], name='core_student_section_course_idx'),
        ),
        migrations.AddIndex(
            model_name='studentprofile',
            index=models.Index(fields=['section', 'year_level'], name='core_student_section_year_idx'),
        ),
        
        # Add indexes to Subject
        migrations.AddIndex(
            model_name='subject',
            index=models.Index(fields=['code'], name='core_subject_code_idx'),
        ),
        migrations.AddIndex(
            model_name='subject',
            index=models.Index(fields=['teacher', 'section'], name='core_subject_teacher_section_idx'),
        ),
        migrations.AddIndex(
            model_name='subject',
            index=models.Index(fields=['section', 'code'], name='core_subject_section_code_idx'),
        ),
        
        # Add indexes and constraints to Attendance
        migrations.AddIndex(
            model_name='attendance',
            index=models.Index(fields=['student', 'date'], name='core_attendance_student_date_idx'),
        ),
        migrations.AddIndex(
            model_name='attendance',
            index=models.Index(fields=['subject', 'date'], name='core_attendance_subject_date_idx'),
        ),
        migrations.AddIndex(
            model_name='attendance',
            index=models.Index(fields=['student', 'subject', 'date'], name='core_attendance_student_subject_date_idx'),
        ),
        migrations.AddIndex(
            model_name='attendance',
            index=models.Index(fields=['date', 'status'], name='core_attendance_date_status_idx'),
        ),
        migrations.AddConstraint(
            model_name='attendance',
            constraint=models.UniqueConstraint(fields=['student', 'subject', 'date'], name='unique_attendance_per_day'),
        ),
        
        # Add indexes and constraints to Grade
        migrations.AddIndex(
            model_name='grade',
            index=models.Index(fields=['student', 'subject'], name='core_grade_student_subject_idx'),
        ),
        migrations.AddIndex(
            model_name='grade',
            index=models.Index(fields=['student', 'term'], name='core_grade_student_term_idx'),
        ),
        migrations.AddIndex(
            model_name='grade',
            index=models.Index(fields=['subject', 'term'], name='core_grade_subject_term_idx'),
        ),
        migrations.AddConstraint(
            model_name='grade',
            constraint=models.UniqueConstraint(fields=['student', 'subject', 'term'], name='unique_grade_per_term'),
        ),
        
        # Add indexes to Assessment
        migrations.AddIndex(
            model_name='assessment',
            index=models.Index(fields=['subject', 'date'], name='core_assessment_subject_date_idx'),
        ),
        migrations.AddIndex(
            model_name='assessment',
            index=models.Index(fields=['subject', 'term'], name='core_assessment_subject_term_idx'),
        ),
        migrations.AddIndex(
            model_name='assessment',
            index=models.Index(fields=['category', 'date'], name='core_assessment_category_date_idx'),
        ),
        migrations.AddIndex(
            model_name='assessment',
            index=models.Index(fields=['created_by', 'date'], name='core_assessment_created_date_idx'),
        ),
        
        # Add indexes to AssessmentScore
        migrations.AddIndex(
            model_name='assessmentscore',
            index=models.Index(fields=['student', 'assessment'], name='core_score_student_assessment_idx'),
        ),
        migrations.AddIndex(
            model_name='assessmentscore',
            index=models.Index(fields=['assessment', 'score'], name='core_score_assessment_score_idx'),
        ),
        migrations.AddIndex(
            model_name='assessmentscore',
            index=models.Index(fields=['recorded_by', 'created_at'], name='core_score_recorded_created_idx'),
        ),
        
        # Add indexes to AuditLog
        migrations.AddIndex(
            model_name='auditlog',
            index=models.Index(fields=['user', 'timestamp'], name='core_audit_user_timestamp_idx'),
        ),
        migrations.AddIndex(
            model_name='auditlog',
            index=models.Index(fields=['action', 'timestamp'], name='core_audit_action_timestamp_idx'),
        ),
        migrations.AddIndex(
            model_name='auditlog',
            index=models.Index(fields=['student', 'timestamp'], name='core_audit_student_timestamp_idx'),
        ),
        
        # Create database views using RunSQL (SQLite compatible)
        migrations.RunSQL(
            # Create view for student performance summary
            sql="""
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
            """,
            reverse_sql="DROP VIEW IF EXISTS vw_student_performance;"
        ),
        
        # Create view for teacher subject statistics
        migrations.RunSQL(
            sql="""
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
            """,
            reverse_sql="DROP VIEW IF EXISTS vw_teacher_subject_stats;"
        ),
        
        # Create view for attendance summary
        migrations.RunSQL(
            sql="""
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
            """,
            reverse_sql="DROP VIEW IF EXISTS vw_attendance_summary;"
        ),
        
        # Create trigger to automatically update audit log on grade changes
        migrations.RunSQL(
            sql="""
            CREATE TRIGGER IF NOT EXISTS trg_grade_audit
            AFTER INSERT ON core_grade
            BEGIN
                INSERT INTO core_auditlog (user_id, action, details, student_id, timestamp)
                VALUES (
                    (SELECT user_id FROM core_teacherprofile WHERE id = (SELECT teacher_id FROM core_subject WHERE id = NEW.subject_id)),
                    'Grade Updated',
                    'Grade recorded: ' || NEW.grade || ' for student ID ' || (SELECT student_id FROM core_studentprofile WHERE id = NEW.student_id) || ' in term ' || NEW.term,
                    NEW.student_id,
                    datetime('now')
                );
            END;
            """,
            reverse_sql="DROP TRIGGER IF EXISTS trg_grade_audit;"
        ),
        
        # Create trigger to validate assessment score range
        migrations.RunSQL(
            sql="""
            CREATE TRIGGER IF NOT EXISTS trg_validate_assessment_score
            BEFORE INSERT ON core_assessmentscore
            BEGIN
                SELECT CASE
                    WHEN NEW.score < 0 THEN
                        RAISE(ABORT, 'Score cannot be negative')
                    WHEN NEW.score > (SELECT max_score FROM core_assessment WHERE id = NEW.assessment_id) THEN
                        RAISE(ABORT, 'Score cannot exceed maximum score')
                END;
            END;
            """,
            reverse_sql="DROP TRIGGER IF EXISTS trg_validate_assessment_score;"
        ),
        
        # Create trigger to update assessment score on update
        migrations.RunSQL(
            sql="""
            CREATE TRIGGER IF NOT EXISTS trg_validate_assessment_score_update
            BEFORE UPDATE ON core_assessmentscore
            BEGIN
                SELECT CASE
                    WHEN NEW.score < 0 THEN
                        RAISE(ABORT, 'Score cannot be negative')
                    WHEN NEW.score > (SELECT max_score FROM core_assessment WHERE id = NEW.assessment_id) THEN
                        RAISE(ABORT, 'Score cannot exceed maximum score')
                END;
            END;
            """,
            reverse_sql="DROP TRIGGER IF EXISTS trg_validate_assessment_score_update;"
        ),
    ]

