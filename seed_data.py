import os
import django
import random
from contextlib import contextmanager

# Configure Django settings BEFORE importing Django models
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "edulog.settings")
django.setup()

from django.contrib.auth import get_user_model
from django.db import transaction

from core.models import (
    ParentProfile,
    TeacherProfile,
    StudentProfile,
    ClassSection,
    Subject,
    YearLevel,
    Semester,
)

User = get_user_model()

# ==========================
# CONFIGURATION
# ==========================
NUM_TEACHERS = 4
SECTIONS_PER_TEACHER = 4
MIN_SUBJECTS_PER_TEACHER = 2
STUDENTS_PER_SECTION = 10
# Subjects organized by year level and semester
SUBJECTS_BY_YEAR_LEVEL = {
    1: {
        'first_semester': [
            ("IT101", "Introduction to Information Technology"),
            ("IT102", "Programming Fundamentals"),
        ],
        'second_semester': [
            ("IT103", "Computer Systems"),
            ("IT104", "Mathematics for IT"),
        ],
    },
    2: {
        'first_semester': [
            ("IT201", "Data Structures and Algorithms"),
            ("IT202", "Object-Oriented Programming"),
        ],
        'second_semester': [
            ("IT203", "Computer Networks"),
            ("IT204", "Web Development"),
        ],
    },
    3: {
        'first_semester': [
            ("IT301", "Database Systems"),
            ("IT302", "Software Engineering"),
        ],
        'second_semester': [
            ("IT303", "Operating Systems"),
            ("IT304", "Mobile Application Development"),
        ],
    },
    4: {
        'first_semester': [
            ("IT401", "Capstone Project"),
            ("IT402", "IT Project Management"),
        ],
        'second_semester': [
            ("IT403", "Information Security"),
            ("IT404", "Cloud Computing"),
        ],
    },
}

# ==========================
# HELPERS
# ==========================
FIRST_NAMES = [
    "Miguel",
    "Angel",
    "John",
    "Claire",
    "Mark",
    "Paulo",
    "Jennie",
    "Sophia",
    "Liam",
    "Chloe",
]
LAST_NAMES = ["Reyes", "Santos", "Cruz", "Mendoza", "Velasco", "Torres", "Lopez", "Delos Santos"]


def rand_name():
    return random.choice(FIRST_NAMES), random.choice(LAST_NAMES)


@contextmanager
def atomic_section(title: str):
    print(f"\n→ {title} ...", end=" ")
    with transaction.atomic():
        yield
    print("done.")


def clear_existing_data():
    print("Clearing existing seed data ...", end=" ")
    Subject.objects.all().delete()
    StudentProfile.objects.all().delete()
    ParentProfile.objects.all().delete()
    ClassSection.objects.all().delete()
    TeacherProfile.objects.all().delete()
    YearLevel.objects.all().delete()
    Semester.objects.all().delete()
    (
        User.objects.filter(role__in=["teacher", "student", "parent"])
        .exclude(is_superuser=True)
        .delete()
    )
    print("done.")


def create_teachers():
    teachers = []
    for i in range(NUM_TEACHERS):
        username = f"teacher{i+1}"
        first, last = rand_name()
        user = User.objects.create_user(
            username=username,
            email=f"{username}@example.com",
            password="TeacherPass123",
            role="teacher",
            first_name=first,
            last_name=last,
        )
        teacher = TeacherProfile.objects.create(
            user=user, department=random.choice(["IT", "Computer Science", "Engineering"])
        )
        teachers.append(teacher)
    print(f"   Created {len(teachers)} teachers")
    return teachers


def create_parents():
    """Create parents without relating them to students"""
    parents = []
    # Calculate total parents needed: NUM_TEACHERS * SECTIONS_PER_TEACHER * STUDENTS_PER_SECTION
    total_parents_needed = NUM_TEACHERS * SECTIONS_PER_TEACHER * STUDENTS_PER_SECTION
    for i in range(total_parents_needed):
        username = f"parent{i+1}"
        first, last = rand_name()
        user = User.objects.create_user(
            username=username,
            email=f"{username}@example.com",
            password="ParentPass123",
            role="parent",
            first_name=first,
            last_name=last,
        )
        parent = ParentProfile.objects.create(
            user=user, contact_number=f"09{random.randint(100000000, 999999999)}"
        )
        parents.append(parent)
    print(f"   Created {len(parents)} parents (not related to students)")
    return parents


def create_year_levels():
    """Create year level records (1st Year, 2nd Year, 3rd Year, 4th Year)"""
    year_levels = []
    for level in range(1, 5):
        year_level, created = YearLevel.objects.get_or_create(
            level=level,
            defaults={
                'name': f'{level}{"st" if level == 1 else "nd" if level == 2 else "rd" if level == 3 else "th"} Year',
                'order': level,
                'is_active': True,
            }
        )
        year_levels.append(year_level)
    print(f"   Created/verified {len(year_levels)} year levels")
    return year_levels


def create_sections(year_levels):
    """Create sections without relating them to teachers"""
    sections = []
    # Create sections for each year level
    for year_level in year_levels:
        for i in range(SECTIONS_PER_TEACHER):
            sec_name = f"BSIT {year_level.level}{chr(65 + i)}"  # 1A, 1B, 1C, 1D, then 2A, 2B, etc.
            section = ClassSection.objects.create(
                name=sec_name,
                year_level=year_level,
                adviser=None  # No adviser assigned
            )
            sections.append(section)
    print(f"   Created {len(sections)} sections ({SECTIONS_PER_TEACHER} per year level)")
    return sections


