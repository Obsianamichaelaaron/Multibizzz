import os
import re
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden, FileResponse
from django.core.files.base import ContentFile
from django.views.decorators.http import require_POST
from django.db.models import Q
from django.utils import timezone

from accounts.decorators import applicant_required, employer_required, admin_required
from accounts.models import ApplicantProfile, EmployerProfile, User
from jobs.models import JobPosting, EmployerRequest, CandidateExport
from jobs.services.excel_exporter import generate_candidates_excel
from jobs.services.google_drive import upload_candidates_excel_to_drive
from .models import Application, CandidateFeedback, InterviewSchedule

from ml_engine.matcher import (
    calculate_match_score,
    rank_candidate_application,
    evaluate_applicant_qualification,
    find_alternative_job_recommendations
)
from messaging.models import Notification
from messaging.notifications import (
    send_application_under_review_email,
    send_application_not_qualified_email,
    send_candidates_sent_to_employer_email
)
from audit.utils import log_audit

# ==========================================
# APPLICANT VIEWS
# ==========================================

@applicant_required
def applicant_dashboard(request):
    """Applicant main dashboard view with comprehensive analytics and AI matching."""
    profile, _ = ApplicantProfile.objects.get_or_create(user=request.user)
    
    # Auto-calculate employability score if not set
    if not profile.employability_score or profile.employability_score <= 0:
        from ml_engine.matcher import calculate_employability_score
        profile.employability_score = calculate_employability_score(profile)
        profile.save()

    applications = Application.objects.filter(applicant=profile).select_related('job', 'job__employer').order_by('-applied_at')
    
    total_apps = applications.count()
    pending_count = applications.filter(status__in=['pending', 'applied']).count()
    qualified_count = applications.filter(qualification_status='qualified').count()
    under_review_count = applications.filter(status='under_review').count()
    shortlisted_count = applications.filter(status='shortlisted').count()
    interview_count = applications.filter(status='interviewed').count()
    accepted_count = applications.filter(status__in=['accepted', 'selected']).count()
    rejected_count = applications.filter(status__in=['rejected', 'not_qualified']).count()

    upcoming_interviews = InterviewSchedule.objects.filter(
        application__applicant=profile,
        status='scheduled'
    ).select_related('application__job', 'employer').order_by('interview_date', 'start_time')[:5]

    # Recommended jobs with AI Matching & Skill Intersection
    from jobs.models import JobPosting, SavedJob
    active_jobs = JobPosting.objects.filter(status='active').select_related('employer').order_by('-posted_at')
    saved_job_ids = set(SavedJob.objects.filter(applicant=profile).values_list('job_id', flat=True))
    applied_job_ids = set(applications.values_list('job_id', flat=True))

    candidate_skills = profile.get_skills_list()
    candidate_skills_lower = set(s.lower().strip() for s in candidate_skills)

    recommended = []
    for j in active_jobs:
        if j.id not in applied_job_ids:
            score = calculate_match_score(profile, j)
            job_skills = j.get_skills_list()
            matched_skills = [s for s in job_skills if s.lower().strip() in candidate_skills_lower]
            missing_skills = [s for s in job_skills if s.lower().strip() not in candidate_skills_lower]
            
            recommended.append({
                'job': j,
                'match_score': int(score),
                'matched_skills': matched_skills[:4],
                'missing_skills': missing_skills[:2],
                'is_saved': j.id in saved_job_ids
            })
    
    # Sort descending by match score
    recommended.sort(key=lambda x: x['match_score'], reverse=True)

    completion_pct = profile.calculate_completion()
    employability_score = int(profile.employability_score) if profile.employability_score else 75

    # Employability Breakdown Scores
    skills_score = min(100, max(30, len(candidate_skills) * 15))
    exp_score = min(100, max(40, (profile.experience_years or 1) * 20 + 20))
    edu_score = 90 if profile.education_level else 40
    resume_score = 95 if profile.resume_file else 30

    # Dynamic AI Career Recommendation Tip
    if not profile.resume_file:
        ai_tip = "Upload your resume PDF to unlock automated AI parsing and boost matching accuracy."
        ai_tip_badge = "Upload Resume"
        ai_tip_url = "/accounts/profile/"
    elif len(candidate_skills) < 4:
        ai_tip = "Adding 3+ technical skills (e.g. Docker, PostgreSQL, AWS) will increase your match score by up to 25%."
        ai_tip_badge = "Add Skills"
        ai_tip_url = "/accounts/profile/"
    elif total_apps == 0:
        ai_tip = "You have top matches waiting! Applying to 3+ verified positions increases recruiter response by 70%."
        ai_tip_badge = "Apply Now"
        ai_tip_url = "/jobs/careers/"
    else:
        ai_tip = f"Your profile ranks in the top tier ({employability_score}% AI score). Prepare for technical interviews with our AI Copilot."
        ai_tip_badge = "Practice with AI"
        ai_tip_url = "/chatbot/"

    saved_jobs = SavedJob.objects.filter(applicant=profile).select_related('job', 'job__employer')[:5]

    return render(request, 'applicant/dashboard.html', {
        'profile': profile,
        'candidate_skills': candidate_skills,
        'total_apps': total_apps,
        'pending_count': pending_count,
        'qualified_count': qualified_count,
        'under_review_count': under_review_count,
        'shortlisted_count': shortlisted_count,
        'interview_count': interview_count,
        'accepted_count': accepted_count,
        'rejected_count': rejected_count,
        'upcoming_interviews': upcoming_interviews,
        'recommended_jobs': recommended[:6],
        'saved_jobs': saved_jobs,
        'saved_count': saved_jobs.count(),
        'recent_applications': applications[:6],
        'completion_pct': completion_pct,
        'employability_score': employability_score,
        'skills_score': skills_score,
        'exp_score': exp_score,
        'edu_score': edu_score,
        'resume_score': resume_score,
        'ai_tip': ai_tip,
        'ai_tip_badge': ai_tip_badge,
        'ai_tip_url': ai_tip_url,
    })



