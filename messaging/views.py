from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Q, Max
from django.utils import timezone

from accounts.models import User
from .models import Message, Notification
from .notifications import send_new_message_email

@login_required
def chat_center(request, recipient_id=None):
    """Main direct messaging interface."""
    current_user = request.user

    # Fetch distinct users the current user has chatted with
    sent_to = Message.objects.filter(sender=current_user).values_list('receiver_id', flat=True)
    received_from = Message.objects.filter(receiver=current_user).values_list('sender_id', flat=True)
    contact_ids = set(list(sent_to) + list(received_from))

    contacts = User.objects.filter(id__in=contact_ids).exclude(id=current_user.id)

    # Active conversation recipient
    active_recipient = None
    if recipient_id:
        active_recipient = get_object_or_404(User, pk=recipient_id)
    elif contacts.exists():
        active_recipient = contacts.first()

    messages_list = []
    if active_recipient:
        # Mark messages from this recipient as read
        Message.objects.filter(sender=active_recipient, receiver=current_user, is_read=False).update(is_read=True)
        messages_list = Message.objects.filter(
            (Q(sender=current_user, receiver=active_recipient) | Q(sender=active_recipient, receiver=current_user))
        ).order_by('created_at')

    # Available users to start new chat with
    if current_user.is_applicant:
        available_users = User.objects.filter(role__in=['employer', 'admin'], status='active').exclude(id=current_user.id)[:20]
    elif current_user.is_employer:
        available_users = User.objects.filter(role__in=['applicant', 'admin'], status='active').exclude(id=current_user.id)[:20]
    else:
        available_users = User.objects.filter(status='active').exclude(id=current_user.id)[:20]

    return render(request, 'messaging/chat.html', {
        'contacts': contacts,
        'active_recipient': active_recipient,
        'messages_list': messages_list,
        'available_users': available_users,
    })


@login_required
@require_POST
def send_message_ajax(request):
    """AJAX handler to send a message."""
    recipient_id = request.POST.get('recipient_id')
    text = request.POST.get('message', '').strip()

    if not recipient_id or not text:
        return JsonResponse({'success': False, 'error': 'Recipient and message content required.'})

    recipient = get_object_or_404(User, pk=recipient_id)
    msg = Message.objects.create(
        sender=request.user,
        receiver=recipient,
        message=text
    )
    send_new_message_email(request, msg)

    return JsonResponse({
        'success': True,
        'message_id': msg.id,
        'sender_name': request.user.full_name,
        'text': msg.message,
        'timestamp': msg.created_at.strftime('%I:%M %p')
    })


@login_required
def fetch_messages_ajax(request, recipient_id):
    """AJAX polling endpoint to get messages in active conversation."""
    recipient = get_object_or_404(User, pk=recipient_id)
    after_id = int(request.GET.get('after_id', 0))

    new_messages = Message.objects.filter(
        (Q(sender=request.user, receiver=recipient) | Q(sender=recipient, receiver=request.user)),
        id__gt=after_id
    ).order_by('created_at')

    # Mark received as read
    Message.objects.filter(sender=recipient, receiver=request.user, is_read=False).update(is_read=True)

    data = []
    for m in new_messages:
        data.append({
            'id': m.id,
            'sender_id': m.sender_id,
            'is_me': (m.sender_id == request.user.id),
            'sender_name': m.sender.full_name,
            'text': m.message,
            'timestamp': m.created_at.strftime('%I:%M %p')
        })

    return JsonResponse({'success': True, 'messages': data})


@login_required
@require_POST
def mark_notifications_read_ajax(request):
    """Mark all user notifications as read."""
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return JsonResponse({'success': True})
