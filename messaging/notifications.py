import os
import re
import logging
import urllib.request
import urllib.parse
import json

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import escape, strip_tags

from .models import Notification
from audit.utils import log_audit

logger = logging.getLogger('multibiz.notifications')


def get_site_url(request=None):
    """Safely computes the base URL for emails and SMS links."""
    if request:
        try:
            return request.build_absolute_uri('/')
        except Exception:
            pass
    return getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000/')


def send_new_message_email(request, message):
    """Notify the recipient by email when a new direct message is sent."""
    recipient = message.receiver
    sender = message.sender
    if not recipient.email:
        return False

    site_url = get_site_url(request).rstrip('/')
    chat_url = f'{site_url}/messaging/chat/{sender.id}/'
    sender_name = sender.full_name or sender.email
    subject = f'New message from {sender_name} on Multibiz'
    text_content = (
        f'Hi {recipient.first_name or recipient.email},\n\n'
        f'{sender_name} sent you a message on Multibiz:\n\n'
        f'{message.message}\n\n'
        f'Open your conversation: {chat_url}'
    )
    html_content = (
        f'<p>Hi {escape(recipient.first_name or recipient.email)},</p>'
        f'<p><strong>{escape(sender_name)}</strong> sent you a message on Multibiz:</p>'
        f'<blockquote>{escape(message.message)}</blockquote>'
        f'<p><a href="{escape(chat_url)}">Open your conversation</a></p>'
    )
    from_email = getattr(
        settings,
        'DEFAULT_FROM_EMAIL',
        getattr(settings, 'EMAIL_HOST_USER', 'no-reply@multibiz.com')
    )

    try:
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email,
            to=[recipient.email]
        )
        email.attach_alternative(html_content, 'text/html')
        email.send(fail_silently=False)
        logger.info('[Email] New message notification sent to %s', recipient.email)
        return True
    except Exception as error:
        logger.error('[Email] Failed to send new message notification to %s: %s', recipient.email, error)
        return False


def send_welcome_email(request, user):
    """
    Renders and sends a Jobstreet-style HTML welcome email with plain-text fallback.
    """
    site_url = get_site_url(request)
    company_name = ""
    if user.is_employer:
        company_profile = getattr(user, 'employer_profile', None)
        company_name = company_profile.display_name if company_profile else f"{user.first_name}'s Enterprise"

    context = {
        'user': user,
        'site_url': site_url,
        'company_name': company_name,
    }

    if user.is_employer:
        subject = f"Welcome to Multibiz Talent Solutions, {user.first_name}!"
        template_html = 'emails/welcome_employer.html'
        template_txt = 'emails/welcome_employer.txt'
    else:
        subject = f"Welcome to Multibiz, {user.first_name} — It's great to have you on board!"
        template_html = 'emails/welcome_applicant.html'
        template_txt = 'emails/welcome_applicant.txt'

    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', getattr(settings, 'EMAIL_HOST_USER', 'no-reply@multibiz.com'))

    try:
        html_content = render_to_string(template_html, context)
        text_content = render_to_string(template_txt, context)
    except Exception as e:
        logger.warning(f"Error rendering welcome email template: {e}")
        text_content = f"Welcome to Multibiz, {user.first_name}! Log in to your portal at {site_url}"
        html_content = f"<p>Welcome to Multibiz, <strong>{user.first_name}</strong>!</p><p><a href='{site_url}'>Log In to Portal</a></p>"

    try:
        bcc_list = []
        admin_email = getattr(settings, 'EMAIL_HOST_USER', '')
        if admin_email and admin_email.lower() != user.email.lower():
            bcc_list.append(admin_email)

        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email,
            to=[user.email],
            bcc=bcc_list if bcc_list else None
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=False)

        # Audit trail logging
        log_audit(
            request,
            'email_sent',
            f"Welcome email dispatched to {user.email} ({user.role.title()})",
            target_type='user',
            target_id=user.id,
            target_name=user.full_name,
            user=user
        )
        logger.info(f"[Email] Welcome email sent successfully to {user.email} (BCC: {bcc_list})")
        return True
    except Exception as e:
        logger.error(f"[Email] Failed to send welcome email to {user.email}: {e}")
        # Audit fail record
        log_audit(
            request,
            'email_failed',
            f"Welcome email dispatch queued/simulated for {user.email} ({e})",
            target_type='user',
            target_id=user.id,
            target_name=user.full_name,
            user=user
        )
        return False