@applicant_required
def apply_job(request, pk):
    """Job application submission view with automated qualification evaluation."""
    profile, _ = ApplicantProfile.objects.get_or_create(user=request.user)
    job = get_object_or_404(JobPosting, pk=pk, status='active')

    existing = Application.objects.filter(job=job, applicant=profile).first()
    if existing:
        messages.info(request, "You have already applied for this position.")
        return redirect('my_applications')

    if request.method == 'POST':
        cover_letter = request.POST.get('cover_letter', '').strip()
        use_profile_resume = request.POST.get('use_profile_resume') == 'true'

        resume_file = profile.resume_file
        resume_text = None
        if 'resume_file' in request.FILES:
            uploaded_file = request.FILES['resume_file']
            from ml_engine.parser import parse_resume_document
            from ml_engine.matcher import calculate_employability_score
            extracted = parse_resume_document(file_obj=uploaded_file)
            validation = extracted.get('validation', {})
            if not validation.get('is_valid_resume', False):
                messages.error(
                    request,
                    f"Application Submission Cancelled by AI Validator: {validation.get('rejection_reason', 'The uploaded file does not appear to be a genuine Resume or CV.')}"
                )
                return render(request, 'applicant/apply_job.html', {
                    'job': job,
                    'profile': profile,
                    'match_score': calculate_match_score(profile, job)
                })
            resume_file = uploaded_file
            resume_text = extracted.get('text', '')

            # Automatically synchronize extracted skills, education, experience into profile
            if extracted.get('skills'):
                existing_skills = [s.strip() for s in (profile.skills or '').split(',') if s.strip()]
                for s in extracted['skills']:
                    if s not in existing_skills:
                        existing_skills.append(s)
                profile.skills = ', '.join(existing_skills)
            if not profile.education_level and extracted.get('education'):
                profile.education_level = extracted['education']
            if profile.experience_years == 0 and extracted.get('experience_years'):
                profile.experience_years = extracted['experience_years']
            
            profile.resume_file = uploaded_file
            profile.employability_score = calculate_employability_score(profile)
            profile.save()

        if not resume_file and not profile.resume_file:
            messages.error(request, "Please attach a verified resume to submit your application.")
            return render(request, 'applicant/apply_job.html', {'job': job, 'profile': profile, 'match_score': calculate_match_score(profile, job)})

        # 1. Compare Applicant against Job Requirements via ML Evaluator
        eval_result = evaluate_applicant_qualification(profile, job, resume_text=resume_text)
        is_qualified = eval_result['is_qualified']
        match_score = eval_result['match_score']

        initial_status = 'qualified' if is_qualified else 'not_qualified'

        app = Application.objects.create(
            job=job,
            applicant=profile,
            status=initial_status,
            qualification_status=eval_result['qualification_status'],
            qualification_reason=eval_result['reason'],
            match_score=match_score,
            skills_match_score=eval_result['skills_score'],
            exp_match_score=eval_result['exp_score'],
            edu_match_score=eval_result['edu_score'],
            cover_letter=cover_letter,
            resume_file=resume_file
        )

        log_audit(
            request,
            'apply_job',
            f"Applicant {request.user.full_name} applied for '{job.title}' @ {job.company_name} (Qualification: {eval_result['qualification_status'].upper()}, Score: {match_score}%)",
            target_type='application',
            target_id=app.id,
            target_name=job.title
        )

        # 2. Automated Applicant Notifications based on qualification
        if is_qualified:
            # Send: "Your application is under review."
            email_sent = send_application_under_review_email(request, app)
            app.notification_sent = email_sent
            app.notification_sent_at = timezone.now() if email_sent else None
            app.status = 'under_review'
            app.save()

            Notification.objects.create(
                user=request.user,
                title=f"Application under review: {job.title}",
                message=(
                    "Your application meets the qualification criteria and is now under review."
                    if email_sent else
                    "Your application meets the qualification criteria and is now under review. "
                    "The email notification could not be delivered."
                ),
                type='application'
            )

            messages.success(
                request,
                f"Your application for '{job.title}' was submitted! Your profile meets the qualifications and is currently under review."
                + (" We could not deliver the email notification." if not email_sent else "")
            )
        else:
            # Find alternative matching job recommendations
            recommended_jobs = find_alternative_job_recommendations(profile, exclude_job_id=job.id, limit=3)
            # Send: "You are not qualified for this position." + alternative job recommendations
            email_sent = send_application_not_qualified_email(request, app, recommended_jobs)
            app.notification_sent = email_sent
            app.notification_sent_at = timezone.now() if email_sent else None
            app.save()

            Notification.objects.create(
                user=request.user,
                title=f"Application update: {job.title}",
                message=(
                    "Your application was evaluated as not qualified for this position. "
                    "Review your recommended alternative openings."
                    if email_sent else
                    "Your application was evaluated as not qualified for this position. "
                    "The email notification could not be delivered."
                ),
                type='application'
            )

            messages.info(
                request,
                f"Your application for '{job.title}' was submitted. While you did not meet all specific prerequisites for this role, we have recommended alternative jobs matching your profile below!"
                + (" We could not deliver the email notification." if not email_sent else "")
            )

        # Notify admin of new application
        for admin_u in User.objects.filter(role='admin'):
            Notification.objects.create(
                user=admin_u,
                title=f"New Application: {job.title}",
                message=f"{request.user.full_name} applied for '{job.title}' ({eval_result['qualification_status'].replace('_', ' ').title()}, {match_score}%).",
                type='application'
            )

        return redirect('my_applications')

    match_score = calculate_match_score(profile, job)
    return render(request, 'applicant/apply_job.html', {
        'job': job,
        'profile': profile,
        'match_score': match_score
    })


