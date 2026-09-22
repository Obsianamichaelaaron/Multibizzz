from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Avg, Q
from django.utils import timezone
from datetime import timedelta

from accounts.decorators import admin_required
from accounts.models import User, ApplicantProfile, EmployerProfile
from .models import AuditTrail
from .utils import log_audit

import json

@admin_required
def admin_dashboard(request):
    """Main administrative dashboard view with key metrics, visual analytics graphs, and recent activity."""
    from jobs.models import JobPosting
    from applications.models import Application
    from core.models import ContactInquiry

    # Core Counts
    total_users = User.objects.count()
    total_applicants = User.objects.filter(role='applicant').count()
    total_employers = User.objects.filter(role='employer').count()
    total_admins = User.objects.filter(role='admin').count()

    total_jobs = JobPosting.objects.count()
    active_jobs = JobPosting.objects.filter(status='active').count()
    draft_jobs = JobPosting.objects.filter(status='draft').count()
    closed_jobs = JobPosting.objects.filter(status='closed').count()

    total_applications = Application.objects.count()
    pending_inquiries = ContactInquiry.objects.filter(is_read=False).count()

    # Match score & 30-day growth
    avg_match_score = Application.objects.aggregate(avg=Avg('match_score'))['avg'] or 0
    thirty_days_ago = timezone.now() - timedelta(days=30)
    new_users_30d = User.objects.filter(created_at__gte=thirty_days_ago).count()
    new_apps_30d = Application.objects.filter(applied_at__gte=thirty_days_ago).count()

    # 1. Pipeline Status Breakdown for Graph
    status_order = ['pending', 'reviewed', 'shortlisted', 'interviewed', 'accepted', 'rejected']
    status_display_map = {
        'pending': 'Pending Review',
        'reviewed': 'Reviewed',
        'shortlisted': 'Shortlisted',
        'interviewed': 'Interview Scheduled',
        'accepted': 'Accepted / Hired',
        'rejected': 'Rejected'
    }
    status_counts_raw = {item['status']: item['count'] for item in Application.objects.values('status').annotate(count=Count('status'))}
    pipeline_labels = [status_display_map.get(s, s.title()) for s in status_order]
    pipeline_data = [status_counts_raw.get(s, 0) for s in status_order]

    # 2. Employment Type Breakdown for Graph
    type_order = ['full-time', 'part-time', 'contract', 'internship']
    type_display_map = {
        'full-time': 'Full-Time',
        'part-time': 'Part-Time',
        'contract': 'Contract',
        'internship': 'Internship'
    }
    type_counts_raw = {item['employment_type']: item['count'] for item in JobPosting.objects.values('employment_type').annotate(count=Count('employment_type'))}
    for k in type_counts_raw:
        if k not in type_order:
            type_order.append(k)
            type_display_map[k] = k.title()
    job_type_labels = [type_display_map.get(t, t.title()) for t in type_order]
    job_type_data = [type_counts_raw.get(t, 0) for t in type_order]

    # 3. AI Match Score Tier Distribution for Graph
    elite_matches = Application.objects.filter(match_score__gte=85).count()
    strong_matches = Application.objects.filter(match_score__gte=70, match_score__lt=85).count()
    moderate_matches = Application.objects.filter(match_score__gte=50, match_score__lt=70).count()
    low_matches = Application.objects.filter(match_score__lt=50).count()
    
    match_tier_labels = ['Elite Match (85-100%)', 'Strong Fit (70-84%)', 'Moderate (50-69%)', 'Developing (<50%)']
    match_tier_data = [elite_matches, strong_matches, moderate_matches, low_matches]

    # 4. User Role Distribution for Graph
    user_role_labels = ['Applicants', 'Employers', 'Administrators']
    user_role_data = [total_applicants, total_employers, total_admins]

    # 5. Monthly Growth Trends (Past 6 Months)
    now = timezone.now()
    trend_labels = []
    trend_users = []
    trend_apps = []

    for i in range(5, -1, -1):
        month_offset = now - timedelta(days=i * 30.5)
        m_start = month_offset.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if m_start.month == 12:
            m_end = m_start.replace(year=m_start.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            m_end = m_start.replace(month=m_start.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)
        
        m_label = m_start.strftime('%b %Y')
        trend_labels.append(m_label)
        
        u_count = User.objects.filter(created_at__gte=m_start, created_at__lt=m_end).count()
        a_count = Application.objects.filter(applied_at__gte=m_start, applied_at__lt=m_end).count()
        trend_users.append(u_count)
        trend_apps.append(a_count)

    # Activity streams
    recent_users = User.objects.order_by('-created_at')[:8]
    recent_audits = AuditTrail.objects.order_by('-created_at')[:8]
    recent_applications = Application.objects.select_related('job', 'applicant__user').order_by('-applied_at')[:6]

    context = {
        'total_users': total_users,
        'total_applicants': total_applicants,
        'total_employers': total_employers,
        'total_admins': total_admins,
        'total_jobs': total_jobs,
        'active_jobs': active_jobs,
        'draft_jobs': draft_jobs,
        'closed_jobs': closed_jobs,
        'total_applications': total_applications,
        'pending_inquiries': pending_inquiries,
        'avg_match_score': round(avg_match_score, 1),
        'new_users_30d': new_users_30d,
        'new_apps_30d': new_apps_30d,
        'elite_matches': elite_matches,
        'strong_matches': strong_matches,
        'recent_users': recent_users,
        'recent_audits': recent_audits,
        'recent_applications': recent_applications,
        
        # Graph Data (JSON formatted for Chart.js)
        'chart_data_json': json.dumps({
            'trend_labels': trend_labels,
            'trend_users': trend_users,
            'trend_apps': trend_apps,
            'user_role_labels': user_role_labels,
            'user_role_data': user_role_data,
            'pipeline_labels': pipeline_labels,
            'pipeline_data': pipeline_data,
            'job_type_labels': job_type_labels,
            'job_type_data': job_type_data,
            'match_tier_labels': match_tier_labels,
            'match_tier_data': match_tier_data,
        })
    }
    return render(request, 'admin/dashboard.html', context)


from django.core.paginator import Paginator

@admin_required
def admin_audit_trail(request):
    """Audit Trail management and inspection page with advanced filtering and pagination."""
    search_query = request.GET.get('q', '').strip()
    action_type = request.GET.get('action_type', '').strip()
    target_type = request.GET.get('target_type', '').strip()
    date_range = request.GET.get('date_range', '').strip()
    page_number = request.GET.get('page', 1)

    logs = AuditTrail.objects.all().order_by('-created_at')

    # Seed initial platform baseline log if table is completely empty
    if AuditTrail.objects.count() == 0:
        admin_u = User.objects.filter(role='admin').first()
        log_audit(
            request,
            'system_init',
            'Initialized Multibiz Platform Security Audit & Operations Ledger',
            target_type='system',
            target_name='Multibiz Core'
        )
        logs = AuditTrail.objects.all().order_by('-created_at')

    # Metrics
    total_logs_count = AuditTrail.objects.count()
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_logs_count = AuditTrail.objects.filter(created_at__gte=today_start).count()
    distinct_admins_count = AuditTrail.objects.values('admin_name').distinct().count()
    security_actions_count = AuditTrail.objects.filter(
        Q(action_type__startswith='delete_') | Q(action_type__icontains='status') | Q(action_type__icontains='auth')
    ).count()

    # Search query
    if search_query:
        logs = logs.filter(
            Q(admin_name__icontains=search_query) |
            Q(action_description__icontains=search_query) |
            Q(target_name__icontains=search_query) |
            Q(ip_address__icontains=search_query) |
            Q(action_type__icontains=search_query)
        )

    # Action type filter
    if action_type:
        logs = logs.filter(action_type=action_type)

    # Target type filter
    if target_type:
        logs = logs.filter(target_type=target_type)

    # Date range filter
    if date_range == 'today':
        logs = logs.filter(created_at__gte=today_start)
    elif date_range == '7d':
        seven_days_ago = now - timedelta(days=7)
        logs = logs.filter(created_at__gte=seven_days_ago)
    elif date_range == '30d':
        thirty_days_ago = now - timedelta(days=30)
        logs = logs.filter(created_at__gte=thirty_days_ago)

    # Dropdown choices
    distinct_actions_raw = AuditTrail.objects.values_list('action_type', flat=True).distinct().order_by('action_type')
    distinct_actions = [{'val': a, 'label': a.replace('_', ' ').title()} for a in distinct_actions_raw if a]

    distinct_targets_raw = AuditTrail.objects.exclude(target_type__isnull=True).exclude(target_type='').values_list('target_type', flat=True).distinct().order_by('target_type')
    distinct_targets = [{'val': t, 'label': t.replace('_', ' ').title()} for t in distinct_targets_raw if t]

    # Pagination: 25 items per page
    paginator = Paginator(logs, 25)
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'logs': page_obj.object_list,
        'search_query': search_query,
        'action_type': action_type,
        'target_type': target_type,
        'date_range': date_range,
        'distinct_actions': distinct_actions,
        'distinct_targets': distinct_targets,
        'total_logs_count': total_logs_count,
        'today_logs_count': today_logs_count,
        'distinct_admins_count': distinct_admins_count,
        'security_actions_count': security_actions_count,
    }
    return render(request, 'admin/audit_trail.html', context)


