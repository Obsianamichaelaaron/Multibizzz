from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.cache import never_cache
from django.db.models import Q, Count

from accounts.decorators import applicant_required, employer_required, admin_required
from accounts.models import ApplicantProfile, EmployerProfile
from .models import JobPosting, SavedJob, Skill, Qualification, EmployerRequest, CandidateExport
from .forms import JobPostingForm, TalentRequestForm
from ml_engine.matcher import calculate_match_score
from audit.utils import log_audit

def careers_public(request):
    """Public job directory with search & filters (careers.php)."""
    query = request.GET.get('q', '').strip()
    emp_type = request.GET.get('type', '').strip()
    location = request.GET.get('location', '').strip()

    jobs = JobPosting.objects.filter(status='active').select_related('employer')

    if query:
        jobs = jobs.filter(
            Q(title__icontains=query) |
            Q(skills_required__icontains=query) |
            Q(description__icontains=query) |
            Q(employer__company_name__icontains=query)
        )
    if emp_type:
        jobs = jobs.filter(employment_type=emp_type)
    if location:
        jobs = jobs.filter(location__icontains=location)

    return render(request, 'jobs/careers.html', {
        'jobs': jobs,
        'query': query,
        'emp_type': emp_type,
        'location': location,
        'total_count': jobs.count()
    })


def job_detail_public(request, pk):
    """Public single job posting details."""
    job = get_object_or_404(JobPosting.objects.select_related('employer'), pk=pk)
    
    # Check if applicant already applied
    has_applied = False
    is_saved = False
    match_score = None

    if request.user.is_authenticated and request.user.is_applicant:
        profile, _ = ApplicantProfile.objects.get_or_create(user=request.user)
        from applications.models import Application
        has_applied = Application.objects.filter(job=job, applicant=profile).exists()
        is_saved = SavedJob.objects.filter(job=job, applicant=profile).exists()
        match_score = calculate_match_score(profile, job)

    similar_jobs = JobPosting.objects.filter(status='active').exclude(pk=job.pk)[:4]

    return render(request, 'jobs/job_detail_public.html', {
        'job': job,
        'has_applied': has_applied,
        'is_saved': is_saved,
        'match_score': match_score,
        'similar_jobs': similar_jobs
    })


# ==========================================
# APPLICANT PORTAL VIEWS
# ==========================================

@applicant_required
def applicant_jobs(request):
    """Applicant job directory with live ML match scores."""
    profile, _ = ApplicantProfile.objects.get_or_create(user=request.user)
    query = request.GET.get('q', '').strip()
    emp_type = request.GET.get('type', '').strip()
    location = request.GET.get('location', '').strip()
    min_match = request.GET.get('min_match', '').strip()

    jobs_qs = JobPosting.objects.filter(status='active').select_related('employer')

    if query:
        jobs_qs = jobs_qs.filter(
            Q(title__icontains=query) |
            Q(skills_required__icontains=query) |
            Q(description__icontains=query) |
            Q(employer__company_name__icontains=query)
        )
    if emp_type:
        jobs_qs = jobs_qs.filter(employment_type=emp_type)
    if location:
        jobs_qs = jobs_qs.filter(location__icontains=location)

    saved_job_ids = set(SavedJob.objects.filter(applicant=profile).values_list('job_id', flat=True))
    
    from applications.models import Application
    applied_job_ids = set(Application.objects.filter(applicant=profile).values_list('job_id', flat=True))

    min_match_val = None
    if min_match:
        try:
            min_match_val = float(min_match)
        except (ValueError, TypeError):
            min_match_val = None

    scored_jobs = []
    for j in jobs_qs:
        score = calculate_match_score(profile, j)
        if min_match_val is not None and score < min_match_val:
            continue
        scored_jobs.append({
            'job': j,
            'match_score': score,
            'is_saved': j.id in saved_job_ids,
            'has_applied': j.id in applied_job_ids
        })

    # Sort by match score descending
    scored_jobs.sort(key=lambda x: x['match_score'], reverse=True)

    return render(request, 'applicant/jobs.html', {
        'scored_jobs': scored_jobs,
        'query': query,
        'emp_type': emp_type,
        'location': location,
        'min_match': min_match,
        'profile': profile
    })


