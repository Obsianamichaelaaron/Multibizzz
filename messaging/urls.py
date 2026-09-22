from django.urls import path
from . import views

urlpatterns = [
    path('chat/', views.chat_center, name='chat_center'),
    path('chat/<int:recipient_id>/', views.chat_center, name='chat_thread'),
    path('api/send/', views.send_message_ajax, name='send_message_ajax'),
    path('api/fetch/<int:recipient_id>/', views.fetch_messages_ajax, name='fetch_messages_ajax'),
    path('api/notifications/read/', views.mark_notifications_read_ajax, name='mark_notifications_read_ajax'),
]