def format_phone_number(raw_phone):
    """
    Cleans and standardizes raw phone numbers for SMS transmission.
    E.g. converts '09171234567' to '+639171234567' or standard international.
    """
    if not raw_phone:
        return ""
    # Remove all non-digit and non-plus characters
    cleaned = re.sub(r'[^\d+]', '', str(raw_phone).strip())
    if cleaned.startswith('09') and len(cleaned) == 11:
        return '+63' + cleaned[1:]
    if cleaned.startswith('639') and len(cleaned) == 12:
        return '+' + cleaned
    if cleaned.startswith('9') and len(cleaned) == 10:
        return '+63' + cleaned
    return cleaned


def send_welcome_sms(request, user):
    """
    Sends a Jobstreet-style welcome SMS text message to the user's phone number.
    Supports Semaphore API, Twilio, PhilSMS, or Console/Logger simulation.
    """
    raw_phone = getattr(user, 'phone', None)
    if not raw_phone:
        return False

    phone = format_phone_number(raw_phone)
    site_url = get_site_url(request).rstrip('/')

    company_name = ""
    if user.is_employer:
        company_profile = getattr(user, 'employer_profile', None)
        company_name = company_profile.display_name if company_profile else "your company"

    if user.is_employer:
        sms_text = (
            f"[Multibiz] Welcome, {user.first_name}! Your employer account for {company_name} is active. "
            f"Post vacancies & access our AI Candidate Radar at {site_url}/employer/dashboard/"
        )
    else:
        sms_text = (
            f"[Multibiz] Welcome to Multibiz, {user.first_name}! Your account is now active. "
            f"Complete your profile & explore AI-matched jobs at {site_url}/applicant/profile/ (Need help? Reply HELP)"
        )

    # 1. Semaphore SMS Gateway (Popular for Philippines / International)
    semaphore_key = os.environ.get('SEMAPHORE_API_KEY')
    if semaphore_key and (phone.startswith('+63') or phone.startswith('09')):
        try:
            url = "https://semaphore.co/api/v4/messages"
            params = {
                'apikey': semaphore_key,
                'number': phone.replace('+63', '0'),
                'message': sms_text,
                'sendername': 'Multibiz'
            }
            data = urllib.parse.urlencode(params).encode('utf-8')
            req = urllib.request.Request(url, data=data, method='POST')
            with urllib.request.urlopen(req, timeout=5) as response:
                resp_data = json.loads(response.read().decode())
                logger.info(f"[SMS:Semaphore] Dispatched SMS to {phone}: {resp_data}")
        except Exception as e:
            logger.warning(f"[SMS:Semaphore] Gateway error: {e}")

    # 2. PhilSMS Gateway
    philsms_token = os.environ.get('PHILSMS_API_TOKEN')
    if philsms_token:
        try:
            url = "https://app.philsms.com/api/v3/sms/send"
            headers = {
                'Authorization': f'Bearer {philsms_token}',
                'Content-Type': 'application/json'
            }
            payload = json.dumps({
                'recipient': phone,
                'sender_id': 'Multibiz',
                'type': 'plain',
                'message': sms_text
            }).encode('utf-8')
            req = urllib.request.Request(url, data=payload, headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=5) as response:
                logger.info(f"[SMS:PhilSMS] Dispatched SMS to {phone}")
        except Exception as e:
            logger.warning(f"[SMS:PhilSMS] Gateway error: {e}")

    # Log SMS transmission to console & audit trail
    print("\n==========================================================================")
    print("[MULTIBIZ SMS GATEWAY DISPATCH]")
    print(f"To: {phone} ({user.full_name})")
    print(f"Message: {sms_text}")
    print("==========================================================================\n")

    log_audit(
        request,
        'sms_sent',
        f"Welcome text message dispatched to {phone}: '{sms_text[:60]}...'",
        target_type='user',
        target_id=user.id,
        target_name=user.full_name,
        user=user
    )
    return True