@applicant_required
def applicant_saved_jobs(request):
    """Saved bookmarks list for applicant."""
    profile, _ = ApplicantProfile.objects.get_or_create(user=request.user)
    saved_items = SavedJob.objects.filter(applicant=profile).select_related('job', 'job__employer')

    return render(request, 'applicant/saved_jobs.html', {
        'saved_items': saved_items,
        'profile': profile
    })


@applicant_required
@require_POST
def toggle_save_job_ajax(request, pk):
    """AJAX handler to toggle saved job bookmark."""
    profile, _ = ApplicantProfile.objects.get_or_create(user=request.user)
    job = get_object_or_404(JobPosting, pk=pk)

    saved_obj, created = SavedJob.objects.get_or_create(applicant=profile, job=job)
    if not created:
        saved_obj.delete()
        is_saved = False
        msg = "Job removed from bookmarks."
        log_audit(
            request,
            'unsave_job',
            f"Applicant {request.user.full_name} removed bookmark for '{job.title}'",
            target_type='job',
            target_id=job.id,
            target_name=job.title
        )
    else:
        is_saved = True
        msg = "Job saved to your bookmarks!"
        log_audit(
            request,
            'save_job',
            f"Applicant {request.user.full_name} bookmarked job opening '{job.title}'",
            target_type='job',
            target_id=job.id,
            target_name=job.title
        )

    return JsonResponse({'success': True, 'is_saved': is_saved, 'message': msg})


# ==========================================
# EMPLOYER PORTAL VIEWS (CONTROLLED PIPELINE)
# ==========================================

@employer_required
def employer_jobs(request):
    """Job postings list associated with the current employer."""
    employer_profile, _ = EmployerProfile.objects.get_or_create(user=request.user)
    jobs = JobPosting.objects.filter(employer=employer_profile).annotate(
        applicant_count=Count('applications')
    ).order_by('-posted_at')

    return render(request, 'employer/jobs.html', {
        'jobs': jobs,
        'employer': employer_profile
    })


@employer_required
def employer_post_job(request):
    """
    Direct job creation is restricted for employers.
    Employers must submit a Talent Request to the Admin recruitment team.
    """
    messages.warning(
        request,
        "Direct job posting is disabled for employer accounts. Please submit a 'Talent Request' to have our Admin team review, optimize, and publish your vacancy."
    )
    return redirect('employer_request_talent')


@employer_required
def employer_edit_job(request, pk):
    """Direct job modification is restricted for employers."""
    messages.warning(
        request,
        "Direct job editing is disabled. Contact your Multibiz Administrator or update your Talent Request."
    )
    return redirect('employer_jobs')


@employer_required
def employer_delete_job(request, pk):
    """Direct job deletion is restricted for employers."""
    messages.warning(
        request,
        "Direct job deletion is disabled. Please contact your Multibiz Administrator."
    )
    return redirect('employer_jobs')


