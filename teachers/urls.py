from django.urls import path
from . import views

app_name = 'teachers'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('subjects/', views.subjects, name='subjects'),
    path('sections/', views.sections, name='sections'),
    path('students/', views.students, name='students'),
    path('attendance/', views.attendance, name='attendance'),
    path('notifications/', views.notifications, name='notifications'),
    path('grades/', views.grades, name='grades'),
    path('add-assessment/', views.add_assessment, name='add_assessment'),
    path('update-score/', views.update_score, name='update_score'),
    path('update-category-weights/', views.update_category_weights, name='update_category_weights'),
    path('reports/', views.reports, name='reports'),
]