@applicant_required
@require_POST
def check_application_ai_ajax(request, pk):
    """AI Application Quality, Document Validity & Alignment Checker."""
    profile, _ = ApplicantProfile.objects.get_or_create(user=request.user)
    job = get_object_or_404(JobPosting, pk=pk, status='active')

    cover_letter = request.POST.get('cover_letter', '').strip()
    use_profile_resume = request.POST.get('use_profile_resume') == 'true'

    # 1. Resume Extraction & Validation
    resume_file = None
    resume_text = ""
    resume_name = ""
    file_uploaded = 'resume_file' in request.FILES

    if file_uploaded:
        uploaded_file = request.FILES['resume_file']
        resume_name = uploaded_file.name
        from ml_engine.parser import extract_text_from_pdf, extract_text_from_docx
        ext = os.path.splitext(resume_name)[1].lower()
        if ext == '.pdf':
            resume_text = extract_text_from_pdf(uploaded_file)
        elif ext in ['.docx', '.doc']:
            resume_text = extract_text_from_docx(uploaded_file)
    elif use_profile_resume and profile.resume_file:
        resume_file = profile.resume_file
        resume_name = os.path.basename(profile.resume_file.name)
        if hasattr(profile, 'parsed_resume_text') and profile.parsed_resume_text:
            resume_text = profile.parsed_resume_text
        else:
            from ml_engine.parser import extract_text_from_pdf, extract_text_from_docx
            ext = os.path.splitext(resume_name)[1].lower()
            try:
                if os.path.exists(profile.resume_file.path):
                    if ext == '.pdf':
                        resume_text = extract_text_from_pdf(profile.resume_file.path)
                    elif ext in ['.docx', '.doc']:
                        resume_text = extract_text_from_docx(profile.resume_file.path)
            except Exception:
                pass

    from ml_engine.parser import validate_and_audit_resume

    # Case A: No file chosen / uploaded
    if not file_uploaded and not (use_profile_resume and profile.resume_file):
        return JsonResponse({
            'status': 'success',
            'is_valid_resume': False,
            'rejection_reason': None,
            'overall_score': 0,
            'readiness_badge': 'Incomplete — Resume Required',
            'readiness_class': 'danger',
            'resume_score': 0,
            'resume_feedback': [{
                'type': 'warning',
                'icon': 'fa-triangle-exclamation',
                'text': 'Please attach a verified resume to complete your application.'
            }],
            'resume_suggestions': ['Attach a professional resume/CV to enable AI match scoring and recruiter review.'],
            'cover_score': 0,
            'cover_feedback': [],
            'has_resume': False
        })

    # Case B: File provided -> Validate content with AI
    resume_audit = validate_and_audit_resume(resume_text)

    if not resume_audit.get('is_valid_resume', False):
        rejection_msg = resume_audit.get('rejection_reason', 'The uploaded file is empty, unreadable, or not a genuine Resume/CV.')
        return JsonResponse({
            'status': 'error',
            'is_valid_resume': False,
            'rejection_reason': rejection_msg,
            'overall_score': 0,
            'readiness_badge': 'Upload Cancelled: Not a Resume',
            'readiness_class': 'danger',
            'resume_score': 0,
            'resume_feedback': [{
                'type': 'danger',
                'icon': 'fa-ban',
                'text': rejection_msg
            }],
            'resume_suggestions': [
                'Please upload a genuine, readable Resume or CV containing your work experience, education, and technical skills.'
            ],
            'cover_score': 0,
            'cover_feedback': [],
            'has_resume': False
        })

    has_resume = True

    # Job requirements & Skill matching
    job_skills_raw = job.skills_required or ""
    job_skills = [s.strip() for s in re.split(r'[,;\n]+', job_skills_raw) if s.strip()]

    profile_skills = profile.get_skills_list()
    combined_skills = set(s.lower() for s in profile_skills)
    if resume_text:
        from ml_engine.parser import extract_skills
        extracted = extract_skills(resume_text)
        for s in extracted:
            combined_skills.add(s.lower())

    matched_skills = [s for s in job_skills if s.lower() in combined_skills]
    missing_skills = [s for s in job_skills if s.lower() not in combined_skills]

    resume_feedback = []
    resume_score = resume_audit.get('strength_score', 60)
    resume_suggestions = resume_audit.get('suggestions', [])
    strength_level = resume_audit.get('strength_level', 'Moderate')

    if strength_level == 'Weak':
        resume_feedback.append({
            'type': 'warning',
            'icon': 'fa-triangle-exclamation',
            'text': f'Resume Strength is Weak ({resume_score}%). Check AI recommendations below to strengthen your profile.'
        })
    elif strength_level == 'Moderate':
        resume_feedback.append({
            'type': 'info',
            'icon': 'fa-circle-info',
            'text': f'Resume Strength is Moderate ({resume_score}%). A few enhancements will make your resume top-tier.'
        })
    else:
        resume_feedback.append({
            'type': 'success',
            'icon': 'fa-circle-check',
            'text': f'Resume Verified & Highly Competitive ({resume_score}% AI Strength Score).'
        })

    if resume_name:
        resume_feedback.append({
            'type': 'success',
            'icon': 'fa-file-lines',
            'text': f'Parsed document: "{resume_name}".'
        })

    # Skill alignment
    if job_skills:
        if len(matched_skills) >= len(job_skills) * 0.7:
            resume_feedback.append({
                'type': 'success',
                'icon': 'fa-wand-magic-sparkles',
                'text': f'Strong skill match: {len(matched_skills)} of {len(job_skills)} required competencies detected.'
            })
        else:
            resume_feedback.append({
                'type': 'warning',
                'icon': 'fa-circle-info',
                'text': f'Partial skill match: {len(matched_skills)} of {len(job_skills)} found. Consider highlighting: {", ".join(missing_skills[:3])}.'
            })
    else:
        resume_feedback.append({
            'type': 'success',
            'icon': 'fa-circle-check',
            'text': 'Resume competencies aligned with position expectations.'
        })

    resume_score = min(100, max(0, resume_score))

    # 2. Cover Letter Check
    cover_feedback = []
    cover_score = 0
    words = cover_letter.split()
    word_count = len(words)

    if not cover_letter:
        cover_score = 40
        cover_feedback.append({
            'type': 'warning',
            'icon': 'fa-circle-info',
            'text': 'No cover letter pitch provided. Adding a tailored note significantly increases recruiter interview rates.'
        })
    else:
        cover_score = 45
        
        # Length evaluation
        if word_count < 25:
            cover_feedback.append({
                'type': 'warning',
                'icon': 'fa-ruler-horizontal',
                'text': f'Pitch is very short ({word_count} words). Aim for 50–250 words to explain your impact.'
            })
        elif 25 <= word_count <= 400:
            cover_score += 20
            cover_feedback.append({
                'type': 'success',
                'icon': 'fa-circle-check',
                'text': f'Ideal length: {word_count} words (concise and easy for hiring managers to digest).'
            })
        else:
            cover_score += 10
            cover_feedback.append({
                'type': 'info',
                'icon': 'fa-ruler-horizontal',
                'text': f'Detailed length: {word_count} words. Ensure your core achievements remain prominent.'
            })

        # Company mention check
        company_name_lower = (job.company_name or '').lower()
        if company_name_lower and company_name_lower in cover_letter.lower():
            cover_score += 15
            cover_feedback.append({
                'type': 'success',
                'icon': 'fa-building',
                'text': f'Personalized: mentions "{job.company_name}" directly.'
            })
        else:
            cover_feedback.append({
                'type': 'warning',
                'icon': 'fa-pen-to-square',
                'text': f'Tip: Mentioning "{job.company_name}" by name creates a personalized, professional impression.'
            })

        # Role mention check
        title_words = [w.lower() for w in re.findall(r'\w+', job.title) if len(w) > 3]
        role_matched = any(tw in cover_letter.lower() for tw in title_words)
        if role_matched:
            cover_score += 10
            cover_feedback.append({
                'type': 'success',
                'icon': 'fa-briefcase',
                'text': f'Explicitly targets the "{job.title}" position.'
            })

        # Action verbs check
        action_verbs = {'led', 'built', 'developed', 'designed', 'managed', 'implemented', 'optimized', 'created', 'achieved', 'improved', 'engineered', 'launched', 'delivered', 'collaborated', 'scaled'}
        detected_verbs = [v for v in action_verbs if re.search(r'\b' + v + r'\b', cover_letter, re.I)]
        if len(detected_verbs) >= 2:
            cover_score += 10
            cover_feedback.append({
                'type': 'success',
                'icon': 'fa-bolt',
                'text': f'High-impact tone with strong action verbs ({", ".join(detected_verbs[:3])}).'
            })
        else:
            cover_feedback.append({
                'type': 'info',
                'icon': 'fa-lightbulb',
                'text': 'Consider adding impactful action verbs like developed, engineered, or optimized.'
            })

    cover_score = min(100, max(0, cover_score))

    # Overall Combined Readiness
    overall_score = int((resume_score * 0.6) + (cover_score * 0.4))
    if not has_resume:
        overall_score = min(35, overall_score)

    if overall_score >= 80:
        readiness_badge = "Excellent — Highly Competitive"
        readiness_class = "success"
    elif overall_score >= 60:
        readiness_badge = "Good — Ready to Submit"
        readiness_class = "primary"
    elif overall_score >= 40:
        readiness_badge = "Average — Review Suggestions"
        readiness_class = "warning"
    else:
        readiness_badge = "Incomplete — Resume Required"
        readiness_class = "danger"

    return JsonResponse({
        'status': 'success',
        'is_valid_resume': True,
        'overall_score': overall_score,
        'readiness_badge': readiness_badge,
        'readiness_class': readiness_class,
        'resume_score': resume_score,
        'resume_feedback': resume_feedback,
        'resume_suggestions': resume_suggestions,
        'matched_skills': matched_skills,
        'missing_skills': missing_skills,
        'cover_score': cover_score,
        'cover_feedback': cover_feedback,
        'has_resume': has_resume,
    })


@applicant_required
@require_POST
def generate_cover_letter_ai_ajax(request, pk):
    """AI Generator that crafts a personalized, role-aligned cover letter draft."""
    profile, _ = ApplicantProfile.objects.get_or_create(user=request.user)
    job = get_object_or_404(JobPosting, pk=pk, status='active')

    candidate_name = request.user.full_name
    company_name = job.company_name
    job_title = job.title
    skills = profile.get_skills_list()
    top_skills = ", ".join(skills[:4]) if skills else "modern software engineering and technology"
    exp = profile.experience_years or 2

    draft = (
        f"Dear Hiring Team at {company_name},\n\n"
        f"I am writing to express my strong enthusiasm for the {job_title} position. "
        f"With over {exp} years of dedicated experience specializing in {top_skills}, "
        f"I have consistently delivered scalable solutions, robust architectures, and collaborative team outcomes.\n\n"
        f"What excites me most about {company_name} is your commitment to technical excellence and industry innovation. "
        f"My background in designing high-impact systems, optimizing workflows, and rapidly mastering new toolsets aligns directly "
        f"with the requirements outlined in your job posting.\n\n"
        f"I would welcome the opportunity to discuss how my technical qualifications, problem-solving mindset, and drive can add immediate value to the team at {company_name}.\n\n"
        f"Thank you for your time and consideration.\n\n"
        f"Sincerely,\n{candidate_name}"
    )

    return JsonResponse({
        'status': 'success',
        'cover_letter': draft
    })


