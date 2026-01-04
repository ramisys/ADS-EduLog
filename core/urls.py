from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('about/', views.about, name='about'),
    path('login/', views.login_view, name='login'),
    path('signup/', views.signup_view, name='signup'),
    path('forgot-password/', views.forgot_password_view, name='forgot_password'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('logout/', views.logout_view, name='logout'),
    path('help/', views.user_manual, name='user_manual'),
    path('feedback/', views.feedback_submit, name='feedback_submit'),
    path('feedback/list/', views.feedback_list, name='feedback_list'),
    path('feedback/<int:feedback_id>/', views.feedback_detail, name='feedback_detail'),
    # Semester Management
    path('semesters/', views.semester_management, name='semester_management'),
    path('semesters/create/', views.semester_create, name='semester_create'),
    path('semesters/<int:semester_id>/set-active/', views.semester_set_active, name='semester_set_active'),
    path('semesters/<int:semester_id>/close/', views.semester_close, name='semester_close'),
    path('semesters/<int:semester_id>/archive/', views.semester_archive, name='semester_archive'),
    # Parent Management
    path('parents/', views.parent_management, name='parent_management'),
    path('parents/link-child/', views.link_child_to_parent, name='link_child_to_parent'),
    path('parents/unlink-child/', views.unlink_child_from_parent, name='unlink_child_from_parent'),
]
