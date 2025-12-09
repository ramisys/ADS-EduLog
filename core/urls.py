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
]
