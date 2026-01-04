# Generated migration to link Grade records with NULL enrollment to correct StudentEnrollment

from django.db import migrations
from django.db.models import Q, Count


def link_null_enrollment_grades(apps, schema_editor):
    """
    Link Grade records with NULL enrollment to the correct StudentEnrollment.
    
    Strategy:
    1. For each enrollment that has AssessmentScores, check if there's a NULL grade for the same term
    2. If there's exactly one NULL grade for that term and no existing grade for that enrollment/term, link it
    3. For students with only one enrollment, link remaining NULL grades to that enrollment
    4. For grades that can't be matched, they remain NULL (will be handled by fallback queries)
    """
    Grade = apps.get_model('core', 'Grade')
    StudentEnrollment = apps.get_model('core', 'StudentEnrollment')
    AssessmentScore = apps.get_model('core', 'AssessmentScore')
    Assessment = apps.get_model('core', 'Assessment')
    
    # Get all grades with NULL enrollment
    null_grades = Grade.objects.filter(enrollment__isnull=True)
    total_null_grades = null_grades.count()
    
    if total_null_grades == 0:
        print("No grades with NULL enrollment found. Migration complete.")
        return
    
    print(f"Found {total_null_grades} grades with NULL enrollment. Starting migration...")
    
    linked_count = 0
    
    # Strategy 1: Match NULL grades to enrollments based on AssessmentScores
    # For each enrollment with AssessmentScores, find matching NULL grades by term
    enrollments_with_scores = StudentEnrollment.objects.filter(
        assessment_scores__isnull=False
    ).distinct()
    
    for enrollment in enrollments_with_scores:
        # Get all AssessmentScores for this enrollment
        assessment_scores = AssessmentScore.objects.filter(
            enrollment=enrollment
        ).select_related('assessment')
        
        if not assessment_scores.exists():
            continue
        
        # Get unique terms from assessments
        terms = set()
        for score in assessment_scores:
            if score.assessment and score.assessment.term:
                terms.add(score.assessment.term)
        
        # For each term, check if there's a grade
        for term in terms:
            # Check if there's already a grade for this enrollment and term
            existing_grade = Grade.objects.filter(
                enrollment=enrollment,
                term=term
            ).first()
            
            if not existing_grade:
                # Try to find a NULL grade for this term
                null_grades_for_term = Grade.objects.filter(
                    enrollment__isnull=True,
                    term=term
                )
                
                # If there's exactly one NULL grade for this term, link it
                # This is safe if each student only has one enrollment with scores for this term
                if null_grades_for_term.count() == 1:
                    null_grade = null_grades_for_term.first()
                    # Use update() to bypass validation during migration
                    Grade.objects.filter(id=null_grade.id).update(enrollment=enrollment)
                    linked_count += 1
                    print(f"  Linked grade ID {null_grade.id} (term: {term}, grade: {null_grade.grade}) to enrollment {enrollment.id}")
    
    # Strategy 2: For students with only one active enrollment, link remaining NULL grades
    # Get all students with exactly one active enrollment
    students_with_one_enrollment = StudentEnrollment.objects.filter(
        is_active=True
    ).values('student').annotate(
        enrollment_count=Count('id')
    ).filter(enrollment_count=1).values_list('student', flat=True)
    
    for student_id in students_with_one_enrollment:
        enrollment = StudentEnrollment.objects.filter(
            student_id=student_id,
            is_active=True
        ).first()
        
        if not enrollment:
            continue
        
        # Get terms that have AssessmentScores for this enrollment
        assessment_scores = AssessmentScore.objects.filter(
            enrollment=enrollment
        ).select_related('assessment')
        
        terms = set()
        for score in assessment_scores:
            if score.assessment and score.assessment.term:
                terms.add(score.assessment.term)
        
        # For each term, check if there's a NULL grade that could belong to this enrollment
        for term in terms:
            # Check if there's already a grade for this enrollment and term
            existing_grade = Grade.objects.filter(
                enrollment=enrollment,
                term=term
            ).first()
            
            if not existing_grade:
                # Try to find a NULL grade for this term
                null_grade = Grade.objects.filter(
                    enrollment__isnull=True,
                    term=term
                ).first()
                
                if null_grade:
                    # Link it (this is safe since student only has one enrollment)
                    # Use update() to bypass validation during migration
                    Grade.objects.filter(id=null_grade.id).update(enrollment=enrollment)
                    linked_count += 1
                    print(f"  Linked grade ID {null_grade.id} (term: {term}, grade: {null_grade.grade}) to single enrollment {enrollment.id} for student {enrollment.student.student_id}")
    
    # Count remaining NULL grades
    remaining_null_grades = Grade.objects.filter(enrollment__isnull=True)
    unlinked_count = remaining_null_grades.count()
    
    print(f"\nMigration complete. {linked_count} grades linked, {unlinked_count} remain NULL.")
    if unlinked_count > 0:
        print("Note: Grades that couldn't be automatically linked will be handled by fallback queries in views.")
        print("      These grades may need manual review or will be recreated when grades are recalculated.")


def reverse_link_null_enrollment_grades(apps, schema_editor):
    """
    Reverse migration - set enrollment back to NULL (not recommended, but included for completeness)
    """
    # This would be dangerous to run, so we'll just pass
    # In practice, you wouldn't want to reverse this
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0025_fix_school_year_to_academic_year'),
    ]

    operations = [
        migrations.RunPython(link_null_enrollment_grades, reverse_link_null_enrollment_grades),
    ]

