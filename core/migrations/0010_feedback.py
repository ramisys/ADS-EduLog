# Generated manually for Feedback model

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def cleanup_orphaned_data(apps, schema_editor):
    """Clean up orphaned data in core_studentdashboardstats before creating new table"""
    db_alias = schema_editor.connection.alias
    
    # Clean up orphaned foreign keys (foreign keys are already disabled by RunSQL above)
    with schema_editor.connection.cursor() as cursor:
        try:
            # Check if the problematic table exists and clean up orphaned foreign keys
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='core_studentdashboardstats'
            """)
            table_exists = cursor.fetchone()
            
            if table_exists:
                # Delete orphaned rows that reference non-existent students
                cursor.execute("""
                    DELETE FROM core_studentdashboardstats 
                    WHERE student_id NOT IN (SELECT id FROM core_studentprofile)
                """)
                deleted_count = cursor.rowcount
                if deleted_count > 0:
                    print(f"Cleaned up {deleted_count} orphaned records from core_studentdashboardstats")
        except Exception as e:
            # Table might not exist or already cleaned, continue
            print(f"Note: Could not clean up orphaned data: {e}")


def reverse_cleanup(apps, schema_editor):
    """Reverse operation - nothing to do"""
    pass


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0009_database_enhancements'),
    ]

    operations = [
        # Disable foreign key checks temporarily to allow migration with orphaned data
        migrations.RunSQL(
            sql="PRAGMA foreign_keys = OFF;",
            reverse_sql="PRAGMA foreign_keys = ON;"
        ),
        # Clean up orphaned data first
        migrations.RunPython(cleanup_orphaned_data, reverse_cleanup),
        migrations.CreateModel(
            name='Feedback',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('feedback_type', models.CharField(choices=[('general', 'General Feedback'), ('bug_report', 'Bug Report'), ('feature_request', 'Feature Request'), ('improvement', 'Improvement Suggestion'), ('compliment', 'Compliment')], default='general', max_length=20)),
                ('rating', models.IntegerField(blank=True, choices=[(1, '1 - Poor'), (2, '2 - Fair'), (3, '3 - Good'), (4, '4 - Very Good'), (5, '5 - Excellent')], help_text='Overall system rating (1-5)', null=True)),
                ('subject', models.CharField(blank=True, help_text='Brief subject/title of feedback', max_length=200)),
                ('message', models.TextField(help_text='Detailed feedback message')),
                ('is_anonymous', models.BooleanField(default=False, help_text='Submit feedback anonymously')),
                ('is_read', models.BooleanField(default=False)),
                ('is_archived', models.BooleanField(default=False)),
                ('admin_response', models.TextField(blank=True, help_text='Admin response to feedback')),
                ('responded_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('responded_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='feedback_responses', to=settings.AUTH_USER_MODEL)),
                ('user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='feedbacks', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Feedback',
                'verbose_name_plural': 'Feedbacks',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='feedback',
            index=models.Index(fields=['user', 'created_at'], name='core_feedba_user_id_created_idx'),
        ),
        migrations.AddIndex(
            model_name='feedback',
            index=models.Index(fields=['feedback_type', 'created_at'], name='core_feedba_feedback_created_idx'),
        ),
        migrations.AddIndex(
            model_name='feedback',
            index=models.Index(fields=['is_read', 'created_at'], name='core_feedba_is_read_created_idx'),
        ),
        migrations.AddIndex(
            model_name='feedback',
            index=models.Index(fields=['rating', 'created_at'], name='core_feedba_rating_created_idx'),
        ),
        # Re-enable foreign key checks
        migrations.RunSQL(
            sql="PRAGMA foreign_keys = ON;",
            reverse_sql="PRAGMA foreign_keys = OFF;"
        ),
    ]

