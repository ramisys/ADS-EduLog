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
    Attendance,
    Grade,
    Notification,
)

User = get_user_model()

# ==========================
# CONFIGURATION
# ==========================
NUM_TEACHERS = 10
NUM_PARENTS = 5
NUM_STUDENTS = 120
SECTIONS = ["BSIT 1A", "BSIT 1B", "BSIT 2A", "BSIT 2B", "BSIT 3A", "BSIT 3B"]
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
    Notification.objects.all().delete()
    Attendance.objects.all().delete()
    Grade.objects.all().delete()
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
    for i in range(NUM_PARENTS):
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
    print(f"   Created {len(parents)} parents")
    return parents


def create_sections(teachers):
    sections = []
    for sec_name in SECTIONS:
        section = ClassSection.objects.create(name=sec_name, adviser=random.choice(teachers))
        sections.append(section)
    print(f"   Created {len(sections)} sections")
    return sections


def create_students(parents, sections):
    students = []
    for i in range(NUM_STUDENTS):
        username = f"student{i+1}"
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
            parent=random.choice(parents),
            course="BSIT",
            year_level=random.choice(["1st Year", "2nd Year", "3rd Year"]),
            section=random.choice(sections),
        )
        students.append(student)
    print(f"   Created {len(students)} students")
    return students


def create_subjects(sections, teachers):
    subjects = []
    for section in sections:
        for _ in range(2):  # two subjects per section
            code, name = random.choice(SUBJECT_POOL)
            subject = Subject.objects.create(
                code=f"{code}-{section.name.replace(' ', '')}",
                name=name,
                teacher=random.choice(teachers),
                section=section,
            )
            subjects.append(subject)
    print(f"   Created {len(subjects)} subjects")
    return subjects


def create_attendance(students, subjects):
    records = 0
    for student in students:
        for subject in random.sample(subjects, min(3, len(subjects))):
            Attendance.objects.create(
                student=student, subject=subject, status=random.choice(["present", "absent", "late"])
            )
            records += 1
    print(f"   Created {records} attendance entries")


def create_grades(students, subjects):
    records = 0
    for student in students:
        for subject in random.sample(subjects, min(3, len(subjects))):
            Grade.objects.create(
                student=student,
                subject=subject,
                term=random.choice(["Midterm", "Finals"]),
                grade=round(random.uniform(70, 99), 2),
            )
            records += 1
    print(f"   Created {records} grade records")


def create_notifications(students):
    for student in students:
        Notification.objects.create(
            recipient=student.user,
            message="Your grade has been updated.",
            is_read=random.choice([True, False]),
        )
    print(f"   Created {len(students)} notifications")


def main():
    clear_existing_data()

    with atomic_section("Generating teachers"):
        teachers = create_teachers()

    with atomic_section("Generating parents"):
        parents = create_parents()

    with atomic_section("Generating sections"):
        sections = create_sections(teachers)

    with atomic_section("Generating students"):
        students = create_students(parents, sections)

    with atomic_section("Generating subjects"):
        subjects = create_subjects(sections, teachers)

    with atomic_section("Generating attendance"):
        create_attendance(students, subjects)

    with atomic_section("Generating grades"):
        create_grades(students, subjects)

    with atomic_section("Generating notifications"):
        create_notifications(students)

    print("\n=== DATASET GENERATION COMPLETE ===")


if __name__ == "__main__":
    main()
