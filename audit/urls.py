from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('audit-trail/', views.admin_audit_trail, name='admin_audit_trail'),
    path('analytics/', views.admin_analytics, name='admin_analytics'),
    path('users/', views.admin_users, name='admin_users'),
    path('users/<int:user_id>/status/', views.admin_toggle_user_status, name='admin_toggle_user_status'),
    path('users/<int:user_id>/delete/', views.admin_delete_user, name='admin_delete_user'),
]
