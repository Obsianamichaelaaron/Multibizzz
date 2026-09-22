from django.urls import path
from . import views

urlpatterns = [
    # Dashboards
    path('applicant/dashboard/', views.applicant_dashboard, name='applicant_dashboard'),
    path('employer/dashboard/', views.employer_dashboard, name='employer_dashboard'),

    # Applicant routes
    path('apply/<int:pk>/', views.apply_job, name='apply_job'),
    path('apply/<int:pk>/ajax/ai-check/', views.check_application_ai_ajax, name='check_application_ai_ajax'),
    path('apply/<int:pk>/ajax/ai-generate-cover-letter/', views.generate_cover_letter_ai_ajax, name='generate_cover_letter_ai_ajax'),
    path('my-applications/', views.my_applications, name='my_applications'),
    path('withdraw/<int:pk>/', views.withdraw_application, name='withdraw_application'),

    # Employer routes
    path('employer/candidates/', views.employer_candidates, name='employer_candidates'),
    path('employer/candidates/<int:pk>/', views.employer_candidate_detail, name='employer_candidate_detail'),
    path('employer/candidates/<int:pk>/resume/', views.view_candidate_resume, name='view_candidate_resume'),
    path('employer/candidates/<int:pk>/resume/file/', views.view_candidate_resume_file, name='view_candidate_resume_file'),
    path('employer/candidates/<int:pk>/status/', views.update_application_status, name='update_application_status'),
    path('employer/candidates/<int:pk>/decide/', views.employer_decide_candidate, name='employer_decide_candidate'),
    path('employer/candidates/<int:pk>/schedule-interview/', views.schedule_interview, name='schedule_interview'),
    path('employer/recommended-candidates/', views.recommended_candidates, name='recommended_candidates'),

    # Admin candidate management routes
    path('admin-portal/jobs/<int:pk>/candidates/', views.admin_job_candidates, name='admin_job_candidates'),
    path('admin-portal/jobs/<int:pk>/notify-qualified/', views.admin_notify_qualified_applicants, name='admin_notify_qualified_applicants'),
    path('admin-portal/applications/<int:pk>/notify/', views.admin_notify_single_applicant, name='admin_notify_single_applicant'),
    path('admin-portal/jobs/<int:pk>/send-candidates/', views.admin_send_candidates_to_employer, name='admin_send_candidates_to_employer'),
    path('admin-portal/jobs/<int:pk>/export-excel/', views.admin_export_candidates_excel, name='admin_export_candidates_excel'),

    # Export access route (Strict authorization for Employer & Admin)
    path('exports/<int:export_id>/view/', views.employer_view_candidate_export, name='employer_view_candidate_export'),
]