@never_cache
@employer_required
def employer_request_talent(request):
    """Employer submits a hiring / talent request to the Admin recruitment team."""
    employer_profile, _ = EmployerProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = TalentRequestForm(request.POST)
        if form.is_valid():
            talent_req = form.save(commit=False)
            talent_req.employer = employer_profile
            talent_req.status = 'submitted'
            talent_req.save()

            log_audit(
                request,
                'submit_talent_request',
                f"Employer {request.user.full_name} ({employer_profile.display_name}) submitted hiring request: '{talent_req.title}'",
                target_type='talent_request',
                target_id=talent_req.id,
                target_name=talent_req.title
            )

            # Notify administrators
            from accounts.models import User
            from messaging.models import Notification
            admin_users = User.objects.filter(role='admin')
            for admin_u in admin_users:
                Notification.objects.create(
                    user=admin_u,
                    title="New Employer Talent Request",
                    message=f"{employer_profile.display_name} requested talent for '{talent_req.title}' ({talent_req.vacancies_count} vacancy).",
                    type='system'
                )

            messages.success(
                request,
                f"Your hiring request for '{talent_req.title}' has been submitted to Admin! Our team will review the requirements and publish the opening."
            )
            return redirect('employer_talent_requests')
    else:
        form = TalentRequestForm(initial={
            'location': employer_profile.company_address or 'Remote / Manila, Philippines',
            'employment_type': 'full-time'
        })

    return render(request, 'employer/request_talent.html', {
        'form': form,
        'employer': employer_profile
    })


@employer_required
def employer_talent_requests(request):
    """Listing of all hiring requests submitted by this employer with stage tracking."""
    employer_profile, _ = EmployerProfile.objects.get_or_create(user=request.user)
    status_filter = request.GET.get('status', '')
    query = request.GET.get('q', '').strip()

    requests_qs = EmployerRequest.objects.filter(employer=employer_profile).select_related('employer')
    if status_filter:
        requests_qs = requests_qs.filter(status=status_filter)
    if query:
        requests_qs = requests_qs.filter(
            Q(title__icontains=query) |
            Q(skills_required__icontains=query) |
            Q(location__icontains=query)
        )

    return render(request, 'employer/talent_requests.html', {
        'talent_requests': requests_qs,
        'selected_status': status_filter,
        'query': query,
        'employer': employer_profile
    })


@employer_required
def employer_talent_request_detail(request, pk):
    """Detail view of a specific hiring request with stage timeline, candidate metrics, and Google Drive evaluation reports."""
    employer_profile, _ = EmployerProfile.objects.get_or_create(user=request.user)
    talent_req = get_object_or_404(EmployerRequest, pk=pk, employer=employer_profile)
    job_posting = talent_req.job_postings.first()

    applications = []
    if job_posting:
        from applications.models import Application
        applications = Application.objects.filter(
            job=job_posting,
            sent_to_employer=True
        ).select_related('applicant__user').order_by('-match_score')

    candidate_exports = CandidateExport.objects.filter(
        Q(talent_request=talent_req) | (Q(job=job_posting) if job_posting else Q(id=0)),
        employer=employer_profile
    ).order_by('-created_at')

    return render(request, 'employer/talent_request_detail.html', {
        'talent_request': talent_req,
        'job_posting': job_posting,
        'applications': applications,
        'candidate_exports': candidate_exports,
        'employer': employer_profile
    })


# ==========================================
# ADMIN PORTAL VIEWS
# ==========================================

@admin_required
def admin_employer_requests(request):
    """Directory of all employer hiring requests for administrator review."""
    status_filter = request.GET.get('status', '')
    query = request.GET.get('q', '').strip()

    requests_qs = EmployerRequest.objects.select_related('employer__user').all()

    status_counts = {
        'all': requests_qs.count(),
        'submitted': requests_qs.filter(status='submitted').count(),
        'under_admin_review': requests_qs.filter(status='under_admin_review').count(),
        'approved': requests_qs.filter(status='approved').count(),
        'job_posted': requests_qs.filter(status='job_posted').count(),
        'candidates_sent': requests_qs.filter(status='candidates_sent').count(),
        'completed': requests_qs.filter(status='completed').count(),
        'rejected': requests_qs.filter(status='rejected').count(),
    }

    if status_filter:
        requests_qs = requests_qs.filter(status=status_filter)
    if query:
        requests_qs = requests_qs.filter(
            Q(title__icontains=query) |
            Q(employer__company_name__icontains=query) |
            Q(skills_required__icontains=query)
        )

    return render(request, 'admin/employer_requests.html', {
        'talent_requests': requests_qs,
        'status_counts': status_counts,
        'selected_status': status_filter,
        'query': query
    })


