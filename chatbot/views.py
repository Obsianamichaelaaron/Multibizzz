import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib import messages

from accounts.decorators import applicant_required, role_required
from accounts.models import ApplicantProfile
from jobs.models import JobPosting, Qualification, Skill
from .models import ChatbotAnswer, ChatbotRecommendation
from ml_engine.matcher import calculate_match_score
from audit.utils import log_audit

CAREER_QUESTIONS = [
    {
        'id': 1,
        'category': 'career_interest',
        'question': "What primary field or role are you most passionate about pursuing?",
        'options': [
            {'text': 'Software Engineering & Web Development', 'value': 'tech_software', 'score': 15},
            {'text': 'Data Analysis, AI & Machine Learning', 'value': 'tech_data', 'score': 15},
            {'text': 'UI/UX Design, Visual Arts & Branding', 'value': 'creative_design', 'score': 12},
            {'text': 'Business Administration, Sales & Operations', 'value': 'business_mgmt', 'score': 10},
            {'text': 'Customer Support & Client Services', 'value': 'customer_service', 'score': 8},
        ]
    },
    {
        'id': 2,
        'category': 'technical_skills',
        'question': "Which core tools and technologies do you use most frequently?",
        'options': [
            {'text': 'Python, Django, SQL & REST APIs', 'value': 'python_stack', 'score': 20},
            {'text': 'JavaScript, React, HTML5 & Modern CSS', 'value': 'js_stack', 'score': 18},
            {'text': 'Figma, Adobe Creative Suite & Prototyping', 'value': 'design_tools', 'score': 15},
            {'text': 'Microsoft Excel, Google Analytics & CRM Systems', 'value': 'business_tools', 'score': 12},
            {'text': 'General office software & Communication tools', 'value': 'general_office', 'score': 8},
        ]
    },
    {
        'id': 3,
        'category': 'experience_level',
        'question': "How many years of professional or practical project experience do you have?",
        'options': [
            {'text': '5+ years (Senior / Lead practitioner)', 'value': 'exp_5plus', 'score': 25},
            {'text': '3 - 5 years (Mid-level professional)', 'value': 'exp_3to5', 'score': 20},
            {'text': '1 - 2 years (Junior / Associate level)', 'value': 'exp_1to2', 'score': 14},
            {'text': 'Less than 1 year / Fresh graduate / Transitioning', 'value': 'exp_fresh', 'score': 8},
        ]
    },
    {
        'id': 4,
        'category': 'work_preference',
        'question': "What is your preferred work arrangement and style?",
        'options': [
            {'text': 'Fully Remote / Autonomous deep work', 'value': 'remote_auto', 'score': 15},
            {'text': 'Hybrid / Collaborative team setting', 'value': 'hybrid_collab', 'score': 15},
            {'text': 'On-site / Direct client or team interaction', 'value': 'onsite_interact', 'score': 12},
        ]
    },
    {
        'id': 5,
        'category': 'growth_goal',
        'question': "What is your highest career priority over the next 12 months?",
        'options': [
            {'text': 'Mastering high-demand technical capabilities', 'value': 'skill_mastery', 'score': 15},
            {'text': 'Advancing to leadership or team management', 'value': 'leadership', 'score': 15},
            {'text': 'Securing a high-impact, competitive compensation role', 'value': 'high_comp', 'score': 12},
            {'text': 'Gaining practical hands-on experience in a top company', 'value': 'industry_exp', 'score': 12},
        ]
    }
]

@applicant_required
def chatbot_view(request):
    """Interactive Career Assessment Chatbot UI."""
    profile, _ = ApplicantProfile.objects.get_or_create(user=request.user)
    past_recommendations = ChatbotRecommendation.objects.filter(applicant=profile).select_related('job', 'qualification')[:6]

    return render(request, 'applicant/chatbot.html', {
        'profile': profile,
        'questions_json': json.dumps(CAREER_QUESTIONS),
        'past_recommendations': past_recommendations
    })


@applicant_required
@require_POST
def submit_assessment_ajax(request):
    """AJAX handler for submitting complete chatbot assessment."""
    profile, _ = ApplicantProfile.objects.get_or_create(user=request.user)
    
    try:
        data = json.loads(request.body)
        answers = data.get('answers', [])
        
        total_assessment_score = 0

        # Save answers
        ChatbotAnswer.objects.filter(applicant=profile).delete()
        for ans in answers:
            q_num = ans.get('question_number', 1)
            q_text = ans.get('question_text', '')
            a_text = ans.get('answer_text', '')
            a_val = ans.get('answer_value', '')
            score = ans.get('score_value', 10)
            category = ans.get('category', 'general')

            total_assessment_score += score

            ChatbotAnswer.objects.create(
                applicant=profile,
                question_number=q_num,
                question_text=q_text,
                answer_text=a_text,
                answer_value=a_val,
                category=category,
                score_value=score
            )

        # Update employability score with chatbot bonus
        profile.employability_score = min(98.0, round(float(profile.employability_score) * 0.5 + (total_assessment_score * 0.6), 2))
        profile.save()

        # Generate top matching jobs
        active_jobs = JobPosting.objects.filter(status='active').select_related('employer')
        scored_jobs = []
        for j in active_jobs:
            sc = calculate_match_score(profile, j)
            scored_jobs.append((j, sc))
        
        scored_jobs.sort(key=lambda x: x[1], reverse=True)

        # Save recommendations
        ChatbotRecommendation.objects.filter(applicant=profile).delete()
        recommendations_output = []

        for job_item, sc in scored_jobs[:4]:
            rec = ChatbotRecommendation.objects.create(
                applicant=profile,
                job=job_item,
                recommendation_type='job',
                recommendation_text=f"High match ({sc}%) for {job_item.title} based on your technical profile and work preferences.",
                match_score=sc
            )
            recommendations_output.append({
                'job_id': job_item.id,
                'title': job_item.title,
                'company': job_item.company_name,
                'match_score': sc,
                'location': job_item.location,
                'type': job_item.get_employment_type_display()
            })

        log_audit(
            request,
            'chatbot_assessment',
            f"Applicant {request.user.full_name} completed AI Career Assessment (Score: {total_assessment_score})",
            target_type='assessment',
            target_id=profile.id,
            target_name='Career Assessment'
        )

        return JsonResponse({
            'success': True,
            'message': 'Assessment processed successfully!',
            'employability_score': float(profile.employability_score),
            'recommendations': recommendations_output
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@role_required('admin', 'employer')
def chatbot_review(request):
    """Review candidates chatbot assessment results."""
    answers = ChatbotAnswer.objects.select_related('applicant__user').all().order_by('-created_at')[:100]
    recommendations = ChatbotRecommendation.objects.select_related('applicant__user', 'job').all()[:100]

    return render(request, 'chatbot/review.html', {
        'answers': answers,
        'recommendations': recommendations
    })
