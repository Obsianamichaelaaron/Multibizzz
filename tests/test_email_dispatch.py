from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.core import mail
from accounts.models import User, EmployerProfile, ApplicantProfile
from jobs.models import JobPosting
from applications.models import Application
from messaging.models import Message
from messaging.notifications import (
    send_application_not_qualified_email,
    send_application_under_review_email,
    send_welcome_email
)


class EmailDispatchNotificationTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Admin
        self.admin = User.objects.create_user(
            email='admin@multibiz.com',
            password='Password123!',
            first_name='Admin',
            last_name='User',
            role='admin'
        )

        # Employer
        self.employer_user = User.objects.create_user(
            email='employer@techcorp.com',
            password='Password123!',
            first_name='Tech',
            last_name='Recruiter',
            role='employer'
        )
        self.employer_profile = EmployerProfile.objects.create(
            user=self.employer_user,
            company_name='TechCorp Inc.'
        )

        # Job
        self.job = JobPosting.objects.create(
            employer=self.employer_profile,
            title='Senior Backend Engineer',
            skills_required='Python, Django, PostgreSQL, Redis',
            min_experience_years=3,
            status='active'
        )

        # Non-qualified applicant
        self.unqualified_user = User.objects.create_user(
            email='unqualified@test.com',
            password='Password123!',
            first_name='Bob',
            last_name='Novice',
            role='applicant'
        )
        self.unqualified_profile = ApplicantProfile.objects.create(
            user=self.unqualified_user,
            skills='Photoshop, Design',
            experience_years=0,
            education_level='High School'
        )

        # Qualified applicant
        self.qualified_user = User.objects.create_user(
            email='qualified@test.com',
            password='Password123!',
            first_name='Alice',
            last_name='Expert',
            role='applicant'
        )
        self.qualified_profile = ApplicantProfile.objects.create(
            user=self.qualified_user,
            skills='Python, Django, PostgreSQL, Redis',
            experience_years=5,
            education_level="Bachelor's Degree in Computer Science"
        )

    def test_send_application_not_qualified_email_direct(self):
        """Test sending not-qualified email directly with alternative jobs."""
        mail.outbox.clear()
        app = Application.objects.create(
            job=self.job,
            applicant=self.unqualified_profile,
            qualification_status='not_qualified',
            match_score=25.0,
            qualification_reason='Matched 0 of 4 required technical competencies'
        )

        sent = send_application_not_qualified_email(None, app)
        self.assertTrue(sent)
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertIn('Update on your application', email.subject)
        self.assertEqual(email.to, ['unqualified@test.com'])
        self.assertIn('Bob', email.body)

    def test_send_application_under_review_email_direct(self):
        """Test sending under-review email directly."""
        mail.outbox.clear()
        app = Application.objects.create(
            job=self.job,
            applicant=self.qualified_profile,
            qualification_status='qualified',
            match_score=95.0,
            qualification_reason='All skills matched'
        )

        sent = send_application_under_review_email(None, app)
        self.assertTrue(sent)
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertIn('is under review', email.subject)
        self.assertEqual(email.to, ['qualified@test.com'])

    def test_admin_dispatch_notice_single_applicant(self):
        """Test admin clicking 'Dispatch Notice' for a non-qualified applicant."""
        mail.outbox.clear()
        app = Application.objects.create(
            job=self.job,
            applicant=self.unqualified_profile,
            qualification_status='not_qualified',
            match_score=25.0
        )

        self.client.force_login(self.admin)
        res = self.client.post(reverse('admin_notify_single_applicant', args=[app.id]))
        self.assertEqual(res.status_code, 302)

        app.refresh_from_db()
        self.assertTrue(app.notification_sent)
        self.assertIsNotNone(app.notification_sent_at)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['unqualified@test.com'])

    def test_chat_message_sends_email_to_recipient(self):
        """Sending an in-app message also notifies the recipient by email."""
        mail.outbox.clear()
        self.client.force_login(self.employer_user)

        response = self.client.post(reverse('send_message_ajax'), {
            'recipient_id': self.qualified_user.id,
            'message': 'We would like to discuss your application.'
        })

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.assertTrue(Message.objects.filter(
            sender=self.employer_user,
            receiver=self.qualified_user,
            message='We would like to discuss your application.'
        ).exists())
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['qualified@test.com'])
        self.assertIn('New message from', mail.outbox[0].subject)
        self.assertIn('We would like to discuss your application.', mail.outbox[0].body)
