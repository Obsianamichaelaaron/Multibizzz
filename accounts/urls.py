from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard_router, name='dashboard_router'),
    path('profile/', views.profile_view, name='profile'),
    path('applicant/profile/', views.profile_view, name='applicant_profile'),
    path('employer/profile/', views.profile_view, name='employer_profile'),
    path('ajax/parse-resume/', views.parse_resume_ajax, name='parse_resume_ajax'),
]
