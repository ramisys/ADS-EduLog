from django.urls import path
from . import views

app_name = 'parents'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('child-subjects/', views.child_subjects, name='child_subjects'),
    path('attendance/', views.attendance, name='attendance'),
    path('grades/', views.grades, name='grades'),
    path('reports/', views.reports, name='reports'),
    path('notifications/', views.notifications, name='notifications'),
]
