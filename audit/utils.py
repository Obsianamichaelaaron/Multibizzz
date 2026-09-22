from .models import AuditTrail

def get_client_ip(request):
    """Safely retrieves client IP address from request."""
    if not request:
        return '127.0.0.1'
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
    return ip

def log_audit(request, action_type, description, target_type=None, target_id=None, target_name=None, user=None):
    """Utility to record an administrative action or system transaction in the AuditTrail table."""
    try:
        actor_user = user if (user is not None and getattr(user, 'pk', None)) else (request.user if (request and request.user.is_authenticated and getattr(request.user, 'pk', None)) else None)
        actor_name = user.full_name if user else (request.user.full_name if (request and request.user.is_authenticated) else "System / Guest")
        ip = get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '') if request else ''

        return AuditTrail.objects.create(
            admin_user=actor_user,
            admin_name=actor_name,
            action_type=action_type,
            action_description=description,
            target_type=target_type,
            target_id=target_id,
            target_name=target_name,
            ip_address=ip,
            user_agent=user_agent
        )
    except Exception as e:
        # Non-blocking safeguard
        return None
