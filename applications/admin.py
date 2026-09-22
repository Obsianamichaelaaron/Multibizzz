from django.contrib import admin
from .models import Application, CandidateFeedback, InterviewSchedule

@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ('applicant', 'job', 'status', 'match_score', 'applied_at')
    list_filter = ('status', 'applied_at')
    search_fields = ('applicant__user__email', 'job__title')

@admin.register(CandidateFeedback)
class CandidateFeedbackAdmin(admin.ModelAdmin):
    list_display = ('applicant', 'employer', 'employability_score', 'feedback_type', 'created_at')

@admin.register(InterviewSchedule)
class InterviewScheduleAdmin(admin.ModelAdmin):
    list_display = ('application', 'employer', 'interview_date', 'start_time', 'interview_type', 'status')
    list_filter = ('status', 'interview_type', 'interview_date')
