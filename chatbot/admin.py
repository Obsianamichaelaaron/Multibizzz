from django.contrib import admin
from .models import ChatbotAnswer, ChatbotRecommendation

@admin.register(ChatbotAnswer)
class ChatbotAnswerAdmin(admin.ModelAdmin):
    list_display = ('applicant', 'question_number', 'score_value', 'category', 'created_at')
    list_filter = ('category', 'created_at')
    search_fields = ('applicant__user__email', 'question_text', 'answer_text')

@admin.register(ChatbotRecommendation)
class ChatbotRecommendationAdmin(admin.ModelAdmin):
    list_display = ('applicant', 'job', 'recommendation_type', 'match_score', 'created_at')
