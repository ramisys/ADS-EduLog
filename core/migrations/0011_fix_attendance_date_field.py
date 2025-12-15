# Generated manually to fix attendance date field
# This migration removes auto_now_add from the date field to allow manual date setting
# We need to drop views that reference core_attendance before altering the table

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0010_feedback'),
    ]

    operations = [
        # Drop views that reference core_attendance before altering the table
        migrations.RunSQL(
            sql="DROP VIEW IF EXISTS vw_student_performance;",
            reverse_sql="""
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
            """
        ),
        migrations.RunSQL(
            sql="DROP VIEW IF EXISTS vw_teacher_subject_stats;",
            reverse_sql="""
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
            """
        ),
        migrations.RunSQL(
            sql="DROP VIEW IF EXISTS vw_attendance_summary;",
            reverse_sql="""
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
            """
        ),
        # Now alter the field
        migrations.AlterField(
            model_name='attendance',
            name='date',
            field=models.DateField(),
        ),
        # Recreate the views after the table is altered
        migrations.RunSQL(
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
    ]