@admin_required
def admin_employer_request_detail(request, pk):
    """Admin inspects an employer hiring request, approves, rejects, or creates job."""
    talent_req = get_object_or_404(EmployerRequest.objects.select_related('employer__user'), pk=pk)
    linked_job = talent_req.job_postings.first()
    latest_export = CandidateExport.objects.filter(
        Q(talent_request=talent_req) | (Q(job=linked_job) if linked_job else Q(id=0))
    ).order_by('-created_at').first()

    if request.method == 'POST':
        action = request.POST.get('action')
        admin_notes = request.POST.get('admin_notes', '').strip()
        talent_req.admin_notes = admin_notes

        from messaging.notifications import send_employer_request_status_email
        from messaging.models import Notification

        if action == 'approve':
            talent_req.status = 'approved'
            talent_req.save()
            log_audit(request, 'approve_talent_request', f"Admin approved hiring request #{talent_req.id}: '{talent_req.title}' ({talent_req.employer.display_name})", target_type='talent_request', target_id=talent_req.id)
            
            Notification.objects.create(
                user=talent_req.employer.user,
                title="Hiring Request Approved!",
                message=f"Your hiring request for '{talent_req.title}' was approved by Admin. Job posting creation in progress.",
                type='application'
            )
            send_employer_request_status_email(request, talent_req)
            messages.success(request, f"Request #{talent_req.id} approved! You can now create and publish the job.")
            return redirect('admin_create_job_from_request', pk=talent_req.id)

        elif action == 'reject':
            talent_req.status = 'rejected'
            talent_req.save()
            log_audit(request, 'reject_talent_request', f"Admin rejected hiring request #{talent_req.id}: '{talent_req.title}'", target_type='talent_request', target_id=talent_req.id)
            
            Notification.objects.create(
                user=talent_req.employer.user,
                title="Hiring Request Update",
                message=f"Your hiring request for '{talent_req.title}' was rejected by Admin. Remarks: {admin_notes}",
                type='system'
            )
            send_employer_request_status_email(request, talent_req)
            messages.info(request, f"Request #{talent_req.id} has been marked as rejected.")
            return redirect('admin_employer_requests')

        elif action == 'request_changes':
            talent_req.status = 'changes_requested'
            talent_req.save()
            log_audit(request, 'changes_requested_talent_request', f"Admin requested changes for request #{talent_req.id}: '{talent_req.title}'", target_type='talent_request', target_id=talent_req.id)
            
            Notification.objects.create(
                user=talent_req.employer.user,
                title="Changes Requested on Hiring Request",
                message=f"Admin requested updates for '{talent_req.title}': {admin_notes}",
                type='system'
            )
            send_employer_request_status_email(request, talent_req)
            messages.warning(request, f"Changes requested for request #{talent_req.id}.")
            return redirect('admin_employer_requests')

    return render(request, 'admin/employer_request_detail.html', {
        'talent_request': talent_req,
        'linked_job': linked_job,
        'latest_export': latest_export
    })


