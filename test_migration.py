import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'multibiz_project.settings')
django.setup()

from django.test import Client
from accounts.models import User, ApplicantProfile, EmployerProfile
from jobs.models import JobPosting, Skill, Qualification
from applications.models import Application
from core.models import CMSHeroSlide, CMSBrand

def run_tests():
    print("--- TESTING DJANGO MULTIBIZ MIGRATION ---")
    client = Client()

    # 1. Test Public Routes
    routes = ['/', '/about/', '/services/', '/solutions/', '/jobs/careers/']
    for r in routes:
        resp = client.get(r)
        assert resp.status_code == 200, f"Route {r} failed with status {resp.status_code}"
        print(f"[OK] Route {r} OK (status {resp.status_code})")

    # 2. Test Accounts Query
    admin_u = User.objects.filter(email='admin@gmail.com').first()
    employer_u = User.objects.filter(email='employer@gmail.com').first()
    applicant_u = User.objects.filter(email='jobseeker@gmail.com').first()

    assert admin_u is not None, "Admin user missing"
    assert employer_u is not None, "Employer user missing"
    assert applicant_u is not None, "Applicant user missing"
    print("[OK] All 3 default user accounts exist")

    # 3. Test Applicant Login & Dashboard, Profile, and Chatbot
    client.force_login(applicant_u)
    resp = client.get('/applications/applicant/dashboard/')
    assert resp.status_code == 200, f"Applicant dashboard failed with {resp.status_code}"
    resp_prof = client.get('/accounts/applicant/profile/')
    assert resp_prof.status_code == 200, f"Applicant profile failed with {resp_prof.status_code}"
    resp_chat = client.get('/chatbot/career-guide/')
    assert resp_chat.status_code == 200, f"Chatbot view failed with {resp_chat.status_code}"
    print("[OK] Applicant login, dashboard, profile, and chatbot access OK")

    # 4. Test Employer Login & Candidates Pipeline and Profile
    client.force_login(employer_u)
    resp = client.get('/applications/employer/candidates/')
    assert resp.status_code == 200, f"Employer candidates failed with {resp.status_code}"
    resp_emp_prof = client.get('/accounts/employer/profile/')
    assert resp_emp_prof.status_code == 200, f"Employer profile failed with {resp_emp_prof.status_code}"
    print("[OK] Employer login, candidates pipeline, and company profile OK")

    # 5. Test Admin Login & Dashboard
    client.force_login(admin_u)
    resp = client.get('/audit/dashboard/')
    assert resp.status_code == 200, f"Admin dashboard failed with {resp.status_code}"
    print("[OK] Admin login and dashboard access OK")

    print("\nALL 5/5 TESTS PASSED SUCCESSFULLY! DJANGO MIGRATION COMPLETE!")

if __name__ == '__main__':
    run_tests()
