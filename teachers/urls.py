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
    path('reports/', views.reports, name='reports'),
]
