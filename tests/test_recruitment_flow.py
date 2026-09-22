from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from accounts.models import User, EmployerProfile, ApplicantProfile
from jobs.models import JobPosting, EmployerRequest
from applications.models import Application
from ml_engine.matcher import evaluate_applicant_qualification, find_alternative_job_recommendations
from django.core import mail

class CompleteRecruitmentFlowTests(TestCase):
    def setUp(self):
        self.client = Client()

        # 1. Create Admin User
        self.admin_user = User.objects.create_user(
            email='admin@multibiz.com',
            password='Password123!',
            first_name='Admin',
            last_name='Officer',
            role='admin'
        )

        # 2. Create Employer User & Profile
        self.employer_user = User.objects.create_user(
            email='employer@techcorp.com',
            password='Password123!',
            first_name='John',
            last_name='Recruiter',
            role='employer'
        )
        self.employer_profile, _ = EmployerProfile.objects.get_or_create(user=self.employer_user)
        self.employer_profile.company_name = 'TechCorp Solutions'
        self.employer_profile.company_address = 'BGC, Taguig, Philippines'
        self.employer_profile.save()

        # 3. Create Qualified Applicant User & Profile (Python, Django, PostgreSQL, 4 years experience)
        self.qualified_user = User.objects.create_user(
            email='qualified@applicant.com',
            password='Password123!',
            first_name='Alice',
            last_name='Engineer',
            role='applicant'
        )
        self.qualified_profile, _ = ApplicantProfile.objects.get_or_create(user=self.qualified_user)
        self.qualified_profile.skills = 'Python, Django, PostgreSQL, Docker, Git'
        self.qualified_profile.experience_years = 4
        self.qualified_profile.education_level = "Bachelor's Degree in Computer Science"
        self.qualified_profile.resume_file = 'resumes/alice_resume.pdf'
        self.qualified_profile.save()

        # 4. Create Unqualified Applicant User & Profile (Graphics, Photoshop, 0 years tech exp)
        self.unqualified_user = User.objects.create_user(
            email='unqualified@applicant.com',
            password='Password123!',
            first_name='Bob',
            last_name='Designer',
            role='applicant'
        )
        self.unqualified_profile, _ = ApplicantProfile.objects.get_or_create(user=self.unqualified_user)
        self.unqualified_profile.skills = 'Photoshop, Illustrator, Graphic Design'
        self.unqualified_profile.experience_years = 0
        self.unqualified_profile.education_level = "High School Diploma"
        self.unqualified_profile.resume_file = 'resumes/bob_resume.pdf'
        self.unqualified_profile.save()

    def test_scenario_1_happy_path_qualified_applicant(self):
        """
        Scenario 1: Full Controlled Flow:
        - Employer submits Talent Request
        - Admin approves request & publishes Job
        - Qualified Applicant applies -> marked qualified / under_review & email dispatched
        - Admin notifies qualified applicants & sends candidates to employer with Talent Radar ranking
        - Employer views candidate on Talent Radar (#1 Top Match) and selects/hires candidate
        """
        # Step A: Employer submits Talent Request
        self.client.force_login(self.employer_user)
        req_data = {
            'title': 'Senior Python Developer',
            'employment_type': 'full-time',
            'location': 'Taguig / Remote',
            'salary_range': '₱90,000 - ₱120,000',
            'vacancies_count': 2,
            'skills_required': 'Python, Django, PostgreSQL',
            'experience_required': '3+ years',
            'education_level': "Bachelor's Degree",
            'certifications': 'None',
            'description': 'Leading core backend microservices.',
            'other_requirements': 'Good communication skills.',
            'additional_notes': 'Urgent hiring need.'
        }
        res = self.client.post(reverse('employer_request_talent'), req_data)
        self.assertEqual(res.status_code, 302)

        talent_req = EmployerRequest.objects.filter(employer=self.employer_profile, title='Senior Python Developer').first()
        self.assertIsNotNone(talent_req)
        self.assertEqual(talent_req.status, 'submitted')

        # Step B: Admin reviews and approves Talent Request
        self.client.force_login(self.admin_user)
        res_approve = self.client.post(reverse('admin_employer_request_detail', args=[talent_req.id]), {
            'action': 'approve',
            'admin_notes': 'Approved. Proceeding to job publishing.'
        })
        talent_req.refresh_from_db()
        self.assertEqual(talent_req.status, 'approved')

        # Step C: Admin creates and publishes JobPosting from Request
        job_data = {
            'employer': self.employer_profile.id,
            'talent_request': talent_req.id,
            'title': 'Senior Python Developer',
            'employment_type': 'full-time',
            'location': 'Taguig / Remote',
            'salary_range': '₱90,000 - ₱120,000',
            'skills_required': 'Python, Django, PostgreSQL',
            'min_experience_years': 3,
            'required_education': "Bachelor's Degree",
            'required_certifications': '',
            'target_qualifications': 'Computer Science',
            'description': 'Leading core backend microservices.',
            'requirements': '3+ years Python & Django experience.',
            'status': 'active'
        }
        res_job = self.client.post(reverse('admin_create_job_from_request', args=[talent_req.id]), job_data)
        self.assertEqual(res_job.status_code, 302)

        job = JobPosting.objects.filter(talent_request=talent_req).first()
        self.assertIsNotNone(job)
        self.assertTrue(job.created_by_admin)
        self.assertEqual(job.status, 'active')

        # Step D: Qualified Applicant applies to Job
        mail.outbox.clear()
        self.client.force_login(self.qualified_user)
        apply_res = self.client.post(reverse('apply_job', args=[job.id]), {
            'cover_letter': 'I am an experienced Python Django developer excited for this role.'
        })
        self.assertEqual(apply_res.status_code, 302)

        application = Application.objects.filter(job=job, applicant=self.qualified_profile).first()
        self.assertIsNotNone(application)
        self.assertEqual(application.qualification_status, 'qualified')
        self.assertEqual(application.status, 'under_review')
        self.assertTrue(application.match_score >= 60)
        
        # Verify "Your application is under review" email was dispatched
        self.assertTrue(len(mail.outbox) >= 1)
        self.assertIn('is under review', mail.outbox[0].subject.lower())

        # Step E: Admin notifies qualified applicants & sends candidates to Employer
        self.client.force_login(self.admin_user)
        
        # Notify single or batch
        res_notify = self.client.post(reverse('admin_notify_qualified_applicants', args=[job.id]))
        self.assertEqual(res_notify.status_code, 302)
        application.refresh_from_db()
        self.assertTrue(application.notification_sent)

        # Send candidates to employer
        res_send = self.client.post(reverse('admin_send_candidates_to_employer', args=[job.id]))
        self.assertEqual(res_send.status_code, 302)
        
        application.refresh_from_db()
        self.assertTrue(application.sent_to_employer)
        self.assertEqual(application.radar_rank, 1)

        talent_req.refresh_from_db()
        self.assertEqual(talent_req.status, 'candidates_sent')

        # Step F: Employer views candidates on Talent Radar and decides
        self.client.force_login(self.employer_user)
        radar_res = self.client.get(reverse('recommended_candidates') + f'?job_id={job.id}')
        self.assertEqual(radar_res.status_code, 200)

        # Employer records decision -> 'selected'
        decision_res = self.client.post(reverse('employer_decide_candidate', args=[application.id]), {
            'decision': 'selected',
            'notes': 'Top candidate from Talent Radar! Offer extended.'
        })
        self.assertEqual(decision_res.status_code, 302)

        application.refresh_from_db()
        self.assertEqual(application.employer_decision, 'selected')
        self.assertEqual(application.status, 'selected')
        self.assertIsNotNone(application.employer_decision_at)

    def test_applicant_application_wizard_has_stepper_and_personal_details(self):
        """The applicant application page should expose a step-by-step wizard matching the expected UX."""
        job = JobPosting.objects.create(
            employer=self.employer_profile,
            title='Operations Analyst',
            skills_required='Excel, SQL, Reporting',
            min_experience_years=1,
            status='active',
            created_by_admin=True
        )

        self.client.force_login(self.qualified_user)
        response = self.client.get(reverse('apply_job', args=[job.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Choose documents')
        self.assertContains(response, 'Answer employee questions')
        self.assertContains(response, 'Update Jobstreet Profile')
        self.assertContains(response, 'Review and submit')
        self.assertContains(response, 'Personal details')
        self.assertContains(response, 'First name')
        self.assertContains(response, 'Last name')
        self.assertContains(response, 'Home location')
        self.assertContains(response, 'Phone number')

    def test_scenario_2_unqualified_applicant_flow(self):
        """
        Scenario 2: Unqualified Applicant Flow:
        - Job requires 5 years exp in Python, AWS, Kubernetes
        - Unqualified candidate applies
        - Evaluated as not_qualified
        - Email sent: "You are not qualified for this position"
        - Alternative jobs recommended
        """
        # Create target job and alternative design job
        job = JobPosting.objects.create(
            employer=self.employer_profile,
            title='Cloud Systems Architect',
            skills_required='Python, AWS, Kubernetes, Terraform',
            min_experience_years=5,
            required_education="Master's or Bachelor's Degree",
            status='active',
            created_by_admin=True
        )

        alt_job = JobPosting.objects.create(
            employer=self.employer_profile,
            title='Junior UI/UX Graphic Designer',
            skills_required='Photoshop, Illustrator, Graphic Design',
            min_experience_years=0,
            status='active',
            created_by_admin=True
        )

        # Apply
        mail.outbox.clear()
        self.client.force_login(self.unqualified_user)
        apply_res = self.client.post(reverse('apply_job', args=[job.id]), {
            'cover_letter': 'I want to try cloud architecture.'
        })
        self.assertEqual(apply_res.status_code, 302)

        application = Application.objects.filter(job=job, applicant=self.unqualified_profile).first()
        self.assertIsNotNone(application)
        self.assertEqual(application.qualification_status, 'not_qualified')
        self.assertEqual(application.status, 'not_qualified')

        # Verify email dispatched with alternative recommendation
        self.assertTrue(len(mail.outbox) >= 1)
        self.assertIn('update on your application', mail.outbox[0].subject.lower())

        # Verify alternative recommendations engine returns the design job
        recs = find_alternative_job_recommendations(self.unqualified_profile, exclude_job_id=job.id)
        self.assertTrue(len(recs) >= 1)
        self.assertEqual(recs[0]['job'].id, alt_job.id)

    def test_scenario_3_direct_employer_posting_blocked(self):
        """
        Scenario 3: Direct Job Posting Restriction:
        - Employers attempting to post a job directly are redirected to Talent Request form.
        """
        self.client.force_login(self.employer_user)
        res = self.client.get(reverse('employer_post_job'))
        self.assertEqual(res.status_code, 302)
        self.assertTrue(res.url.endswith(reverse('employer_request_talent')))

    def test_scenario_4_admin_workflow_and_candidate_management(self):
        """
        Scenario 4: Admin Oversight:
        - Admin can list all employer talent requests
        - Admin can filter candidates and inspect score breakdown
        - Admin can reject / request changes
        """
        req = EmployerRequest.objects.create(
            employer=self.employer_profile,
            title='DevOps Specialist',
            skills_required='Linux, Docker, CI/CD',
            experience_required='2 years',
            status='submitted'
        )

        self.client.force_login(self.admin_user)
        list_res = self.client.get(reverse('admin_employer_requests'))
        self.assertEqual(list_res.status_code, 200)
        self.assertContains(list_res, 'DevOps Specialist')

        # Test request changes
        res_change = self.client.post(reverse('admin_employer_request_detail', args=[req.id]), {
            'action': 'request_changes',
            'admin_notes': 'Please clarify remote vs on-site requirements.'
        })
        req.refresh_from_db()
        self.assertEqual(req.status, 'changes_requested')

    def test_scenario_5_employer_candidate_review_and_decision(self):
        """
        Scenario 5: Employer Talent Radar Candidate Decision:
        - Candidate sent to employer
        - Employer can shortlist candidate
        - Employer can reject candidate
        - Employer can select candidate
        """
        job = JobPosting.objects.create(
            employer=self.employer_profile,
            title='Backend Developer',
            skills_required='Python, Django',
            min_experience_years=2,
            status='active',
            created_by_admin=True
        )

        app = Application.objects.create(
            job=job,
            applicant=self.qualified_profile,
            qualification_status='qualified',
            match_score=88.5,
            skills_match_score=90.0,
            exp_match_score=85.0,
            edu_match_score=90.0,
            sent_to_employer=True,
            radar_rank=1,
            status='under_review'
        )

        self.client.force_login(self.employer_user)

        # Shortlist
        res_shortlist = self.client.post(reverse('employer_decide_candidate', args=[app.id]), {
            'decision': 'shortlisted',
            'notes': 'Impressive backend background.'
        })
        app.refresh_from_db()
        self.assertEqual(app.employer_decision, 'shortlisted')
        self.assertEqual(app.status, 'shortlisted')

        # Reject
        res_reject = self.client.post(reverse('employer_decide_candidate', args=[app.id]), {
            'decision': 'rejected',
            'notes': 'Not suitable at this time.'
        })
        app.refresh_from_db()
        self.assertEqual(app.employer_decision, 'rejected')
        self.assertEqual(app.status, 'rejected')
