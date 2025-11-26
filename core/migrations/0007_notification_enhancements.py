# Generated manually for notification enhancements

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_assessment_auditlog_assessmentscore_categoryweights'),
    ]

    operations = [
        migrations.AddField(
            model_name='notification',
            name='notification_type',
            field=models.CharField(choices=[('attendance_absent', 'Attendance - Absent'), ('attendance_late', 'Attendance - Late'), ('performance_at_risk', 'Performance - At Risk'), ('performance_improved', 'Performance - Improved'), ('performance_warning_attendance', 'Performance Warning - Low Attendance'), ('performance_warning_gpa', 'Performance Warning - Low GPA'), ('consecutive_absences', 'Consecutive Absences'), ('teacher_student_at_risk', 'Teacher - Student At Risk'), ('teacher_consecutive_absences', 'Teacher - Consecutive Absences'), ('general', 'General')], default='general', max_length=50),
        ),
        migrations.AddField(
            model_name='notification',
            name='notification_key',
            field=models.CharField(blank=True, db_index=True, max_length=200, null=True),
        ),
        migrations.AddField(
            model_name='notification',
            name='related_student',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='related_notifications', to='core.studentprofile'),
        ),
        migrations.AddField(
            model_name='notification',
            name='related_subject',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='related_notifications', to='core.subject'),
        ),
        migrations.AlterField(
            model_name='notification',
            name='recipient',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterModelOptions(
            name='notification',
            options={'ordering': ['-created_at']},
        ),
        migrations.AddIndex(
            model_name='notification',
            index=models.Index(fields=['recipient', 'is_read'], name='core_notifi_recipie_idx'),
        ),
    ]

