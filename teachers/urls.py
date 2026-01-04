from django.urls import path
from . import views

app_name = 'teachers'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('subjects/', views.subjects, name='subjects'),
    path('subjects/assign/', views.assign_subject, name='assign_subject'),
    path('subjects/remove/<int:assignment_id>/', views.remove_assignment, name='remove_assignment'),
    path('subjects/get-sections/', views.get_sections_by_year_level, name='get_sections_by_year_level'),
    path('subjects/get-subjects/', views.get_subjects_by_year_level, name='get_subjects_by_year_level'),
    path('sections/', views.sections, name='sections'),
    path('students/', views.students, name='students'),
    path('students/add/', views.add_student, name='add_student'),
    path('students/enroll/', views.enroll_student, name='enroll_student'),
    path('students/search/', views.search_students, name='search_students'),
    path('students/eligible-assignments/', views.get_eligible_assignments, name='get_eligible_assignments'),
    path('students/assign-section/', views.assign_student_section, name='assign_student_section'),
    path('students/enroll/create/', views.create_enrollment, name='create_enrollment'),
    path('attendance/', views.attendance, name='attendance'),
    path('notifications/', views.notifications, name='notifications'),
    path('grades/', views.grades, name='grades'),
    path('add-assessment/', views.add_assessment, name='add_assessment'),
    path('update-score/', views.update_score, name='update_score'),
    path('update-category-weights/', views.update_category_weights, name='update_category_weights'),
    path('reports/', views.reports, name='reports'),
]