def create_students(year_levels):
    """Create students without relating them to parents or sections"""
    students = []
    student_counter = 1
    
    # Create students for each year level
    for year_level in year_levels:
        for i in range(STUDENTS_PER_SECTION * SECTIONS_PER_TEACHER):
            username = f"student{student_counter}"
            first, last = rand_name()
            user = User.objects.create_user(
                username=username,
                email=f"{username}@example.com",
                password="StudentPass123",
                role="student",
                first_name=first,
                last_name=last,
            )
            
            student = StudentProfile.objects.create(
                user=user,
                parent=None,  # No parent assigned
                course="BSIT",
                year_level=year_level,
                section=None,  # No section assigned
            )
            students.append(student)
            student_counter += 1
    
    print(f"   Created {len(students)} students ({STUDENTS_PER_SECTION * SECTIONS_PER_TEACHER} per year level)")
    return students


def create_semesters():
    """Create first and second semester for the current academic year"""
    from datetime import date, timedelta
    
    # Get current year for academic year
    current_year = date.today().year
    academic_year = f"{current_year}-{current_year + 1}"
    
    # First Semester: August to December
    first_sem_start = date(current_year, 8, 1)
    first_sem_end = date(current_year, 12, 31)
    
    # Second Semester: January to May
    second_sem_start = date(current_year + 1, 1, 1)
    second_sem_end = date(current_year + 1, 5, 31)
    
    # Create or get first semester
    first_semester, created = Semester.objects.get_or_create(
        name="1st Semester",
        academic_year=academic_year,
        defaults={
            'start_date': first_sem_start,
            'end_date': first_sem_end,
            'status': 'active',
            'is_current': True,  # Set first semester as current
        }
    )
    
    # Create or get second semester
    second_semester, created = Semester.objects.get_or_create(
        name="2nd Semester",
        academic_year=academic_year,
        defaults={
            'start_date': second_sem_start,
            'end_date': second_sem_end,
            'status': 'upcoming',
            'is_current': False,
        }
    )
    
    # Ensure only one current semester
    if first_semester.is_current:
        Semester.objects.exclude(pk=first_semester.pk).update(is_current=False)
    
    print(f"   Created/verified semesters: {first_semester} (current), {second_semester}")
    return first_semester, second_semester


def create_subjects(year_levels, first_semester, second_semester):
    """Create subjects as master catalog entries organized by semester"""
    subjects = []
    
    # Create subjects for each year level, organized by semester
    for year_level in year_levels:
        level = year_level.level
        if level in SUBJECTS_BY_YEAR_LEVEL:
            year_subjects = SUBJECTS_BY_YEAR_LEVEL[level]
            
            # Create first semester subjects
            for code, name in year_subjects.get('first_semester', []):
                subject = Subject.objects.create(
                    code=code,
                    name=name,
                    description=f"Master catalog entry for {name} ({year_level.name}) - 1st Semester",
                    is_active=True,
                )
                subjects.append(subject)
            
            # Create second semester subjects
            for code, name in year_subjects.get('second_semester', []):
                subject = Subject.objects.create(
                    code=code,
                    name=name,
                    description=f"Master catalog entry for {name} ({year_level.name}) - 2nd Semester",
                    is_active=True,
                )
                subjects.append(subject)
    
    print(f"   Created {len(subjects)} subjects (master catalog, organized by semester)")
    return subjects


def main():
    clear_existing_data()

    with atomic_section("Generating year levels"):
        year_levels = create_year_levels()

    with atomic_section("Generating semesters"):
        first_semester, second_semester = create_semesters()

    with atomic_section("Generating teachers"):
        teachers = create_teachers()

    with atomic_section("Generating sections"):
        sections = create_sections(year_levels)

    with atomic_section("Generating parents"):
        parents = create_parents()

    with atomic_section("Generating students"):
        students = create_students(year_levels)

    with atomic_section("Generating subjects"):
        subjects = create_subjects(year_levels, first_semester, second_semester)

    print("\n=== DATASET GENERATION COMPLETE ===")
    print(f"\nSummary:")
    print(f"  - Year Levels: {len(year_levels)}")
    print(f"  - Semesters: 1st Semester (current), 2nd Semester (upcoming)")
    print(f"  - Teachers: {len(teachers)}")
    print(f"  - Sections: {len(sections)} ({SECTIONS_PER_TEACHER} per year level, no adviser assigned)")
    print(f"  - Subjects: {len(subjects)} (master catalog, organized by semester)")
    print(f"  - Students: {len(students)} ({STUDENTS_PER_SECTION * SECTIONS_PER_TEACHER} per year level, no section/parent assigned)")
    print(f"  - Parents: {len(parents)} (not related to students)")
    print(f"\nNote: No relationships created. Entities are standalone.")
    print(f"\nSubjects are organized by semester:")
    for year_level in year_levels:
        level = year_level.level
        if level in SUBJECTS_BY_YEAR_LEVEL:
            first_sem_count = len(SUBJECTS_BY_YEAR_LEVEL[level].get('first_semester', []))
            second_sem_count = len(SUBJECTS_BY_YEAR_LEVEL[level].get('second_semester', []))
            print(f"  - {year_level.name}: {first_sem_count} subjects (1st Sem), {second_sem_count} subjects (2nd Sem)")


if __name__ == "__main__":
    main()
