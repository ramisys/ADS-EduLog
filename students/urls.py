from django.urls import path
from . import views

app_name = 'students'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('subjects/', views.subjects, name='subjects'),
    path('attendance/', views.attendance, name='attendance'),
    path('grades/', views.grades, name='grades'),
    path('notifications/', views.notifications, name='notifications'),
]
