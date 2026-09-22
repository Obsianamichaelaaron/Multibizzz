import datetime
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from accounts.models import User, EmployerProfile, ApplicantProfile
from jobs.models import JobPosting, EmployerRequest
from applications.models import Application
from audit.models import AuditTrail
from audit.utils import log_audit

class AllFiltersComprehensiveTests(TestCase):
    def setUp(self):
        self.client = Client()

        # 1. Users
        self.admin_user = User.objects.create_user(
            email='admin@multibiz.com',
            password='Password123!',
            first_name='Admin',
            last_name='Supervisor',
            role='admin',
            status='active'
        )
        self.inactive_user = User.objects.create_user(
            email='inactive@user.com',
            password='Password123!',
            first_name='Inactive',
            last_name='Member',
            role='applicant',
            status='inactive'
        )

        self.employer_user = User.objects.create_user(
            email='employer@techcorp.com',
            password='Password123!',
            first_name='John',
            last_name='Recruiter',
            role='employer',
            status='active'
        )
        self.employer_profile, _ = EmployerProfile.objects.get_or_create(user=self.employer_user)
        self.employer_profile.company_name = 'TechCorp Solutions'
        self.employer_profile.save()

        self.applicant1 = User.objects.create_user(
            email='alice@python.com',
            password='Password123!',
            first_name='Alice',
            last_name='Dev',
            role='applicant',
            status='active'
        )
        self.applicant1_profile, _ = ApplicantProfile.objects.get_or_create(user=self.applicant1)
        self.applicant1_profile.skills = 'Python, Django, PostgreSQL, Docker'
        self.applicant1_profile.experience_years = 5
        self.applicant1_profile.education_level = "Master's Degree"
        self.applicant1_profile.save()

        self.applicant2 = User.objects.create_user(
            email='bob@design.com',
            password='Password123!',
            first_name='Bob',
            last_name='Artist',
            role='applicant',
            status='active'
        )
        self.applicant2_profile, _ = ApplicantProfile.objects.get_or_create(user=self.applicant2)
        self.applicant2_profile.skills = 'Photoshop, Figma, UI/UX'
        self.applicant2_profile.experience_years = 2
        self.applicant2_profile.save()

        # 2. Job Postings
        self.job1 = JobPosting.objects.create(
            title='Senior Backend Engineer',
            employer=self.employer_profile,
            location='Manila / Remote',
            employment_type='full-time',
            skills_required='Python, Django, PostgreSQL',
            min_experience_years=3,
            description='Build Python APIs and services',
            status='active'
        )
        self.job2 = JobPosting.objects.create(
            title='UI/UX Product Designer',
            employer=self.employer_profile,
            location='Cebu City',
            employment_type='contract',
            skills_required='Figma, Photoshop, Wireframing',
            min_experience_years=2,
            description='Design UI mockups and prototypes',
            status='active'
        )
        self.job3_draft = JobPosting.objects.create(
            title='Draft Internship Role',
            employer=self.employer_profile,
            location='Remote',
            employment_type='internship',
            skills_required='Basic Programming',
            description='Draft position',
            status='draft'
        )

        # 3. Employer Requests
        self.req1 = EmployerRequest.objects.create(
            employer=self.employer_profile,
            title='DevOps Cloud Specialist',
            skills_required='AWS, Kubernetes, Terraform',
            experience_required='4+ years',
            vacancies_count=2,
            location='BGC Taguig',
            employment_type='full-time',
            status='submitted'
        )
        self.req2 = EmployerRequest.objects.create(
            employer=self.employer_profile,
            title='Mobile Flutter Developer',
            skills_required='Flutter, Dart, Mobile SDK',
            experience_required='2+ years',
            vacancies_count=1,
            location='Remote',
            employment_type='full-time',
            status='job_posted'
        )

        # 4. Applications
        self.app1 = Application.objects.create(
            job=self.job1,
            applicant=self.applicant1_profile,
            status='shortlisted',
            qualification_status='qualified',
            qualification_reason='Full stack skills match',
            match_score=92.0,
            skills_match_score=95.0,
            exp_match_score=90.0,
            edu_match_score=90.0,
            sent_to_employer=True,
            employer_decision='shortlisted'
        )
        self.app2 = Application.objects.create(
            job=self.job1,
            applicant=self.applicant2_profile,
            status='not_qualified',
            qualification_status='not_qualified',
            qualification_reason='Lacks required Python & backend tech',
            match_score=25.0,
            skills_match_score=10.0,
            exp_match_score=40.0,
            edu_match_score=30.0,
            sent_to_employer=False,
            employer_decision='none'
        )

        # 5. Audit Trail Logs
        AuditTrail.objects.create(
            admin_name='Admin Supervisor',
            action_type='approve_talent_request',
            action_description='Admin approved hiring request for DevOps',
            target_type='talent_request',
            target_id=self.req1.id,
            target_name=self.req1.title,
            ip_address='192.168.1.50'
        )
        AuditTrail.objects.create(
            admin_name='Admin Supervisor',
            action_type='delete_user',
            action_description='Admin deleted suspicious account',
            target_type='user',
            target_id=999,
            target_name='spammer@test.com',
            ip_address='10.0.0.1'
        )

    # -------------------------------------------------------------
    # 1. PUBLIC CAREERS DIRECTORY FILTERS
    # -------------------------------------------------------------
    def test_public_careers_filters(self):
        url = reverse('careers')

        # No filter: shows active jobs only (job1, job2), not draft (job3_draft)
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Senior Backend Engineer')
        self.assertContains(res, 'UI/UX Product Designer')
        self.assertNotContains(res, 'Draft Internship Role')

        # Search query 'Backend'
        res_q = self.client.get(url, {'q': 'Backend'})
        self.assertEqual(res_q.status_code, 200)
        self.assertContains(res_q, 'Senior Backend Engineer')
        self.assertNotContains(res_q, 'UI/UX Product Designer')

        # Employment type 'contract'
        res_type = self.client.get(url, {'type': 'contract'})
        self.assertEqual(res_type.status_code, 200)
        self.assertContains(res_type, 'UI/UX Product Designer')
        self.assertNotContains(res_type, 'Senior Backend Engineer')

        # Location 'Cebu'
        res_loc = self.client.get(url, {'location': 'Cebu'})
        self.assertEqual(res_loc.status_code, 200)
        self.assertContains(res_loc, 'UI/UX Product Designer')
        self.assertNotContains(res_loc, 'Senior Backend Engineer')

        # Combined filter matching 0 items
        res_none = self.client.get(url, {'q': 'Backend', 'location': 'Cebu'})
        self.assertEqual(res_none.status_code, 200)
        self.assertEqual(res_none.context['total_count'], 0)

    # -------------------------------------------------------------
    # 2. APPLICANT JOBS DIRECTORY FILTERS
    # -------------------------------------------------------------
    def test_applicant_jobs_filters(self):
        self.client.login(email='alice@python.com', password='Password123!')
        url = reverse('applicant_jobs')

        # No filter
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        scored_jobs = res.context['scored_jobs']
        self.assertEqual(len(scored_jobs), 2)

        # Filter by min_match = 80 (Alice has high match with Backend, low with UI/UX)
        res_match = self.client.get(url, {'min_match': '80'})
        self.assertEqual(res_match.status_code, 200)
        filtered_scores = res_match.context['scored_jobs']
        for sj in filtered_scores:
            self.assertGreaterEqual(sj['match_score'], 80)

        # Filter by keyword 'Designer'
        res_kw = self.client.get(url, {'q': 'Designer'})
        self.assertEqual(res_kw.status_code, 200)
        self.assertEqual(len(res_kw.context['scored_jobs']), 1)
        self.assertEqual(res_kw.context['scored_jobs'][0]['job'].title, 'UI/UX Product Designer')

        # Invalid min_match value (gracefully handled)
        res_invalid = self.client.get(url, {'min_match': 'not_a_number'})
        self.assertEqual(res_invalid.status_code, 200)

    # -------------------------------------------------------------
    # 3. EMPLOYER TALENT REQUESTS FILTERS
    # -------------------------------------------------------------
    def test_employer_talent_requests_filters(self):
        self.client.login(email='employer@techcorp.com', password='Password123!')
        url = reverse('employer_talent_requests')

        # All requests
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'DevOps Cloud Specialist')
        self.assertContains(res, 'Mobile Flutter Developer')

        # Filter by status 'submitted'
        res_sub = self.client.get(url, {'status': 'submitted'})
        self.assertEqual(res_sub.status_code, 200)
        self.assertContains(res_sub, 'DevOps Cloud Specialist')
        self.assertNotContains(res_sub, 'Mobile Flutter Developer')

        # Filter by keyword 'Flutter'
        res_q = self.client.get(url, {'q': 'Flutter'})
        self.assertEqual(res_q.status_code, 200)
        self.assertContains(res_q, 'Mobile Flutter Developer')
        self.assertNotContains(res_q, 'DevOps Cloud Specialist')

    # -------------------------------------------------------------
    # 4. EMPLOYER CANDIDATE PIPELINE FILTERS
    # -------------------------------------------------------------
    def test_employer_candidates_filters(self):
        self.client.login(email='employer@techcorp.com', password='Password123!')
        url = reverse('employer_candidates')

        # All sent candidates (only app1 is sent_to_employer=True)
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Alice Dev')
        self.assertNotContains(res, 'Bob Artist')

        # Filter by status 'shortlisted'
        res_sl = self.client.get(url, {'status': 'shortlisted'})
        self.assertEqual(res_sl.status_code, 200)
        self.assertEqual(len(res_sl.context['candidates_data']), 1)

        # Filter by status 'rejected' (should return 0)
        res_rej = self.client.get(url, {'status': 'rejected'})
        self.assertEqual(res_rej.status_code, 200)
        self.assertEqual(len(res_rej.context['candidates_data']), 0)

        # Filter by category 'excellent' (Alice score >= 85)
        res_cat = self.client.get(url, {'category': 'excellent'})
        self.assertEqual(res_cat.status_code, 200)
        self.assertEqual(len(res_cat.context['candidates_data']), 1)

        # Filter by category 'poor' (Alice is 92%, should not match)
        res_cat_poor = self.client.get(url, {'category': 'poor'})
        self.assertEqual(res_cat_poor.status_code, 200)
        self.assertEqual(len(res_cat_poor.context['candidates_data']), 0)

        # Search query by candidate name 'Alice'
        res_q = self.client.get(url, {'q': 'Alice'})
        self.assertEqual(res_q.status_code, 200)
        self.assertEqual(len(res_q.context['candidates_data']), 1)

        # Search query non-existent 'Charlie'
        res_none = self.client.get(url, {'q': 'Charlie'})
        self.assertEqual(res_none.status_code, 200)
        self.assertEqual(len(res_none.context['candidates_data']), 0)

    # -------------------------------------------------------------
    # 5. EMPLOYER TALENT RADAR JOB SELECTOR FILTER
    # -------------------------------------------------------------
    def test_employer_talent_radar_filters(self):
        self.client.login(email='employer@techcorp.com', password='Password123!')
        url = reverse('recommended_candidates')

        # Default view (first active job selected)
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertIsNotNone(res.context['selected_job'])

        # Explicit job_id selector
        res_job2 = self.client.get(url, {'job_id': self.job2.id})
        self.assertEqual(res_job2.status_code, 200)
        self.assertEqual(res_job2.context['selected_job'].id, self.job2.id)

    # -------------------------------------------------------------
    # 6. ADMIN JOBS OVERSIGHT FILTERS
    # -------------------------------------------------------------
    def test_admin_jobs_filters(self):
        self.client.login(email='admin@multibiz.com', password='Password123!')
        url = reverse('admin_jobs')

        # All jobs (active + draft)
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Senior Backend Engineer')
        self.assertContains(res, 'Draft Internship Role')

        # Filter by status 'draft'
        res_draft = self.client.get(url, {'status': 'draft'})
        self.assertEqual(res_draft.status_code, 200)
        self.assertContains(res_draft, 'Draft Internship Role')
        self.assertNotContains(res_draft, 'Senior Backend Engineer')

        # Search query 'Backend'
        res_q = self.client.get(url, {'q': 'Backend'})
        self.assertEqual(res_q.status_code, 200)
        self.assertContains(res_q, 'Senior Backend Engineer')
        self.assertNotContains(res_q, 'Draft Internship Role')

    # -------------------------------------------------------------
    # 7. ADMIN EMPLOYER REQUESTS FILTERS
    # -------------------------------------------------------------
    def test_admin_employer_requests_filters(self):
        self.client.login(email='admin@multibiz.com', password='Password123!')
        url = reverse('admin_employer_requests')

        # All requests
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context['status_counts']['submitted'], 1)
        self.assertEqual(res.context['status_counts']['job_posted'], 1)

        # Filter by status 'submitted'
        res_sub = self.client.get(url, {'status': 'submitted'})
        self.assertEqual(res_sub.status_code, 200)
        self.assertContains(res_sub, 'DevOps Cloud Specialist')
        self.assertNotContains(res_sub, 'Mobile Flutter Developer')

        # Search by keyword 'DevOps'
        res_q = self.client.get(url, {'q': 'DevOps'})
        self.assertEqual(res_q.status_code, 200)
        self.assertContains(res_q, 'DevOps Cloud Specialist')
        self.assertNotContains(res_q, 'Mobile Flutter Developer')

    # -------------------------------------------------------------
    # 8. ADMIN JOB CANDIDATES FILTERS & COUNTS
    # -------------------------------------------------------------
    def test_admin_job_candidates_filters(self):
        self.client.login(email='admin@multibiz.com', password='Password123!')
        url = reverse('admin_job_candidates', kwargs={'pk': self.job1.id})

        # All applicants for job1 (Alice + Bob)
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context['counts']['all'], 2)
        self.assertEqual(res.context['counts']['qualified'], 1)
        self.assertEqual(res.context['counts']['not_qualified'], 1)
        self.assertEqual(len(res.context['candidates']), 2)

        # Filter qual='qualified'
        res_qual = self.client.get(url, {'qual': 'qualified'})
        self.assertEqual(res_qual.status_code, 200)
        self.assertEqual(len(res_qual.context['candidates']), 1)
        self.assertEqual(res_qual.context['candidates'][0]['applicant'].user.first_name, 'Alice')

        # Filter qual='not_qualified'
        res_unqual = self.client.get(url, {'qual': 'not_qualified'})
        self.assertEqual(res_unqual.status_code, 200)
        self.assertEqual(len(res_unqual.context['candidates']), 1)
        self.assertEqual(res_unqual.context['candidates'][0]['applicant'].user.first_name, 'Bob')

        # Filter status='sent'
        res_sent = self.client.get(url, {'status': 'sent'})
        self.assertEqual(res_sent.status_code, 200)
        self.assertEqual(len(res_sent.context['candidates']), 1)
        self.assertTrue(res_sent.context['candidates'][0]['sent_to_employer'])

        # Sort by 'lowest'
        res_sort = self.client.get(url, {'sort': 'lowest'})
        self.assertEqual(res_sort.status_code, 200)
        self.assertEqual(res_sort.context['candidates'][0]['applicant'].user.first_name, 'Bob')

        # Search 'Alice'
        res_q = self.client.get(url, {'q': 'Alice'})
        self.assertEqual(res_q.status_code, 200)
        self.assertEqual(len(res_q.context['candidates']), 1)

    # -------------------------------------------------------------
    # 9. ADMIN USERS MANAGER FILTERS
    # -------------------------------------------------------------
    def test_admin_users_filters(self):
        self.client.login(email='admin@multibiz.com', password='Password123!')
        url = reverse('admin_users')

        # All users
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)

        # Filter role='employer'
        res_emp = self.client.get(url, {'role': 'employer'})
        self.assertEqual(res_emp.status_code, 200)
        self.assertIn(self.employer_user, res_emp.context['users'])
        self.assertNotIn(self.applicant1, res_emp.context['users'])

        # Filter status='inactive'
        res_inact = self.client.get(url, {'status': 'inactive'})
        self.assertEqual(res_inact.status_code, 200)
        self.assertIn(self.inactive_user, res_inact.context['users'])
        self.assertNotIn(self.admin_user, res_inact.context['users'])

        # Search by email 'alice'
        res_q = self.client.get(url, {'q': 'alice@python.com'})
        self.assertEqual(res_q.status_code, 200)
        self.assertIn(self.applicant1, res_q.context['users'])
        self.assertNotIn(self.applicant2, res_q.context['users'])

    # -------------------------------------------------------------
    # 10. ADMIN AUDIT TRAIL ADVANCED FILTERS & PAGINATION
    # -------------------------------------------------------------
    def test_admin_audit_trail_filters(self):
        self.client.login(email='admin@multibiz.com', password='Password123!')
        url = reverse('admin_audit_trail')

        # All logs
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertGreaterEqual(res.context['total_logs_count'], 2)

        # Filter by action_type='delete_user'
        res_act = self.client.get(url, {'action_type': 'delete_user'})
        self.assertEqual(res_act.status_code, 200)
        self.assertEqual(len(res_act.context['logs']), 1)
        self.assertEqual(res_act.context['logs'][0].action_type, 'delete_user')

        # Filter by target_type='talent_request'
        res_tgt = self.client.get(url, {'target_type': 'talent_request'})
        self.assertEqual(res_tgt.status_code, 200)
        self.assertEqual(len(res_tgt.context['logs']), 1)
        self.assertEqual(res_tgt.context['logs'][0].target_type, 'talent_request')

        # Filter by date_range='today'
        res_today = self.client.get(url, {'date_range': 'today'})
        self.assertEqual(res_today.status_code, 200)

        # Search query by IP '192.168.1.50'
        res_ip = self.client.get(url, {'q': '192.168.1.50'})
        self.assertEqual(res_ip.status_code, 200)
        self.assertEqual(len(res_ip.context['logs']), 1)
        self.assertEqual(res_ip.context['logs'][0].ip_address, '192.168.1.50')

        # Pagination parameter page=1
        res_page = self.client.get(url, {'page': 1})
        self.assertEqual(res_page.status_code, 200)
