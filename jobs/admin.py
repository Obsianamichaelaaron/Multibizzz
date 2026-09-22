from django.contrib import admin
from .models import Skill, Qualification, JobPosting, SavedJob, JobRecommendation

@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ('skill_name', 'category', 'status', 'created_at')
    list_filter = ('status', 'category')
    search_fields = ('skill_name', 'category')

@admin.register(Qualification)
class QualificationAdmin(admin.ModelAdmin):
    list_display = ('name', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('name',)

@admin.register(JobPosting)
class JobPostingAdmin(admin.ModelAdmin):
    list_display = ('title', 'employer', 'employment_type', 'location', 'status', 'posted_at')
    list_filter = ('status', 'employment_type', 'posted_at')
    search_fields = ('title', 'description', 'employer__company_name', 'skills_required')

@admin.register(SavedJob)
class SavedJobAdmin(admin.ModelAdmin):
    list_display = ('applicant', 'job', 'saved_at')

@admin.register(JobRecommendation)
class JobRecommendationAdmin(admin.ModelAdmin):
    list_display = ('applicant', 'job', 'recommendation_score', 'created_at')
