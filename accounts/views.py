import os
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .forms import LoginForm, ApplicantRegistrationForm, EmployerRegistrationForm, ApplicantProfileForm, EmployerProfileForm
from .models import User, ApplicantProfile, EmployerProfile
from ml_engine.parser import parse_resume_document, validate_and_audit_resume
from ml_engine.matcher import calculate_employability_score
from audit.utils import log_audit

def get_user_destination(user):
    """Returns the destination route name for the user based on their role."""
    if getattr(user, 'is_admin_user', False):
        return 'admin_dashboard'
    elif getattr(user, 'is_employer', False):
        return 'employer_dashboard'
    else:
        return 'careers'


def login_view(request):
    """Unified user login view."""
    if request.user.is_authenticated:
        return redirect(get_user_destination(request.user))

    next_url = request.GET.get('next') or request.POST.get('next')
    job_id = request.GET.get('job_id') or request.POST.get('job_id')

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            user = form.cleaned_data['user']
            login(request, user)
            
            # Log audit trail event
            log_audit(
                request,
                f"{user.role}_login",
                f"{user.role.title()} {user.full_name} logged in ({user.email})",
                target_type='user',
                target_id=user.id,
                target_name=user.full_name,
                user=user
            )

            messages.success(request, f"Welcome back, {user.full_name}!")

            # Custom redirect handlers
            if job_id and user.is_applicant:
                return redirect('apply_job', pk=job_id)
            if next_url:
                return redirect(next_url)
            return redirect(get_user_destination(user))
    else:
        form = LoginForm()

    return render(request, 'accounts/login.html', {
        'form': form,
        'next': next_url,
        'job_id': job_id
    })


def register_view(request):
    """Unified registration view supporting both Applicant and Employer tabs."""
    if request.user.is_authenticated:
        return redirect(get_user_destination(request.user))

    tab = request.GET.get('tab')
    applicant_form = ApplicantRegistrationForm()
    employer_form = EmployerRegistrationForm()

    if request.method == 'POST':
        form_type = request.POST.get('form_type', 'applicant')
        if form_type == 'applicant':
            applicant_form = ApplicantRegistrationForm(request.POST, request.FILES)
            tab = 'applicant'
            if applicant_form.is_valid():
                resume_file = applicant_form.cleaned_data.get('resume_file')
                if resume_file:
                    extracted = parse_resume_document(file_obj=resume_file)
                    validation = extracted.get('validation', {})
                    if not validation.get('is_valid_resume', False):
                        applicant_form.add_error(
                            'resume_file',
                            validation.get(
                                'rejection_reason',
                                'The uploaded file does not appear to be a valid Resume or CV.'
                            )
                        )
                if not applicant_form.errors:
                    user = applicant_form.save()
                    login(request, user)
                    
                    # Log audit trail event
                    log_audit(
                        request,
                        'register_applicant',
                        f"New candidate registered: {user.full_name} ({user.email})",
                        target_type='applicant',
                        target_id=user.id,
                        target_name=user.full_name,
                        user=user
                    )

                    # Dispatch Welcome Email and SMS Notification
                    from messaging.notifications import send_all_welcome_notifications
                    send_all_welcome_notifications(request, user)

                    messages.success(
                        request, 
                        f"Welcome to Multibiz, {user.first_name}! Your candidate account has been created. "
                        f"A welcome email and SMS notification have been dispatched to your contact details."
                    )
                    return redirect('applicant_profile')
        elif form_type == 'employer':
            employer_form = EmployerRegistrationForm(request.POST)
            tab = 'employer'
            if employer_form.is_valid():
                user = employer_form.save()
                login(request, user)

                # Log audit trail event
                company_title = getattr(user, 'employer_profile', None)
                company_name = company_title.display_name if company_title else user.full_name
                log_audit(
                    request,
                    'register_employer',
                    f"New employer registered: {user.full_name} ({user.email}) - {company_name}",
                    target_type='employer',
                    target_id=user.id,
                    target_name=company_name,
                    user=user
                )

                # Dispatch Welcome Email and SMS Notification
                from messaging.notifications import send_all_welcome_notifications
                send_all_welcome_notifications(request, user)

                messages.success(
                    request, 
                    f"Welcome to Multibiz Talent Solutions! Your employer account for '{company_name}' is active. "
                    f"A welcome email and SMS confirmation have been sent."
                )
                return redirect('employer_profile')

    return render(request, 'accounts/register.html', {
        'applicant_form': applicant_form,
        'employer_form': employer_form,
        'active_tab': tab
    })


def logout_view(request):
    """Logs out user and redirects to home."""
    if request.user.is_authenticated:
        log_audit(
            request,
            f"{request.user.role}_logout",
            f"{request.user.role.title()} {request.user.full_name} signed out",
            target_type='user',
            target_id=request.user.id,
            target_name=request.user.full_name
        )
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('home')


@login_required
def dashboard_router(request):
    """Routes user to their respective destination depending on their assigned role."""
    return redirect(get_user_destination(request.user))


