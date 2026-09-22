from django.urls import path
from . import views

urlpatterns = [
    path('careers/', views.careers_public, name='careers'),
    path('careers/<int:pk>/', views.job_detail_public, name='job_detail_public'),
    
    # Applicant routes
    path('applicant/jobs/', views.applicant_jobs, name='applicant_jobs'),
    path('applicant/saved/', views.applicant_saved_jobs, name='applicant_saved_jobs'),
    path('ajax/toggle-save/<int:pk>/', views.toggle_save_job_ajax, name='toggle_save_job_ajax'),
    
    # Employer routes (Controlled Hiring Workflow)
    path('employer/jobs/', views.employer_jobs, name='employer_jobs'),
    path('employer/jobs/post/', views.employer_post_job, name='employer_post_job'),
    path('employer/post-job/', views.employer_post_job, name='post_job'),
    path('employer/jobs/<int:pk>/edit/', views.employer_edit_job, name='employer_edit_job'),
    path('employer/jobs/<int:pk>/delete/', views.employer_delete_job, name='employer_delete_job'),
    path('employer/request-talent/', views.employer_request_talent, name='employer_request_talent'),
    path('employer/talent-requests/', views.employer_talent_requests, name='employer_talent_requests'),
    path('employer/talent-requests/<int:pk>/', views.employer_talent_request_detail, name='employer_talent_request_detail'),
    
    # Admin routes
    path('admin-portal/jobs/', views.admin_jobs, name='admin_jobs'),
    path('admin-portal/jobs/create/', views.admin_create_job, name='admin_create_job'),
    path('admin-portal/jobs/<int:pk>/edit/', views.admin_edit_job, name='admin_edit_job'),
    path('admin-portal/jobs/<int:pk>/delete/', views.admin_delete_job, name='admin_delete_job'),
    path('admin-portal/talent-requests/', views.admin_employer_requests, name='admin_employer_requests'),
    path('admin-portal/talent-requests/<int:pk>/', views.admin_employer_request_detail, name='admin_employer_request_detail'),
    path('admin-portal/talent-requests/<int:pk>/create-job/', views.admin_create_job_from_request, name='admin_create_job_from_request'),
]

