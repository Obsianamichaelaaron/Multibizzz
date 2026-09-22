from django.urls import path
from . import views

urlpatterns = [
    path('career-guide/', views.chatbot_view, name='chatbot_view'),
    path('career-copilot/', views.chatbot_view, name='applicant_chatbot'),
    path('api/submit-assessment/', views.submit_assessment_ajax, name='chatbot_submit_assessment'),
    path('review/', views.chatbot_review, name='chatbot_review'),
]