@login_required
def profile_view(request):
    """User profile management for Applicant and Employer."""
    user = request.user

    if user.is_applicant:
        profile, _ = ApplicantProfile.objects.get_or_create(user=user)
        resume_audit = None

        if request.method == 'POST':
            form = ApplicantProfileForm(request.POST, request.FILES, instance=profile)
            if form.is_valid():
                user.first_name = form.cleaned_data['first_name']
                user.last_name = form.cleaned_data['last_name']
                user.phone = form.cleaned_data['phone']
                user.save()
                saved_profile = form.save(commit=False)

                upload_cancelled = False

                # If resume was newly uploaded, validate content before accepting
                if 'resume_file' in request.FILES:
                    uploaded_file = request.FILES['resume_file']
                    extracted = parse_resume_document(file_obj=uploaded_file)
                    validation = extracted.get('validation', {})

                    if not validation.get('is_valid_resume', False):
                        # CANCEL UPLOAD: Document is not a resume
                        upload_cancelled = True
                        saved_profile.resume_file = profile.resume_file  # retain previous file
                        rejection_reason = validation.get('rejection_reason', 'The uploaded file does not appear to be a valid Resume or CV.')
                        messages.error(
                            request,
                            f"Resume Upload Cancelled by AI Validator: {rejection_reason}"
                        )
                    else:
                        # VALID RESUME: Save and extract
                        saved_profile.resume_file = uploaded_file
                        resume_audit = validation
                        if extracted.get('skills'):
                            existing_skills = [s.strip() for s in (saved_profile.skills or '').split(',') if s.strip()]
                            for s in extracted['skills']:
                                if s not in existing_skills:
                                    existing_skills.append(s)
                            saved_profile.skills = ', '.join(existing_skills)
                        if not saved_profile.education_level and extracted.get('education'):
                            saved_profile.education_level = extracted['education']
                        if (saved_profile.experience_years == 0 or not saved_profile.experience_years) and extracted.get('experience_years'):
                            saved_profile.experience_years = extracted['experience_years']
                        saved_profile.employability_score = calculate_employability_score(saved_profile)

                        level = validation.get('strength_level', 'Moderate')
                        score = validation.get('strength_score', 60)
                        if level == 'Weak':
                            messages.warning(
                                request,
                                f"Resume uploaded! AI Audit: Resume Strength is Weak ({score}%). Review the AI Suggestions below to make your profile competitive."
                            )
                        elif level == 'Moderate':
                            messages.info(
                                request,
                                f"Resume uploaded! AI Audit: Resume Strength is Moderate ({score}%). Check the AI suggestions to reach top tier."
                            )
                        else:
                            messages.success(
                                request,
                                f"Resume uploaded successfully! AI Audit: Strong, highly competitive resume ({score}%)."
                            )

                # Recalculate employability score
                saved_profile.employability_score = calculate_employability_score(saved_profile)
                saved_profile.calculate_completion()
                saved_profile.save()

                if not upload_cancelled:
                    log_audit(
                        request,
                        'update_applicant_profile',
                        f"Applicant {user.full_name} updated profile details & competencies",
                        target_type='applicant',
                        target_id=user.id,
                        target_name=user.full_name
                    )
                    messages.success(request, "Your profile details have been saved successfully!")
                return redirect('applicant_profile')
        else:
            form = ApplicantProfileForm(instance=profile, initial={
                'first_name': user.first_name,
                'last_name': user.last_name,
                'phone': user.phone
            })

        # Pre-calculate audit for existing resume if available
        if profile.resume_file and not resume_audit:
            text_to_audit = getattr(profile, 'parsed_resume_text', '') or ''
            if not text_to_audit and hasattr(profile.resume_file, 'path') and os.path.exists(profile.resume_file.path):
                from ml_engine.parser import extract_text_from_pdf, extract_text_from_docx
                ext = os.path.splitext(profile.resume_file.name)[1].lower()
                if ext == '.pdf':
                    text_to_audit = extract_text_from_pdf(profile.resume_file.path)
                elif ext in ['.docx', '.doc']:
                    text_to_audit = extract_text_from_docx(profile.resume_file.path)
            if text_to_audit:
                resume_audit = validate_and_audit_resume(text_to_audit)

        completion_pct = profile.calculate_completion()
        return render(request, 'applicant/profile.html', {
            'form': form,
            'profile': profile,
            'completion_pct': completion_pct,
            'skills_list': profile.get_skills_list(),
            'resume_audit': resume_audit
        })

    elif user.is_employer:
        profile, _ = EmployerProfile.objects.get_or_create(user=user)
        if request.method == 'POST':
            form = EmployerProfileForm(request.POST, request.FILES, instance=profile)
            if form.is_valid():
                user.first_name = form.cleaned_data['first_name']
                user.last_name = form.cleaned_data['last_name']
                user.phone = form.cleaned_data['phone']
                user.save()
                saved_employer = form.save()
                log_audit(
                    request,
                    'update_employer_profile',
                    f"Employer {user.full_name} updated company profile ({saved_employer.display_name})",
                    target_type='employer',
                    target_id=user.id,
                    target_name=saved_employer.display_name
                )
                messages.success(request, "Company profile updated successfully!")
                return redirect('employer_profile')
        else:
            form = EmployerProfileForm(instance=profile, initial={
                'first_name': user.first_name,
                'last_name': user.last_name,
                'phone': user.phone
            })
        return render(request, 'employer/profile.html', {'form': form, 'profile': profile})

    else:
        messages.info(request, "Administrator settings.")
        return redirect('admin_dashboard')


@login_required
@require_POST
def parse_resume_ajax(request):
    """AJAX handler to parse, validate, and audit uploaded resume document in real time."""
    if 'resume_file' not in request.FILES:
        return JsonResponse({'success': False, 'error': 'No resume file uploaded.'})

    file_obj = request.FILES['resume_file']
    parsed = parse_resume_document(file_obj=file_obj)
    validation = parsed.get('validation', {})

    return JsonResponse({
        'success': True,
        'is_valid_resume': validation.get('is_valid_resume', False),
        'rejection_reason': validation.get('rejection_reason'),
        'strength_score': validation.get('strength_score', 0),
        'strength_level': validation.get('strength_level', 'Invalid'),
        'suggestions': validation.get('suggestions', []),
        'skills': parsed.get('skills', []),
        'education': parsed.get('education', ''),
        'experience_years': parsed.get('experience_years', 0),
        'data': parsed
    })