@admin_required
def admin_create_job_from_request(request, pk):
    """Admin creates and publishes a JobPosting directly from an approved EmployerRequest."""
    talent_req = get_object_or_404(EmployerRequest.objects.select_related('employer'), pk=pk)

    # Experience years parsing helper
    exp_years = 0
    import re
    m = re.search(r'(\d+)', talent_req.experience_required or '')
    if m:
        exp_years = int(m.group(1))

    if request.method == 'POST':
        form = JobPostingForm(request.POST)
        if form.is_valid():
            job = form.save(commit=False)
            job.employer = talent_req.employer
            job.talent_request = talent_req
            job.created_by_admin = True
            job.status = 'active'
            job.save()

            # Update request status to job_posted
            talent_req.status = 'job_posted'
            talent_req.save()

            log_audit(
                request,
                'create_job_from_request',
                f"Admin published job '{job.title}' from Employer Request #{talent_req.id} for {talent_req.employer.display_name}",
                target_type='job',
                target_id=job.id,
                target_name=job.title
            )

            from messaging.models import Notification
            from messaging.notifications import send_employer_request_status_email
            Notification.objects.create(
                user=talent_req.employer.user,
                title="Job Opening Published!",
                message=f"Your job vacancy for '{job.title}' is now live on the Multibiz Careers board.",
                type='application'
            )
            send_employer_request_status_email(request, talent_req)

            messages.success(request, f"Job '{job.title}' has been successfully created and published!")
            return redirect('admin_jobs')
    else:
        initial_data = {
            'employer': talent_req.employer.id,
            'talent_request': talent_req.id,
            'title': talent_req.title,
            'employment_type': talent_req.employment_type,
            'location': talent_req.location,
            'salary_range': talent_req.salary_range,
            'skills_required': talent_req.skills_required,
            'min_experience_years': exp_years,
            'required_education': talent_req.education_level,
            'required_certifications': talent_req.certifications,
            'description': talent_req.description,
            'requirements': talent_req.other_requirements or f"Experience: {talent_req.experience_required}\nEducation: {talent_req.education_level or 'Any'}\nCertifications: {talent_req.certifications or 'None'}",
            'status': 'active'
        }
        form = JobPostingForm(initial=initial_data)

    return render(request, 'admin/create_job_from_request.html', {
        'form': form,
        'talent_request': talent_req
    })


@admin_required
def admin_jobs(request):
    """Administrative job directory oversight."""
    status_filter = request.GET.get('status', '')
    query = request.GET.get('q', '').strip()

    jobs = JobPosting.objects.select_related('employer', 'talent_request').annotate(
        applicant_count=Count('applications')
    ).order_by('-posted_at')

    if status_filter:
        jobs = jobs.filter(status=status_filter)
    if query:
        jobs = jobs.filter(
            Q(title__icontains=query) |
            Q(employer__company_name__icontains=query) |
            Q(skills_required__icontains=query)
        )

    return render(request, 'admin/jobs.html', {
        'jobs': jobs,
        'status_filter': status_filter,
        'query': query
    })


@admin_required
def admin_create_job(request):
    """Admin creates a standalone job vacancy."""
    if request.method == 'POST':
        form = JobPostingForm(request.POST)
        if form.is_valid():
            job = form.save(commit=False)
            job.created_by_admin = True
            job.save()

            log_audit(
                request,
                'admin_create_job',
                f"Admin created job vacancy: '{job.title}'",
                target_type='job',
                target_id=job.id,
                target_name=job.title
            )

            messages.success(request, f"Job '{job.title}' created and published successfully!")
            return redirect('admin_jobs')
    else:
        form = JobPostingForm(initial={'status': 'active', 'location': 'Manila, Philippines / Remote'})

    return render(request, 'admin/create_job.html', {'form': form})


@admin_required
def admin_edit_job(request, pk):
    """Admin edits existing job vacancy."""
    job = get_object_or_404(JobPosting, pk=pk)

    if request.method == 'POST':
        form = JobPostingForm(request.POST, instance=job)
        if form.is_valid():
            form.save()
            log_audit(request, 'admin_update_job', f"Admin updated job vacancy: '{job.title}'", target_type='job', target_id=job.id)
            messages.success(request, f"Job '{job.title}' updated successfully!")
            return redirect('admin_jobs')
    else:
        form = JobPostingForm(instance=job)

    return render(request, 'admin/edit_job.html', {'form': form, 'job': job})


@admin_required
def admin_delete_job(request, pk):
    """Admin delete job posting."""
    job = get_object_or_404(JobPosting, pk=pk)
    title = job.title
    job.delete()
    log_audit(request, 'delete_job', f'Admin deleted job posting: {title}', target_type='job', target_id=pk)
    messages.success(request, f"Job '{title}' deleted by administrator.")
    return redirect('admin_jobs')
