from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages

def role_required(*allowed_roles):
    """Decorator ensuring that logged-in users possess one of the allowed roles."""
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                messages.warning(request, "Please log in to access this page.")
                return redirect('login')
            
            if request.user.status != 'active':
                messages.error(request, f"Your account status is: {request.user.status}. Access denied.")
                return redirect('logout')

            if request.user.is_superuser or request.user.role in allowed_roles:
                return view_func(request, *args, **kwargs)
            
            messages.error(request, "You do not have permission to access that section.")
            return redirect('dashboard_router')
        return _wrapped_view
    return decorator

def applicant_required(view_func):
    return role_required('applicant')(view_func)

def employer_required(view_func):
    return role_required('employer')(view_func)

def admin_required(view_func):
    return role_required('admin')(view_func)
