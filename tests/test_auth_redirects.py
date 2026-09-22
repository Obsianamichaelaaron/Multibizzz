from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User, ApplicantProfile, EmployerProfile

class AuthRedirectsTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Admin user
        self.admin_user = User.objects.create_user(
            email='admin@test.com',
            password='Password123!',
            first_name='Admin',
            last_name='User',
            role='admin'
        )

        # Employer user
        self.employer_user = User.objects.create_user(
            email='employer@test.com',
            password='Password123!',
            first_name='Employer',
            last_name='User',
            role='employer'
        )
        self.employer_profile = EmployerProfile.objects.create(
            user=self.employer_user,
            company_name='Test Company'
        )

        # Applicant user
        self.applicant_user = User.objects.create_user(
            email='applicant@test.com',
            password='Password123!',
            first_name='Applicant',
            last_name='User',
            role='applicant'
        )
        self.applicant_profile = ApplicantProfile.objects.create(
            user=self.applicant_user
        )

    def test_authenticated_applicant_login_redirect_to_careers(self):
        """Logged in applicant visiting /accounts/login/ is redirected directly to careers."""
        self.client.force_login(self.applicant_user)
        response = self.client.get(reverse('login'))
        self.assertRedirects(response, reverse('careers'), target_status_code=200)

    def test_authenticated_applicant_register_redirect_to_careers(self):
        """Logged in applicant visiting /accounts/register/ is redirected directly to careers."""
        self.client.force_login(self.applicant_user)
        response = self.client.get(reverse('register'))
        self.assertRedirects(response, reverse('careers'), target_status_code=200)

    def test_authenticated_applicant_dashboard_router_redirect_to_careers(self):
        """Logged in applicant visiting /accounts/dashboard/ is redirected directly to careers."""
        self.client.force_login(self.applicant_user)
        response = self.client.get(reverse('dashboard_router'))
        self.assertRedirects(response, reverse('careers'), target_status_code=200)

    def test_applicant_post_login_redirects_to_careers(self):
        """Applicant submitting login credentials is redirected directly to careers."""
        response = self.client.post(reverse('login'), {
            'email': 'applicant@test.com',
            'password': 'Password123!'
        })
        self.assertRedirects(response, reverse('careers'), target_status_code=200)

    def test_authenticated_employer_login_redirect_to_employer_dashboard(self):
        """Logged in employer visiting /accounts/login/ is redirected to employer dashboard."""
        self.client.force_login(self.employer_user)
        response = self.client.get(reverse('login'))
        self.assertRedirects(response, reverse('employer_dashboard'), target_status_code=200)

    def test_authenticated_employer_register_redirect_to_employer_dashboard(self):
        """Logged in employer visiting /accounts/register/ is redirected to employer dashboard."""
        self.client.force_login(self.employer_user)
        response = self.client.get(reverse('register'))
        self.assertRedirects(response, reverse('employer_dashboard'), target_status_code=200)

    def test_authenticated_employer_dashboard_router_redirect_to_employer_dashboard(self):
        """Logged in employer visiting /accounts/dashboard/ is redirected to employer dashboard."""
        self.client.force_login(self.employer_user)
        response = self.client.get(reverse('dashboard_router'))
        self.assertRedirects(response, reverse('employer_dashboard'), target_status_code=200)

    def test_employer_post_login_redirects_to_employer_dashboard(self):
        """Employer submitting login credentials is redirected to employer dashboard."""
        response = self.client.post(reverse('login'), {
            'email': 'employer@test.com',
            'password': 'Password123!'
        })
        self.assertRedirects(response, reverse('employer_dashboard'), target_status_code=200)

    def test_authenticated_admin_login_redirect_to_admin_dashboard(self):
        """Logged in admin visiting /accounts/login/ is redirected to admin dashboard."""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('login'))
        self.assertRedirects(response, reverse('admin_dashboard'), target_status_code=200)

    def test_authenticated_admin_register_redirect_to_admin_dashboard(self):
        """Logged in admin visiting /accounts/register/ is redirected to admin dashboard."""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('register'))
        self.assertRedirects(response, reverse('admin_dashboard'), target_status_code=200)

    def test_authenticated_admin_dashboard_router_redirect_to_admin_dashboard(self):
        """Logged in admin visiting /accounts/dashboard/ is redirected to admin dashboard."""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('dashboard_router'))
        self.assertRedirects(response, reverse('admin_dashboard'), target_status_code=200)

    def test_admin_post_login_redirects_to_admin_dashboard(self):
        """Admin submitting login credentials is redirected to admin dashboard."""
        response = self.client.post(reverse('login'), {
            'email': 'admin@test.com',
            'password': 'Password123!'
        })
        self.assertRedirects(response, reverse('admin_dashboard'), target_status_code=200)