def create_welcome_inapp_notification(user):
    """Creates an in-app notification for the newly registered user."""
    if user.is_employer:
        title = "Welcome to Multibiz Talent Solutions!"
        msg = "Your employer account is active. Complete your company details and post your first vacancy to start receiving AI-scored candidate applications."
    else:
        title = "Welcome to Multibiz Intelligence!"
        msg = "Welcome on board! Upload your resume and take the 2-minute AI Career Assessment to calculate your live Employability Score."

    Notification.objects.create(
        user=user,
        title=title,
        message=msg,
        type='system'
    )


def send_all_welcome_notifications(request, user):
    """
    Helper function called immediately after successful user registration
    to dispatch welcome email, welcome SMS, in-app notification, and audit trail.
    """
    # 1. In-App Notification
    try:
        create_welcome_inapp_notification(user)
    except Exception as e:
        logger.warning(f"Error creating in-app notification: {e}")

    # 2. Welcome Email
    email_sent = send_welcome_email(request, user)

    # 3. Welcome SMS Text
    sms_sent = send_welcome_sms(request, user)

    return {
        'email_sent': email_sent,
        'sms_sent': sms_sent
    }


def send_application_under_review_email(request, application):
    """
    Dispatches email notifying applicant: 'Your application is under review.'
    Includes position, company, applied date, and current status.
    """
    user = application.applicant.user
    site_url = get_site_url(request)

    context = {
        'user': user,
        'application': application,
        'job': application.job,
        'site_url': site_url,
    }

    subject = f"Your application for {application.job.title} is under review"
    template_html = 'emails/application_under_review.html'
    template_txt = 'emails/application_under_review.txt'
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', getattr(settings, 'EMAIL_HOST_USER', 'no-reply@multibiz.com'))
    reply_to_list = [settings.EMAIL_HOST_USER] if getattr(settings, 'EMAIL_HOST_USER', None) else None

    try:
        html_content = render_to_string(template_html, context)
        text_content = render_to_string(template_txt, context)
    except Exception as e:
        logger.warning(f"Error rendering application_under_review template: {e}")
        text_content = f"Hello {user.first_name}, your application for {application.job.title} @ {application.job.company_name} is under review."
        html_content = f"<p>Hello {user.first_name}, your application for <strong>{application.job.title}</strong> is under review.</p>"

    try:
        bcc_list = []
        admin_email = getattr(settings, 'EMAIL_HOST_USER', '')
        if admin_email and admin_email.lower() != user.email.lower():
            bcc_list.append(admin_email)

        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email,
            to=[user.email],
            bcc=bcc_list if bcc_list else None,
            reply_to=reply_to_list
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=False)

        log_audit(
            request,
            'email_sent',
            f"Qualified applicant notification sent to {user.email} (BCC: {bcc_list}) for '{application.job.title}'",
            target_type='application',
            target_id=application.id,
            target_name=application.job.title,
            user=user
        )
        logger.info(f"[Email] Application under review email sent to {user.email} (BCC: {bcc_list})")
        return True
    except Exception as e:
        logger.error(f"[Email] Failed to send under review email to {user.email}: {e}")
        log_audit(
            request,
            'email_failed',
            f"Failed to send under review email to {user.email} for '{application.job.title}': {e}",
            target_type='application',
            target_id=application.id,
            target_name=application.job.title,
            user=user
        )
        return False