@applicant_required
def my_applications(request):
    """Applicant's tracking center for all submitted applications."""
    profile, _ = ApplicantProfile.objects.get_or_create(user=request.user)
    applications = Application.objects.filter(applicant=profile).select_related('job', 'job__employer').prefetch_related('interviews').order_by('-applied_at')

    # Find alternative recommendations for any unqualified applications or empty list
    unqualified_recs = find_alternative_job_recommendations(profile, limit=4)

    return render(request, 'applicant/my_applications.html', {
        'applications': applications,
        'profile': profile,
        'unqualified_recs': unqualified_recs,
    })


@applicant_required
def withdraw_application(request, pk):
    """Withdraw a pending application."""
    profile, _ = ApplicantProfile.objects.get_or_create(user=request.user)
    app = get_object_or_404(Application, pk=pk, applicant=profile)
    job_title = app.job.title
    app_id = app.id
    app.delete()

    log_audit(
        request,
        'withdraw_application',
        f"Applicant {request.user.full_name} withdrew application for '{job_title}'",
        target_type='application',
        target_id=app_id,
        target_name=job_title
    )

    messages.info(request, f"Your application for '{job_title}' has been withdrawn.")
    return redirect('my_applications')


# ==========================================
# EMPLOYER VIEWS
# ==========================================

@employer_required
def employer_dashboard(request):
    """Employer main dashboard view with analytics, pipeline tracker, and AI talent radar."""
    employer_profile, _ = EmployerProfile.objects.get_or_create(user=request.user)
    posted_jobs = JobPosting.objects.filter(employer=employer_profile)
    talent_requests = EmployerRequest.objects.filter(employer=employer_profile)
    total_jobs = posted_jobs.count()
    active_jobs = posted_jobs.filter(status='active').count()

    applications = Application.objects.filter(job__employer=employer_profile).select_related('applicant__user', 'job')
    total_candidates = applications.count()
    pending_count = applications.filter(status__in=['pending', 'applied']).count()
    qualified_count = applications.filter(qualification_status='qualified').count()
    under_review_count = applications.filter(status='under_review').count()
    shortlisted_count = applications.filter(employer_decision='shortlisted').count()
    interview_count = applications.filter(status='interviewed').count()
    hired_count = applications.filter(employer_decision='selected').count()
    rejected_count = applications.filter(employer_decision='rejected').count()

    # Candidates sent by Admin for review
    sent_candidates = applications.filter(sent_to_employer=True).order_by('-match_score')
    sent_candidates_count = sent_candidates.count()

    recent_candidates_data = []
    for rank_idx, app in enumerate(sent_candidates[:6], start=1):
        ranking_info = rank_candidate_application(app)
        recent_candidates_data.append({
            'application': app,
            'ml_score': ranking_info['ml_ranking_score'],
            'ranking_category': ranking_info['ranking_category'],
            'radar_rank': app.radar_rank or rank_idx,
            'is_top_match': (app.radar_rank == 1 or rank_idx == 1),
            'skills': app.applicant.get_skills_list()[:3]
        })

    upcoming_interviews = InterviewSchedule.objects.filter(
        employer=employer_profile,
        status='scheduled'
    ).select_related('application__applicant__user', 'application__job').order_by('interview_date', 'start_time')[:5]

    # Active postings breakdown with applicant count
    active_postings = []
    for j in posted_jobs.filter(status='active').order_by('-posted_at')[:4]:
        j_apps = applications.filter(job=j)
        active_postings.append({
            'job': j,
            'total_applicants': j_apps.count(),
            'qualified_count': j_apps.filter(qualification_status='qualified').count(),
            'sent_count': j_apps.filter(sent_to_employer=True).count(),
            'shortlisted': j_apps.filter(employer_decision='shortlisted').count(),
            'selected': j_apps.filter(employer_decision='selected').count()
        })

    return render(request, 'employer/dashboard.html', {
        'employer': employer_profile,
        'total_jobs': total_jobs,
        'active_jobs': active_jobs,
        'talent_requests': talent_requests[:5],
        'total_candidates': total_candidates,
        'pending_count': pending_count,
        'qualified_count': qualified_count,
        'under_review_count': under_review_count,
        'sent_candidates_count': sent_candidates_count,
        'shortlisted_count': shortlisted_count,
        'interview_count': interview_count,
        'hired_count': hired_count,
        'rejected_count': rejected_count,
        'recent_candidates': recent_candidates_data,
        'upcoming_interviews': upcoming_interviews,
        'active_postings': active_postings,
    })


@employer_required
def employer_candidates(request):
    """Employer pipeline of candidates provided by Admin, with ML ranking, multi-filters and sorting."""
    employer_profile, _ = EmployerProfile.objects.get_or_create(user=request.user)
    job_id = request.GET.get('job_id', '')
    status_filter = request.GET.get('status', '')
    decision_filter = request.GET.get('decision', '')
    category_filter = request.GET.get('category', '').strip()
    sort_by = request.GET.get('sort', 'score')
    query = request.GET.get('q', '').strip()

    posted_jobs = JobPosting.objects.filter(employer=employer_profile)
    base_apps = Application.objects.filter(
        job__employer=employer_profile,
        sent_to_employer=True
    ).select_related('applicant__user', 'job')

    status_counts = {
        'all': base_apps.count(),
        'pending': base_apps.filter(
            Q(employer_decision='none') | Q(status__in=['pending', 'applied', 'under_review', 'qualified'])
        ).count(),
        'shortlisted': base_apps.filter(
            Q(employer_decision='shortlisted') | Q(status='shortlisted')
        ).count(),
        'interviewed': base_apps.filter(status='interviewed').count(),
        'accepted': base_apps.filter(
            Q(employer_decision='selected') | Q(status__in=['accepted', 'selected'])
        ).count(),
        'rejected': base_apps.filter(
            Q(employer_decision='rejected') | Q(status__in=['rejected', 'not_qualified'])
        ).count(),
    }

    apps_qs = base_apps
    if job_id:
        apps_qs = apps_qs.filter(job_id=job_id)
    if decision_filter:
        apps_qs = apps_qs.filter(employer_decision=decision_filter)
    if status_filter:
        if status_filter == 'pending':
            apps_qs = apps_qs.filter(
                Q(employer_decision='none') | Q(status__in=['pending', 'applied', 'under_review', 'qualified'])
            )
        elif status_filter == 'shortlisted':
            apps_qs = apps_qs.filter(
                Q(employer_decision='shortlisted') | Q(status='shortlisted')
            )
        elif status_filter == 'interviewed':
            apps_qs = apps_qs.filter(status='interviewed')
        elif status_filter == 'accepted':
            apps_qs = apps_qs.filter(
                Q(employer_decision='selected') | Q(status__in=['accepted', 'selected'])
            )
        elif status_filter == 'rejected':
            apps_qs = apps_qs.filter(
                Q(employer_decision='rejected') | Q(status__in=['rejected', 'not_qualified'])
            )
        else:
            apps_qs = apps_qs.filter(status=status_filter)

    if query:
        apps_qs = apps_qs.filter(
            Q(applicant__user__first_name__icontains=query) |
            Q(applicant__user__last_name__icontains=query) |
            Q(applicant__user__email__icontains=query) |
            Q(applicant__skills__icontains=query) |
            Q(applicant__qualifications__icontains=query) |
            Q(job__title__icontains=query)
        )

    # Order candidates by score descending to determine Talent Radar top matches
    sorted_apps = list(apps_qs.order_by('-match_score'))
    candidates_data = []
    for rank_idx, app in enumerate(sorted_apps, start=1):
        ranking_info = rank_candidate_application(app)
        cand_score = float(app.match_score) or ranking_info['ml_ranking_score']
        cand_category = ranking_info['ranking_category']

        # Category filter based on fit tier
        if category_filter:
            if category_filter == 'excellent' and cand_score < 85:
                continue
            elif category_filter == 'good' and not (70 <= cand_score < 85):
                continue
            elif category_filter == 'average' and not (50 <= cand_score < 70):
                continue
            elif category_filter == 'poor' and cand_score >= 50:
                continue

        candidates_data.append({
            'application': app,
            'ml_score': cand_score,
            'ranking_category': cand_category,
            'radar_rank': app.radar_rank or rank_idx,
            'is_top_match': (app.radar_rank == 1 or rank_idx == 1),
            'skills': app.applicant.get_skills_list()[:4]
        })

    # Sort based on selected criterion
    if sort_by == 'recent':
        candidates_data.sort(key=lambda x: x['application'].applied_at, reverse=True)
    elif sort_by == 'name':
        candidates_data.sort(key=lambda x: x['application'].applicant.user.full_name.lower())
    elif sort_by == 'exp':
        candidates_data.sort(key=lambda x: x['application'].applicant.experience_years or 0, reverse=True)
    else:  # 'score'
        candidates_data.sort(key=lambda x: x['ml_score'], reverse=True)

    return render(request, 'employer/candidates.html', {
        'candidates_data': candidates_data,
        'posted_jobs': posted_jobs,
        'selected_job_id': job_id,
        'selected_status': status_filter,
        'selected_decision': decision_filter,
        'selected_category': category_filter,
        'selected_sort': sort_by,
        'query': query,
        'status_counts': status_counts,
    })


