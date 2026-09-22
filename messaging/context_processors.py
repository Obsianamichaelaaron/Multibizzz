from .models import Message, Notification

def unread_messages_count(request):
    """Context processor providing unread messages and notifications count."""
    if request.user.is_authenticated:
        unread_msg = Message.objects.filter(receiver=request.user, is_read=False).count()
        unread_notif = Notification.objects.filter(user=request.user, is_read=False).count()
        recent_notifs = Notification.objects.filter(user=request.user).order_by('-created_at')[:5]
        return {
            'unread_messages_count': unread_msg,
            'unread_notifications_count': unread_notif,
            'recent_notifications': recent_notifs
        }
    return {
        'unread_messages_count': 0,
        'unread_notifications_count': 0,
        'recent_notifications': []
    }