def send_application_not_qualified_email(request, application, recommended_jobs=None):
    """
    Dispatches email notifying applicant: 'You are not qualified for this position.'
    Includes alternative job recommendations matching the applicant's profile.
    """
    user = application.applicant.user
    site_url = get_site_url(request)

    if recommended_jobs is None:
        from ml_engine.matcher import find_alternative_job_recommendations
        recommended_jobs = find_alternative_job_recommendations(application.applicant, exclude_job_id=application.job.id, limit=3)

    is_under_qualified = (application.qualification_status == 'under_qualified')
    status_display = "Under Qualified" if is_under_qualified else "Not Qualified"

    context = {
        'user': user,
        'application': application,
        'job': application.job,
        'recommended_jobs': recommended_jobs,
        'site_url': site_url,
        'is_under_qualified': is_under_qualified,
        'status_display': status_display,
        'qualification_reason': application.qualification_reason or '',
    }

    subject = f"Update on your application for {application.job.title}"
    template_html = 'emails/application_not_qualified.html'
    template_txt = 'emails/application_not_qualified.txt'
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', getattr(settings, 'EMAIL_HOST_USER', 'no-reply@multibiz.com'))
    reply_to_list = [settings.EMAIL_HOST_USER] if getattr(settings, 'EMAIL_HOST_USER', None) else None

    try:
        html_content = render_to_string(template_html, context)
        text_content = render_to_string(template_txt, context)
    except Exception as e:
        logger.warning(f"Error rendering application_not_qualified template: {e}")
        text_content = f"Hello {user.first_name}, update regarding your application for {application.job.title}: you are not qualified for this position."
        html_content = f"<p>Hello {user.first_name}, update regarding your application for <strong>{application.job.title}</strong>: you are not qualified for this position.</p>"

    try:
        bcc_list = []
        admin_email = getattr(settings, 'EMAIL_HOST_USER', '')
        if admin_email and admin_email.lower() != user.email.lower():
            bcc_list.append(admin_email)

        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email,
            to=[user.email],
            bcc=bcc_list if bcc_list else None,
            reply_to=reply_to_list
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=False)

        log_audit(
            request,
            'email_sent',
            f"Not-qualified notification sent to {user.email} (BCC: {bcc_list}) for '{application.job.title}'",
            target_type='application',
            target_id=application.id,
            target_name=application.job.title,
            user=user
        )
        logger.info(f"[Email] Not qualified email sent to {user.email} (BCC: {bcc_list})")
        return True
    except Exception as e:
        logger.error(f"[Email] Failed to send not-qualified email to {user.email}: {e}")
        log_audit(
            request,
            'email_failed',
            f"Failed to send not-qualified email to {user.email} for '{application.job.title}': {e}",
            target_type='application',
            target_id=application.id,
            target_name=application.job.title,
            user=user
        )
        return False