@login_required
def view_candidate_resume(request, pk):
    """Show the original applicant resume in the browser."""
    application = get_object_or_404(
        Application.objects.select_related('applicant__user', 'job__employer__user'),
        pk=pk
    )
    user = request.user
    is_authorized_employer = user.is_employer and application.job.employer.user_id == user.id
    if not (user.is_admin_user or is_authorized_employer):
        return HttpResponseForbidden('You do not have permission to view this resume.')

    resume = application.applicant.resume_file
    if not resume:
        return HttpResponse('This candidate has not uploaded a resume.', status=404)

    extension = os.path.splitext(resume.name)[1].lower()
    if extension == '.pdf':
        response = FileResponse(resume.open('rb'), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{os.path.basename(resume.name)}"'
        return response

    return render(request, 'employer/resume_view.html', {
        'applicant': application.applicant,
        'resume_name': os.path.basename(resume.name),
        'is_docx': extension == '.docx',
        'resume_file_url': reverse('view_candidate_resume_file', kwargs={'pk': pk}),
    })


@login_required
def view_candidate_resume_file(request, pk):
    """Serve the original resume bytes to the in-browser preview renderer."""
    application = get_object_or_404(
        Application.objects.select_related('applicant__user', 'job__employer__user'),
        pk=pk
    )
    user = request.user
    is_authorized_employer = user.is_employer and application.job.employer.user_id == user.id
    if not (user.is_admin_user or is_authorized_employer):
        return HttpResponseForbidden('You do not have permission to view this resume.')

    resume = application.applicant.resume_file
    if not resume:
        return HttpResponse('This candidate has not uploaded a resume.', status=404)

    extension = os.path.splitext(resume.name)[1].lower()
    content_types = {
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.doc': 'application/msword',
        '.pdf': 'application/pdf',
    }
    response = FileResponse(resume.open('rb'), content_type=content_types.get(extension, 'application/octet-stream'))
    response['Content-Disposition'] = f'inline; filename="{os.path.basename(resume.name)}"'
    return response


def employer_candidate_detail(request, pk):
    """Detailed candidate profile review, skill comparison, remarks history, and interview scheduler."""
    is_admin_view = request.user.is_authenticated and request.user.is_admin_user
    application_query = Application.objects.select_related('applicant__user', 'job')
    if is_admin_view:
        app = get_object_or_404(application_query, pk=pk)
    else:
        employer_profile, _ = EmployerProfile.objects.get_or_create(user=request.user)
        app = get_object_or_404(application_query, pk=pk, job__employer=employer_profile)

    ranking_info = rank_candidate_application(app)
    interviews = app.interviews.all().order_by('-interview_date')
    remarks_list = app.get_remarks_list()

    # Skill comparison breakdown
    job_skills_list = app.job.get_skills_list()
    cand_skills_list = app.applicant.get_skills_list()
    job_skills_set = set(s.lower().strip() for s in job_skills_list if s.strip())
    cand_skills_set = set(s.lower().strip() for s in cand_skills_list if s.strip())

    matched_skills = [s for s in cand_skills_list if s.lower().strip() in job_skills_set]
    missing_skills = [s for s in job_skills_list if s.lower().strip() not in cand_skills_set]
    extra_skills = [s for s in cand_skills_list if s.lower().strip() not in job_skills_set]

    # Match score components
    skill_match_pct = int(app.skills_match_score) if app.skills_match_score else (int((len(matched_skills) / max(1, len(job_skills_list))) * 100) if job_skills_list else 85)
    exp_alignment = min(100, max(50, (app.applicant.experience_years or 1) * 20))
    edu_alignment = 95 if app.applicant.education_level else 60

    return render(request, 'employer/candidate_detail.html', {
        'application': app,
        'applicant': app.applicant,
        'ml_score': float(app.match_score) or ranking_info['ml_ranking_score'],
        'ranking_category': ranking_info['ranking_category'],
        'radar_rank': app.radar_rank,
        'is_top_match': (app.radar_rank == 1),
        'interviews': interviews,
        'remarks_list': remarks_list,
        'matched_skills': matched_skills,
        'missing_skills': missing_skills,
        'extra_skills': extra_skills,
        'skill_match_pct': skill_match_pct,
        'exp_alignment': exp_alignment,
        'edu_alignment': edu_alignment,
        'is_admin_view': is_admin_view,
    })


@employer_required
@require_POST
def employer_decide_candidate(request, pk):
    """
    Employer records hiring decision: 'shortlist', 'reject', or 'select' (Hire candidate).
    Stores final decision, notes, timestamps, and logs audit trail.
    """
    employer_profile, _ = EmployerProfile.objects.get_or_create(user=request.user)
    app = get_object_or_404(Application, pk=pk, job__employer=employer_profile)

    decision = request.POST.get('decision')  # 'shortlisted', 'rejected', 'selected'
    notes = request.POST.get('decision_notes', '').strip()

    if decision in ['shortlisted', 'rejected', 'selected']:
        app.employer_decision = decision
        app.employer_decision_at = timezone.now()
        app.employer_decision_notes = notes

        # Update application status
        if decision == 'selected':
            app.status = 'selected'
            status_text = "Selected for Hiring"
        elif decision == 'shortlisted':
            app.status = 'shortlisted'
            status_text = "Shortlisted"
        elif decision == 'rejected':
            app.status = 'rejected'
            status_text = "Not Selected"

        app.add_remark(app.status, f"Employer Decision: {status_text}. Notes: {notes}", employer_profile.display_name)
        app.save()

        log_audit(
            request,
            f"employer_decision_{decision}",
            f"Employer {request.user.full_name} ({employer_profile.display_name}) marked candidate {app.applicant.user.full_name} as '{status_text}' for '{app.job.title}'",
            target_type='application',
            target_id=app.id,
            target_name=app.applicant.user.full_name
        )

        # Notify applicant
        Notification.objects.create(
            user=app.applicant.user,
            title=f"Application Update: {status_text}",
            message=f"{employer_profile.display_name} has updated your candidate status to '{status_text}' for '{app.job.title}'.",
            type='application'
        )

        # If job has linked talent_request and candidate is selected, update request status
        if decision == 'selected' and app.job.talent_request:
            req = app.job.talent_request
            req.status = 'completed'
            req.save()

        messages.success(request, f"Decision recorded! Candidate {app.applicant.user.full_name} marked as '{status_text}'.")

    return redirect('employer_candidates')


@employer_required
@require_POST
def update_application_status(request, pk):
    """Updates status with remark history."""
    employer_profile, _ = EmployerProfile.objects.get_or_create(user=request.user)
    app = get_object_or_404(Application, pk=pk, job__employer=employer_profile)

    new_status = request.POST.get('status')
    remarks_text = request.POST.get('remarks', '').strip()

    if new_status:
        reviewer_name = employer_profile.display_name
        app.add_remark(new_status, remarks_text, reviewer_name)
        app.reviewed_by_employer_id = employer_profile.id
        app.save()

        log_audit(
            request,
            f"candidate_status_{new_status}",
            f"Employer {request.user.full_name} updated candidate {app.applicant.user.full_name} status to '{app.get_status_display()}' for '{app.job.title}'",
            target_type='application',
            target_id=app.id,
            target_name=app.applicant.user.full_name
        )

        # Send notification to applicant
        Notification.objects.create(
            user=app.applicant.user,
            title="Application Status Updated",
            message=f"Your application status for '{app.job.title}' was updated to '{app.get_status_display()}'.",
            type='application'
        )

        messages.success(request, f"Candidate status updated to '{app.get_status_display()}'.")

    return redirect('employer_candidate_detail', pk=pk)


@employer_required
@require_POST
def schedule_interview(request, pk):
    """Schedules an interview appointment with candidate."""
    employer_profile, _ = EmployerProfile.objects.get_or_create(user=request.user)
    app = get_object_or_404(Application, pk=pk, job__employer=employer_profile)

    interview_date = request.POST.get('interview_date')
    start_time = request.POST.get('start_time')
    end_time = request.POST.get('end_time')
    interview_type = request.POST.get('interview_type', 'video')
    location = request.POST.get('location', '')
    meeting_link = request.POST.get('meeting_link', '')
    notes = request.POST.get('notes', '')

    if interview_date and start_time and end_time:
        sched = InterviewSchedule.objects.create(
            application=app,
            employer=employer_profile,
            interview_date=interview_date,
            start_time=start_time,
            end_time=end_time,
            interview_type=interview_type,
            location=location,
            meeting_link=meeting_link,
            notes=notes,
            status='scheduled'
        )

        # Update application status to interviewed
        app.add_remark('interviewed', f"Scheduled {interview_type} interview for {interview_date} at {start_time}", employer_profile.display_name)
        app.save()

        log_audit(
            request,
            'schedule_interview',
            f"Employer {request.user.full_name} scheduled {interview_type} interview with {app.applicant.user.full_name} for '{app.job.title}' on {interview_date} at {start_time}",
            target_type='interview',
            target_id=sched.id,
            target_name=app.applicant.user.full_name
        )

        # Notify applicant
        Notification.objects.create(
            user=app.applicant.user,
            title="Interview Scheduled!",
            message=f"You have been invited for an interview for '{app.job.title}' on {interview_date} at {start_time}.",
            type='application'
        )

        messages.success(request, f"Interview scheduled with {app.applicant.user.full_name}!")

    return redirect('employer_candidate_detail', pk=pk)


@employer_required
def recommended_candidates(request):
    """
    Talent Radar: Displays and ranks qualified candidates sent by Admin for the employer's active openings.
    Clearly highlights the '#1 Top Candidate' match.
    """
    employer_profile, _ = EmployerProfile.objects.get_or_create(user=request.user)
    active_jobs = JobPosting.objects.filter(employer=employer_profile, status='active')
    talent_requests = EmployerRequest.objects.filter(employer=employer_profile)
    
    job_id = request.GET.get('job_id')
    request_id = request.GET.get('request_id')

    selected_job = None
    if request_id:
        talent_req = talent_requests.filter(pk=request_id).first()
        if talent_req and talent_req.job_postings.exists():
            selected_job = talent_req.job_postings.first()
    elif job_id:
        selected_job = active_jobs.filter(pk=job_id).first()
    elif active_jobs.exists():
        selected_job = active_jobs.first()

    recommendations = []
    high_match_count = 0
    total_score_sum = 0.0

    if selected_job:
        job_skills_raw = selected_job.skills_required or ''
        job_skills_set = set(s.lower().strip() for s in re.split(r'[,;\n]+', job_skills_raw) if s.strip())

        # Pull applications sent by Admin for this job
        sent_apps = Application.objects.filter(
            job=selected_job,
            sent_to_employer=True
        ).select_related('applicant__user').order_by('-match_score')

        # If no applications yet marked sent, also allow previewing qualified applications
        if not sent_apps.exists():
            sent_apps = Application.objects.filter(
                job=selected_job,
                qualification_status='qualified'
            ).select_related('applicant__user').order_by('-match_score')

        for rank_idx, app in enumerate(sent_apps, start=1):
            applicant = app.applicant
            score = float(app.match_score) or calculate_match_score(applicant, selected_job)
            applicant_skills_list = applicant.get_skills_list()
            applicant_skills_lower = set(s.lower().strip() for s in applicant_skills_list)
            
            matched_skills = [s for s in applicant_skills_list if s.lower().strip() in job_skills_set]
            other_skills = [s for s in applicant_skills_list if s.lower().strip() not in job_skills_set]
            missing_skills = [s.strip() for s in re.split(r'[,;\n]+', job_skills_raw) if s.strip() and s.lower().strip() not in applicant_skills_lower]

            if score >= 80:
                fit_level = "Excellent Fit"
                fit_badge = "badge-match-excellent"
                high_match_count += 1
            elif score >= 60:
                fit_level = "Good Match"
                fit_badge = "badge-match-good"
            else:
                fit_level = "Moderate Fit"
                fit_badge = "badge-match-average"

            total_score_sum += float(score)
            recommendations.append({
                'application': app,
                'applicant': applicant,
                'match_score': int(score),
                'fit_level': fit_level,
                'fit_badge': fit_badge,
                'radar_rank': app.radar_rank or rank_idx,
                'is_top_match': (app.radar_rank == 1 or rank_idx == 1),
                'matched_skills': matched_skills,
                'missing_skills': missing_skills[:4],
                'other_skills': other_skills[:4],
                'job': selected_job,
                'employer_decision': app.employer_decision
            })

    avg_score = round(total_score_sum / len(recommendations), 1) if recommendations else 0.0

    return render(request, 'employer/recommended_candidates.html', {
        'active_jobs': active_jobs,
        'talent_requests': talent_requests,
        'selected_job': selected_job,
        'recommendations': recommendations,
        'high_match_count': high_match_count,
        'avg_score': avg_score,
        'total_matches': len(recommendations)
    })


# ==========================================
# ADMIN CANDIDATE MANAGEMENT & DISPATCH
# ==========================================

@admin_required
def admin_job_candidates(request, pk):
    """
    Admin Candidate Management: Overview of all applicants for a job posting.
    Displays match breakdown, qualification status, and triggers bulk actions.
    """
    job = get_object_or_404(JobPosting.objects.select_related('employer', 'talent_request'), pk=pk)
    status_filter = request.GET.get('status', '')
    qual_filter = request.GET.get('qual', '')
    sort_by = request.GET.get('sort', 'score')
    query = request.GET.get('q', '').strip()

    base_apps = Application.objects.filter(job=job).select_related('applicant__user')

    counts = {
        'all': base_apps.count(),
        'total': base_apps.count(),
        'qualified': base_apps.filter(qualification_status='qualified').count(),
        'under_qualified': base_apps.filter(qualification_status='under_qualified').count(),
        'not_qualified': base_apps.filter(qualification_status='not_qualified').count(),
        'under_review': base_apps.filter(status='under_review').count(),
        'sent_to_employer': base_apps.filter(sent_to_employer=True).count(),
        'shortlisted': base_apps.filter(employer_decision='shortlisted').count(),
        'selected': base_apps.filter(employer_decision='selected').count(),
    }

    apps_qs = base_apps
    if qual_filter:
        apps_qs = apps_qs.filter(qualification_status=qual_filter)
    if status_filter:
        if status_filter == 'sent':
            apps_qs = apps_qs.filter(sent_to_employer=True)
        else:
            apps_qs = apps_qs.filter(status=status_filter)

    if query:
        apps_qs = apps_qs.filter(
            Q(applicant__user__first_name__icontains=query) |
            Q(applicant__user__last_name__icontains=query) |
            Q(applicant__user__email__icontains=query) |
            Q(applicant__skills__icontains=query)
        )

    # Convert to candidate cards with ranking & breakdown
    sorted_apps = list(apps_qs.order_by('-match_score'))
    candidates = []
    job_skills_list = job.get_skills_list()
    job_skills_set = set(s.lower().strip() for s in job_skills_list)

    for rank_idx, app in enumerate(sorted_apps, start=1):
        applicant = app.applicant
        cand_skills = applicant.get_skills_list()
        matched_skills = [s for s in cand_skills if s.lower().strip() in job_skills_set]
        missing_skills = [s for s in job_skills_list if s.lower().strip() not in set(cs.lower().strip() for cs in cand_skills)]

        candidates.append({
            'application': app,
            'applicant': applicant,
            'match_score': float(app.match_score),
            'skills_match_score': float(app.skills_match_score),
            'exp_match_score': float(app.exp_match_score),
            'edu_match_score': float(app.edu_match_score),
            'radar_rank': app.radar_rank or rank_idx,
            'is_top_match': (app.radar_rank == 1 or rank_idx == 1),
            'matched_skills': matched_skills,
            'missing_skills': missing_skills[:3],
            'qualification_status': app.qualification_status,
            'qualification_reason': app.qualification_reason,
            'notification_sent': app.notification_sent,
            'notification_sent_at': app.notification_sent_at,
            'sent_to_employer': app.sent_to_employer,
            'employer_decision': app.employer_decision,
        })

    # Sort
    if sort_by == 'lowest':
        candidates.sort(key=lambda x: x['match_score'])
    elif sort_by == 'name':
        candidates.sort(key=lambda x: x['applicant'].user.full_name.lower())
    elif sort_by == 'exp':
        candidates.sort(key=lambda x: x['applicant'].experience_years or 0, reverse=True)
    else:  # 'score'
        candidates.sort(key=lambda x: x['match_score'], reverse=True)

    recent_exports = CandidateExport.objects.filter(job=job).select_related('exported_by').order_by('-created_at')[:5]

    return render(request, 'admin/job_candidates.html', {
        'job': job,
        'candidates': candidates,
        'counts': counts,
        'recent_exports': recent_exports,
        'google_drive_folder_url': f"https://drive.google.com/drive/folders/{getattr(settings, 'GOOGLE_DRIVE_FOLDER_ID', '')}",
        'selected_qual': qual_filter,
        'selected_status': status_filter,
        'selected_sort': sort_by,
        'query': query
    })


@admin_required
@require_POST
def admin_notify_qualified_applicants(request, pk):
    """
    One-Click Qualified Applicant Notification:
    Finds all qualified applicants for the job, sends 'Your application is under review' email,
    updates application status, and records notification.
    """
    job = get_object_or_404(JobPosting, pk=pk)
    qualified_apps = Application.objects.filter(job=job, qualification_status='qualified')

    notified_count = 0
    for app in qualified_apps:
        email_sent = send_application_under_review_email(request, app)
        app.notification_sent = email_sent
        app.notification_sent_at = timezone.now() if email_sent else None
        app.status = 'under_review'
        app.save()
        if email_sent:
            notified_count += 1

    log_audit(
        request,
        'notify_qualified_applicants',
        f"Admin dispatched 'Under Review' notifications to {notified_count} qualified candidates for '{job.title}'",
        target_type='job',
        target_id=job.id,
        target_name=job.title
    )

    messages.success(request, f"Successfully notified {notified_count} qualified candidate(s) for '{job.title}'!")
    return redirect('admin_job_candidates', pk=pk)


@admin_required
@require_POST
def admin_notify_single_applicant(request, pk):
    """Admin notifies a single applicant of their qualification status."""
    app = get_object_or_404(Application.objects.select_related('job', 'applicant__user'), pk=pk)

    if app.qualification_status == 'qualified':
        email_sent = send_application_under_review_email(request, app)
        app.status = 'under_review'
        msg_type = "Under Review notification"
        notification_message = "Your application is under review."
    elif app.qualification_status == 'under_qualified':
        recs = find_alternative_job_recommendations(app.applicant, exclude_job_id=app.job.id, limit=3)
        email_sent = send_application_not_qualified_email(request, app, recs)
        app.status = 'not_qualified'
        msg_type = "Under-Qualified notification with alternative recommendations"
        notification_message = "Your application was evaluated as under qualified. Review your alternative job recommendations."
    else:
        recs = find_alternative_job_recommendations(app.applicant, exclude_job_id=app.job.id, limit=3)
        email_sent = send_application_not_qualified_email(request, app, recs)
        app.status = 'not_qualified'
        msg_type = "Not-Qualified notification with alternative recommendations"
        notification_message = "Your application was evaluated as not qualified. Review your alternative job recommendations."

    app.notification_sent = email_sent
    app.notification_sent_at = timezone.now() if email_sent else None
    app.save()

    Notification.objects.create(
        user=app.applicant.user,
        title=f"Application update: {app.job.title}",
        message=notification_message + (" Email delivery failed; please check your email settings." if not email_sent else ""),
        type='application'
    )

    log_audit(
        request,
        'notify_single_applicant',
        f"Admin dispatched {msg_type} to {app.applicant.user.email} for '{app.job.title}'",
        target_type='application',
        target_id=app.id,
        target_name=app.applicant.user.full_name
    )

    if email_sent:
        messages.success(request, f"Dispatched {msg_type} to {app.applicant.user.full_name} ({app.applicant.user.email}).")
    else:
        messages.error(
            request,
            f"Could not deliver {msg_type.lower()} email to {app.applicant.user.email}. "
            "An in-app notification was dispatched."
        )
    return redirect('admin_job_candidates', pk=app.job.id)


@admin_required
@require_POST
def admin_send_candidates_to_employer(request, pk):
    """
    Export Candidates & Send to Employer with Google Drive View-Only Access:
    1. Collects evaluated candidates (both Qualified and Not Qualified).
    2. Ranks qualified candidates for Talent Radar (1 = Top Match) and marks them sent.
    3. Generates comprehensive Excel (.xlsx) report containing all evaluated candidates.
    4. Uploads Excel workbook to Google Drive with strict View-Only (role='reader') permissions for the employer.
    5. Stores Google Drive file ID, view link, and embed link in CandidateExport model.
    6. Updates EmployerRequest status to 'candidates_sent' if linked.
    7. Dispatches email & in-app notifications to the Employer.
    8. Shows the required confirmation message.
    """
    job = get_object_or_404(JobPosting.objects.select_related('employer__user', 'talent_request'), pk=pk)
    
    # Check for specific selected candidates or all candidates for this job
    selected_candidate_ids = request.POST.getlist('selected_candidates')
    if selected_candidate_ids:
        apps_to_export = Application.objects.filter(job=job, id__in=selected_candidate_ids).select_related('applicant__user', 'job')
    else:
        apps_to_export = Application.objects.filter(job=job).select_related('applicant__user', 'job')

    if not apps_to_export.exists():
        messages.warning(request, f"No candidate applications found to export for '{job.title}'.")
        return redirect('admin_job_candidates', pk=pk)

    # 1. Update qualification ranking & sent status for qualified candidates
    qualified_apps = apps_to_export.filter(qualification_status='qualified').order_by('-match_score')
    for rank_idx, app in enumerate(qualified_apps, start=1):
        app.radar_rank = rank_idx
        app.sent_to_employer = True
        app.sent_to_employer_at = timezone.now()
        app.save()

    # 2. Generate corporate Excel workbook with both Qualified and Not Qualified candidates
    excel_buffer, filename = generate_candidates_excel(job, apps_to_export)
    excel_bytes = excel_buffer.getvalue()

    # 3. Upload to Google Drive with strict View-Only (reader) permissions for employer
    employer_email = job.employer.user.email if (job.employer and job.employer.user) else ""
    drive_result = upload_candidates_excel_to_drive(
        file_content_bytes=excel_bytes,
        filename=filename,
        employer_email=employer_email,
        folder_id=getattr(settings, 'GOOGLE_DRIVE_FOLDER_ID', None)
    )

    # 4. Record CandidateExport with Drive metadata when live, plus a local backup
    total_count = apps_to_export.count()
    qualified_count = apps_to_export.filter(qualification_status='qualified').count()
    not_qualified_count = apps_to_export.filter(qualification_status__in=['not_qualified', 'under_qualified']).count()

    candidate_export = CandidateExport(
        job=job,
        employer=job.employer,
        talent_request=job.talent_request,
        filename=filename,
        google_drive_file_id=drive_result.get('file_id', ''),
        google_drive_view_link=drive_result.get('web_view_link', ''),
        google_drive_embed_link=drive_result.get('embed_link', ''),
        exported_by=request.user,
        total_candidates=total_count,
        qualified_count=qualified_count,
        not_qualified_count=not_qualified_count,
        sent_to_employer=True
    )
    candidate_export.excel_file.save(filename, ContentFile(excel_bytes), save=True)

    # 5. Update linked talent request status
    if job.talent_request:
        job.talent_request.status = 'candidates_sent'
        job.talent_request.save()

    # 6. Notify employer via in-app & email
    if job.employer and job.employer.user:
        Notification.objects.create(
            user=job.employer.user,
            title="Qualified Candidates & Evaluation Report Ready!",
            message=f"Admin has exported {total_count} candidate evaluations ({qualified_count} qualified) for '{job.title}'. Access the report on Google Drive or your Talent Radar.",
            type='application'
        )

        if job.talent_request:
            send_candidates_sent_to_employer_email(request, job.talent_request, qualified_count)

    log_audit(
        request,
        'send_candidates_to_employer',
        f"Admin exported {total_count} candidates ({qualified_count} qualified, {not_qualified_count} not qualified) for '{job.title}' to Google Drive with view-only access and dispatched to employer {job.employer.display_name if job.employer else 'N/A'}",
        target_type='job',
        target_id=job.id,
        target_name=job.title
    )

    if drive_result.get('is_mock'):
        confirmation_message = (
            "Candidates exported successfully. Google Drive is not configured, "
            "so the Excel file was saved to local secure storage."
        )
    else:
        confirmation_message = (
            "Candidates successfully exported and sent to the employer. "
            "The Excel file has been saved to Google Drive with view-only access."
        )

    messages.success(
        request,
        confirmation_message
    )
    return redirect('admin_job_candidates', pk=pk)


@admin_required
def admin_export_candidates_excel(request, pk):
    """
    Direct Excel Export for Admin:
    Generates and downloads the corporate Excel spreadsheet (.xlsx) for evaluated candidates.
    Supports candidate filtering/selection or exports all applicants for this job.
    """
    job = get_object_or_404(JobPosting.objects.select_related('employer', 'talent_request'), pk=pk)
    
    selected_candidate_ids = request.GET.getlist('selected_candidates') or request.POST.getlist('selected_candidates')
    if selected_candidate_ids:
        apps_to_export = Application.objects.filter(job=job, id__in=selected_candidate_ids).select_related('applicant__user', 'job')
    else:
        # Include all evaluated candidates (both qualified and not qualified)
        apps_to_export = Application.objects.filter(job=job).select_related('applicant__user', 'job')

    if not apps_to_export.exists():
        messages.warning(request, f"No candidate applications found to export for '{job.title}'.")
        return redirect('admin_job_candidates', pk=pk)

    excel_buffer, filename = generate_candidates_excel(job, apps_to_export)
    excel_bytes = excel_buffer.getvalue()

    log_audit(
        request,
        'export_candidates_excel',
        f"Admin downloaded candidate evaluation Excel report for '{job.title}' ({apps_to_export.count()} candidates)",
        target_type='job',
        target_id=job.id,
        target_name=job.title
    )

    response = HttpResponse(
        excel_bytes,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
def employer_view_candidate_export(request, export_id):
    """
    Secure Google Drive / Local Candidate Export Viewer:
    Enforces strict Employer Data Isolation.
    Only the designated Employer owning the export or an authorized Admin can view the export.
    """
    export = get_object_or_404(
        CandidateExport.objects.select_related('employer__user', 'job', 'talent_request'),
        pk=export_id
    )

    # Strict Data Isolation Access Control
    if request.user.role == 'employer':
        if not export.employer or export.employer.user != request.user:
            return HttpResponseForbidden("You do not have permission to access this candidate export.")
    elif request.user.role not in ['admin', 'superadmin'] and not request.user.is_staff and not request.user.is_superuser:
        return HttpResponseForbidden("Access denied.")

    # Redirect to Google Drive View Link if present
    if export.google_drive_view_link:
        return redirect(export.google_drive_view_link)
    elif export.excel_file:
        try:
            response = HttpResponse(
                export.excel_file.read(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'inline; filename="{export.filename}"'
            return response
        except Exception:
            pass

    messages.error(request, "Candidate export file is currently unavailable.")
    if request.user.role == 'employer':
        return redirect('employer_dashboard')
    return redirect('admin_job_candidates', pk=export.job.id)


