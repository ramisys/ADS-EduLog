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
)

User = get_user_model()

# ==========================
# CONFIGURATION
# ==========================
NUM_TEACHERS = 4
SECTIONS_PER_TEACHER = 4
MIN_SUBJECTS_PER_TEACHER = 2
STUDENTS_PER_SECTION = 10
SUBJECT_POOL = [
    ("IT101", "Intro to IT"),
    ("IT102", "Programming 1"),
    ("IT201", "Data Structures"),
    ("IT202", "OOP"),
    ("IT203", "Networks"),
    ("IT301", "Database Systems"),
]

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
    print(f"   Created {len(parents)} parents (1 per student)")
    return parents


def create_sections(teachers):
    sections = []
    section_counter = 1
    # Each teacher gets SECTIONS_PER_TEACHER sections
    for teacher in teachers:
        for i in range(SECTIONS_PER_TEACHER):
            sec_name = f"BSIT {section_counter}{chr(65 + i)}"  # 1A, 1B, 1C, 1D, then 2A, 2B, etc.
            section = ClassSection.objects.create(name=sec_name, adviser=teacher)
            sections.append(section)
        section_counter += 1
    print(f"   Created {len(sections)} sections ({SECTIONS_PER_TEACHER} per teacher)")
    return sections


def create_students(parents, sections):
    students = []
    student_counter = 1
    parent_index = 0
    
    # Each section needs STUDENTS_PER_SECTION students
    for section in sections:
        for i in range(STUDENTS_PER_SECTION):
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
            # Assign parent: each student gets a unique parent
            parent = parents[parent_index]
            parent_index += 1
            
            # Determine year level based on section name (extract number from section name)
            section_num = ''.join(filter(str.isdigit, section.name))
            if section_num:
                year_num = int(section_num)
                if year_num == 1:
                    year_level = "1st Year"
                elif year_num == 2:
                    year_level = "2nd Year"
                elif year_num == 3:
                    year_level = "3rd Year"
                else:
                    year_level = f"{year_num}th Year"
            else:
                year_level = "1st Year"
            
            student = StudentProfile.objects.create(
                user=user,
                parent=parent,
                course="BSIT",
                year_level=year_level,
                section=section,
            )
            students.append(student)
            student_counter += 1
    
    print(f"   Created {len(students)} students ({STUDENTS_PER_SECTION} per section)")
    return students


def create_subjects(sections, teachers):
    subjects = []
    # Track teacher assignments to ensure each teacher teaches at least MIN_SUBJECTS_PER_TEACHER subjects
    teacher_assignments = {teacher.id: {'sections': set(), 'subjects': set()} for teacher in teachers}
    
    # Group sections by teacher (adviser)
    sections_by_teacher = {teacher: [] for teacher in teachers}
    for section in sections:
        sections_by_teacher[section.adviser].append(section)
    
    # Assign subjects to each teacher
    # Each teacher teaches at least MIN_SUBJECTS_PER_TEACHER subjects
    # Each subject is taught in all sections that the teacher advises
    for teacher in teachers:
        teacher_sections = sections_by_teacher[teacher]
        # Select at least MIN_SUBJECTS_PER_TEACHER subjects for this teacher
        num_subjects = max(MIN_SUBJECTS_PER_TEACHER, random.randint(MIN_SUBJECTS_PER_TEACHER, len(SUBJECT_POOL)))
        selected_subjects = random.sample(SUBJECT_POOL, num_subjects)
        
        # For each selected subject, create it in each section the teacher advises
        for code, name in selected_subjects:
            for section in teacher_sections:
                subject = Subject.objects.create(
                    code=f"{code}-{section.name.replace(' ', '')}",
                    name=name,
                    teacher=teacher,
                    section=section,
                )
                subjects.append(subject)
                teacher_assignments[teacher.id]['sections'].add(section.id)
                teacher_assignments[teacher.id]['subjects'].add((code, name))
    
    # Verify assignments
    teachers_with_enough_subjects = sum(1 for t in teacher_assignments.values() if len(t['subjects']) >= MIN_SUBJECTS_PER_TEACHER)
    
    print(f"   Created {len(subjects)} subjects")
    print(f"   Teachers with at least {MIN_SUBJECTS_PER_TEACHER} subjects: {teachers_with_enough_subjects}/{len(teachers)}")
    for teacher in teachers:
        num_subjects = len(teacher_assignments[teacher.id]['subjects'])
        num_sections = len(teacher_assignments[teacher.id]['sections'])
        print(f"      {teacher.user.get_full_name()}: {num_subjects} subjects across {num_sections} sections")
    return subjects


def main():
    clear_existing_data()

    with atomic_section("Generating teachers"):
        teachers = create_teachers()

    with atomic_section("Generating sections"):
        sections = create_sections(teachers)

    with atomic_section("Generating parents"):
        parents = create_parents()

    with atomic_section("Generating students"):
        students = create_students(parents, sections)

    with atomic_section("Generating subjects"):
        subjects = create_subjects(sections, teachers)

    print("\n=== DATASET GENERATION COMPLETE ===")
    print(f"\nSummary:")
    print(f"  - Teachers: {len(teachers)}")
    print(f"  - Sections: {len(sections)} ({SECTIONS_PER_TEACHER} per teacher)")
    print(f"  - Subjects: {len(subjects)}")
    print(f"  - Students: {len(students)} ({STUDENTS_PER_SECTION} per section)")
    print(f"  - Parents: {len(parents)} (1 per student)")


if __name__ == "__main__":
    main()