@admin_required
def admin_analytics(request):
    """Redirects to admin dashboard where full visual graph analytics is embedded."""
    return redirect('admin_dashboard')


@admin_required
def admin_users(request):
    """User accounts manager for administrators."""
    role_filter = request.GET.get('role', '')
    status_filter = request.GET.get('status', '')
    query = request.GET.get('q', '').strip()

    users = User.objects.all().order_by('-created_at')

    if role_filter:
        users = users.filter(role=role_filter)
    if status_filter:
        users = users.filter(status=status_filter)
    if query:
        users = users.filter(
            Q(email__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query)
        )

    if request.method == 'POST' and 'create_user' in request.POST:
        email = request.POST.get('email', '').strip()
        pwd = request.POST.get('password', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        role = request.POST.get('role', 'applicant')
        phone = request.POST.get('phone', '').strip()

        if User.objects.filter(email=email).exists():
            messages.error(request, f"User with email {email} already exists.")
        else:
            new_u = User.objects.create_user(
                email=email,
                password=pwd,
                first_name=first_name,
                last_name=last_name,
                role=role,
                phone=phone,
                status='active',
                created_by_admin=True
            )
            if role == 'applicant':
                ApplicantProfile.objects.create(user=new_u)
            elif role == 'employer':
                company_name = request.POST.get('company_name', '').strip() or f"{first_name}'s Company"
                EmployerProfile.objects.create(user=new_u, company_name=company_name)

            log_audit(request, f"create_{role}", f"Created new {role} account: {new_u.full_name} ({email})", target_type=role, target_id=new_u.id, target_name=new_u.full_name)
            
            # Dispatch Welcome Email and SMS Notification to the new user
            from messaging.notifications import send_all_welcome_notifications
            send_all_welcome_notifications(request, new_u)

            messages.success(request, f"User {email} created successfully and welcome notifications dispatched!")
            return redirect('admin_users')

    return render(request, 'admin/users.html', {
        'users': users,
        'role_filter': role_filter,
        'status_filter': status_filter,
        'query': query,
    })


@admin_required
def admin_toggle_user_status(request, user_id):
    """Activates, deactivates, or suspends a user account."""
    target_user = get_object_or_404(User, pk=user_id)
    new_status = request.POST.get('status', 'active')
    
    if target_user.pk == request.user.pk:
        messages.error(request, "You cannot modify your own administrator account status.")
        return redirect('admin_users')

    old_status = target_user.status
    target_user.status = new_status
    target_user.save()

    log_audit(
        request,
        "update_user_status",
        f"Changed status for {target_user.email} from {old_status} to {new_status}",
        target_type='user',
        target_id=target_user.pk,
        target_name=target_user.full_name
    )
    messages.success(request, f"Status for {target_user.email} updated to {new_status}.")
    return redirect('admin_users')


@admin_required
def admin_delete_user(request, user_id):
    """Deletes a user account."""
    target_user = get_object_or_404(User, pk=user_id)
    if target_user.pk == request.user.pk:
        messages.error(request, "You cannot delete your own administrator account.")
        return redirect('admin_users')

    user_email = target_user.email
    user_name = target_user.full_name
    target_user.delete()

    log_audit(
        request,
        "delete_user",
        f"Deleted account for {user_name} ({user_email})",
        target_type='user',
        target_id=user_id,
        target_name=user_name
    )
    messages.success(request, f"User {user_email} has been permanently deleted.")
    return redirect('admin_users')