def send_candidates_sent_to_employer_email(request, employer_request, candidate_count):
    """
    Dispatches email to employer notifying that qualified candidates have been sent to Talent Radar.
    """
    employer_user = employer_request.employer.user
    site_url = get_site_url(request)

    context = {
        'employer_name': employer_request.employer.display_name,
        'employer_request': employer_request,
        'candidate_count': candidate_count,
        'site_url': site_url,
    }

    subject = f"Qualified Candidates Ready for Review — {employer_request.title}"
    template_html = 'emails/candidates_sent_to_employer.html'
    template_txt = 'emails/candidates_sent_to_employer.txt'
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', getattr(settings, 'EMAIL_HOST_USER', 'no-reply@multibiz.com'))
    reply_to_list = [settings.EMAIL_HOST_USER] if getattr(settings, 'EMAIL_HOST_USER', None) else None

    try:
        html_content = render_to_string(template_html, context)
        text_content = render_to_string(template_txt, context)
    except Exception as e:
        logger.warning(f"Error rendering candidates_sent_to_employer template: {e}")
        text_content = f"Hello {employer_request.employer.display_name}, {candidate_count} qualified candidates are ready for review for {employer_request.title}."
        html_content = f"<p>Hello <strong>{employer_request.employer.display_name}</strong>, {candidate_count} qualified candidates are ready for review on Talent Radar.</p>"

    try:
        bcc_list = []
        admin_email = getattr(settings, 'EMAIL_HOST_USER', '')
        if admin_email and admin_email.lower() != employer_user.email.lower():
            bcc_list.append(admin_email)

        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email,
            to=[employer_user.email],
            bcc=bcc_list if bcc_list else None,
            reply_to=reply_to_list
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=False)

        log_audit(
            request,
            'email_sent',
            f"Qualified candidates notification ({candidate_count} candidates) sent to {employer_user.email} (BCC: {bcc_list}) for '{employer_request.title}'",
            target_type='talent_request',
            target_id=employer_request.id,
            target_name=employer_request.title,
            user=employer_user
        )
        logger.info(f"[Email] Qualified candidates sent email delivered to {employer_user.email} (BCC: {bcc_list})")
        return True
    except Exception as e:
        logger.error(f"[Email] Failed to send candidates ready email to {employer_user.email}: {e}")
        log_audit(
            request,
            'email_failed',
            f"Failed to send candidates ready email to {employer_user.email} for '{employer_request.title}': {e}",
            target_type='talent_request',
            target_id=employer_request.id,
            target_name=employer_request.title,
            user=employer_user
        )
        return False


def send_employer_request_status_email(request, employer_request):
    """
    Dispatches email alerting employer of request status updates.
    """
    employer_user = employer_request.employer.user
    site_url = get_site_url(request)

    context = {
        'employer_name': employer_request.employer.display_name,
        'employer_request': employer_request,
        'site_url': site_url,
    }

    subject = f"Hiring Request Update: {employer_request.title} (#{employer_request.id})"
    template_html = 'emails/employer_request_status.html'
    template_txt = 'emails/employer_request_status.txt'
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', getattr(settings, 'EMAIL_HOST_USER', 'no-reply@multibiz.com'))
    reply_to_list = [settings.EMAIL_HOST_USER] if getattr(settings, 'EMAIL_HOST_USER', None) else None

    try:
        html_content = render_to_string(template_html, context)
        text_content = render_to_string(template_txt, context)
    except Exception as e:
        logger.warning(f"Error rendering employer_request_status template: {e}")
        text_content = f"Hello {employer_request.employer.display_name}, status for request '{employer_request.title}' is now {employer_request.get_status_display()}."
        html_content = f"<p>Status for request '{employer_request.title}' is now {employer_request.get_status_display()}.</p>"

    try:
        bcc_list = []
        admin_email = getattr(settings, 'EMAIL_HOST_USER', '')
        if admin_email and admin_email.lower() != employer_user.email.lower():
            bcc_list.append(admin_email)

        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email,
            to=[employer_user.email],
            bcc=bcc_list if bcc_list else None,
            reply_to=reply_to_list
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=False)

        log_audit(
            request,
            'email_sent',
            f"Talent request status update email sent to {employer_user.email} (BCC: {bcc_list}) for '{employer_request.title}' ({employer_request.get_status_display()})",
            target_type='talent_request',
            target_id=employer_request.id,
            target_name=employer_request.title,
            user=employer_user
        )
        return True
    except Exception as e:
        logger.error(f"[Email] Failed to send request status update email to {employer_user.email}: {e}")
        log_audit(
            request,
            'email_failed',
            f"Failed to send request status update email to {employer_user.email} for '{employer_request.title}': {e}",
            target_type='talent_request',
            target_id=employer_request.id,
            target_name=employer_request.title,
            user=employer_user
        )
        return False
