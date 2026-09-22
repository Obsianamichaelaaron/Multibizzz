import os
from django.core.management.base import BaseCommand
from django.utils import timezone
from accounts.models import User, ApplicantProfile, EmployerProfile
from jobs.models import Skill, Qualification, JobPosting, SavedJob
from applications.models import Application, CandidateFeedback, InterviewSchedule
from core.models import CMSHeroSlide, CMSBrand, CMSTestimonial, CMSNews, ContactInquiry
from chatbot.models import ChatbotAnswer, ChatbotRecommendation

class Command(BaseCommand):
    help = 'Seeds initial default data, master catalogs, demo jobs, CMS content, and user accounts for Multibiz.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Seeding Multibiz initial database..."))

        # 1. DEFAULT USERS
        users_data = [
            {
                'email': 'admin@gmail.com',
                'password': 'admin123',
                'role': 'admin',
                'first_name': 'Admin',
                'last_name': 'Administrator',
                'is_staff': True,
                'is_superuser': True,
            },
            {
                'email': 'employer@gmail.com',
                'password': 'employer123',
                'role': 'employer',
                'first_name': 'TechCorp',
                'last_name': 'Recruiter',
                'company_name': 'TechCorp Solutions Inc.',
                'industry': 'Information Technology',
                'company_address': 'Bonifacio Global City, Taguig, Metro Manila',
                'company_website': 'https://techcorp.multibiz.com',
                'company_size': '51-200 employees',
            },
            {
                'email': 'jobseeker@gmail.com',
                'password': 'jobseeker123',
                'role': 'applicant',
                'first_name': 'Alex',
                'last_name': 'Dela Cruz',
                'phone': '+63 912 345 6789',
                'skills': 'Python, Django, JavaScript, React, SQL, Git, Problem Solving, Communication',
                'qualifications': 'Bachelor of Science in Information Technology',
                'education_level': 'Bachelor',
                'experience_years': 3,
                'employability_score': 84.50,
            },
            {
                'email': 'maria.santos@gmail.com',
                'password': 'jobseeker123',
                'role': 'applicant',
                'first_name': 'Maria',
                'last_name': 'Santos',
                'phone': '+63 920 987 6543',
                'skills': 'UI/UX Design, Figma, Adobe XD, HTML, CSS, JavaScript, Visual Design, Collaboration',
                'qualifications': 'Bachelor of Science in Computer Science',
                'education_level': 'Bachelor',
                'experience_years': 4,
                'employability_score': 88.00,
            }
        ]

        created_users = {}
        for udata in users_data:
            u, created = User.objects.get_or_create(
                email=udata['email'],
                defaults={
                    'first_name': udata['first_name'],
                    'last_name': udata['last_name'],
                    'role': udata['role'],
                    'status': 'active',
                    'is_staff': udata.get('is_staff', False),
                    'is_superuser': udata.get('is_superuser', False),
                }
            )
            u.set_password(udata['password'])
            u.save()
            created_users[udata['email']] = u

            if u.is_applicant:
                prof, _ = ApplicantProfile.objects.get_or_create(user=u)
                prof.skills = udata.get('skills', '')
                prof.qualifications = udata.get('qualifications', '')
                prof.education_level = udata.get('education_level', 'Bachelor')
                prof.experience_years = udata.get('experience_years', 1)
                prof.employability_score = udata.get('employability_score', 50.0)
                prof.profile_completed = True
                prof.save()
            elif u.is_employer:
                eprof, _ = EmployerProfile.objects.get_or_create(user=u)
                eprof.company_name = udata.get('company_name', 'TechCorp Solutions')
                eprof.industry = udata.get('industry', 'Information Technology')
                eprof.company_address = udata.get('company_address', 'Manila, Philippines')
                eprof.company_website = udata.get('company_website', 'https://example.com')
                eprof.company_size = udata.get('company_size', '51-200 employees')
                eprof.save()

        self.stdout.write(self.style.SUCCESS("[OK] Default user accounts seeded."))

        # 2. MASTER QUALIFICATIONS
        qualifications_list = [
            ("Bachelor of Science in Information Technology", "Comprehensive software, systems, and networking foundation."),
            ("Bachelor of Science in Computer Science", "Algorithms, software engineering, systems design, and AI."),
            ("Bachelor of Science in Accounting Information System", "Financial systems, auditing, accounting software, and compliance."),
            ("Bachelor of Science in Business Administration", "Management, strategic operations, finance, and marketing."),
            ("Bachelor of Science in Marketing Management", "Digital advertising, consumer behavior, brand management, and market research."),
            ("Bachelor of Science in Nursing", "Clinical healthcare, patient care, medical administration."),
            ("Bachelor of Science in Civil Engineering", "Structural design, construction management, infrastructure development."),
            ("Bachelor of Science in Criminology", "Law enforcement, security management, forensic analysis, compliance."),
            ("Bachelor of Science in Hospitality Management", "Guest services, hotel operations, event planning, hospitality management."),
        ]

        for qname, qdesc in qualifications_list:
            Qualification.objects.get_or_create(name=qname, defaults={'description': qdesc, 'status': 'active'})

        self.stdout.write(self.style.SUCCESS("[OK] Master qualifications catalog seeded."))

        # 3. MASTER SKILLS TAXONOMY
        skills_catalog = [
            ('Python', 'Programming'), ('Django', 'Web Framework'), ('JavaScript', 'Programming'),
            ('TypeScript', 'Programming'), ('React', 'Frontend'), ('Vue', 'Frontend'),
            ('HTML', 'Frontend'), ('CSS', 'Frontend'), ('Bootstrap', 'Frontend'),
            ('SQL', 'Database'), ('MySQL', 'Database'), ('PostgreSQL', 'Database'),
            ('Git', 'DevOps'), ('GitHub', 'DevOps'), ('Docker', 'DevOps'),
            ('REST API', 'Backend'), ('PHP', 'Programming'), ('Laravel', 'Web Framework'),
            ('UI/UX Design', 'Design'), ('Figma', 'Design'), ('Adobe XD', 'Design'),
            ('Photoshop', 'Design'), ('Communication', 'Soft Skills'), ('Problem Solving', 'Soft Skills'),
            ('Leadership', 'Soft Skills'), ('Project Management', 'Management'), ('Time Management', 'Soft Skills'),
            ('Teamwork', 'Soft Skills'), ('Adaptability', 'Soft Skills'), ('Marketing', 'Business'),
            ('Social Media Marketing', 'Business'), ('Accounting', 'Finance'), ('Customer Service', 'Operations'),
        ]

        for sname, scat in skills_catalog:
            Skill.objects.get_or_create(skill_name=sname, defaults={'category': scat, 'status': 'active'})

        self.stdout.write(self.style.SUCCESS("[OK] Master skills taxonomy seeded."))

        # 4. CMS HERO SLIDES & CONTENT
        slides_data = [
            {
                'title': 'Connecting Exceptional Talent with Industry Leaders',
                'subtitle': 'Empowering careers through smart AI-powered recruitment, automated skill matching, and verified qualification pipelines.',
                'button_text': 'Explore Careers',
                'button_link': '/jobs/careers/',
                'sort_order': 1,
            },
            {
                'title': 'Intelligent Candidate Matching for Forward-Thinking Teams',
                'subtitle': 'Hiring made seamless. Discover qualified candidates ranked by experience, capability, and predictive AI scores.',
                'button_text': 'Post a Job Today',
                'button_link': '/accounts/register/?tab=employer',
                'sort_order': 2,
            }
        ]
        for sdata in slides_data:
            CMSHeroSlide.objects.get_or_create(title=sdata['title'], defaults=sdata)

        # CMS Brands
        brands_data = [
            {'brand_name': 'Multibiz International', 'brand_category': 'cor', 'sort_order': 1},
            {'brand_name': 'Apex Global Solutions', 'brand_category': 'cor', 'sort_order': 2},
            {'brand_name': 'Vanguard Tech Partners', 'brand_category': 'cor', 'sort_order': 3},
            {'brand_name': 'NextGen Media', 'brand_category': 'cor', 'sort_order': 4},
            {'brand_name': 'Pinnacle Capital Group', 'brand_category': 'cor', 'sort_order': 5},
        ]
        for bdata in brands_data:
            CMSBrand.objects.get_or_create(brand_name=bdata['brand_name'], defaults=bdata)

        # CMS Testimonials
        testimonials_data = [
            {
                'author_name': 'David Harrison',
                'author_role': 'VP of Engineering',
                'company': 'Apex Global',
                'content': 'Multibiz streamlined our technical recruitment cycle by over 60%. The candidate matching and resume parsing accuracy is second to none.',
                'rating': 5,
                'sort_order': 1,
            },
            {
                'author_name': 'Clarissa Mendoza',
                'author_role': 'Lead Talent Specialist',
                'company': 'Vanguard Innovations',
                'content': 'The AI chatbot career assessment and automated candidate ranking made identifying top-tier developers and analysts effortless.',
                'rating': 5,
                'sort_order': 2,
            }
        ]
        for tdata in testimonials_data:
            CMSTestimonial.objects.get_or_create(author_name=tdata['author_name'], defaults=tdata)

        # CMS News
        news_data = [
            {
                'title': 'Multibiz Unveils Next-Gen AI Resume & Skills Match Engine',
                'category': 'Platform Update',
                'excerpt': 'New algorithm accurately parses candidate resumes and ranks qualifications with unprecedented precision.',
                'content': 'Today we are excited to roll out the latest enhancement to our matching architecture...',
                'news_date': timezone.now().date(),
                'is_featured': True
            },
            {
                'title': 'Top Tech and Business Skills in High Demand for 2026',
                'category': 'Career Insights',
                'excerpt': 'An in-depth analysis of emerging hiring patterns across Southeast Asia and global tech hubs.',
                'content': 'From full-stack web development to data science and automated workflow engineering...',
                'news_date': timezone.now().date(),
                'is_featured': True
            }
        ]
        for ndata in news_data:
            CMSNews.objects.get_or_create(title=ndata['title'], defaults=ndata)

        self.stdout.write(self.style.SUCCESS("[OK] CMS content (Hero slides, brands, testimonials, news) seeded."))

        # 5. DEMO JOB POSTINGS
        employer_user = created_users['employer@gmail.com']
        employer_prof = employer_user.employer_profile

        jobs_data = [
            {
                'title': 'Senior Python / Django Full-Stack Developer',
                'employment_type': 'full-time',
                'location': 'Taguig / Remote, Philippines',
                'salary_range': '₱80,000 - ₱130,000 / month',
                'skills_required': 'Python, Django, JavaScript, React, SQL, REST API, Git, Docker',
                'target_qualifications': 'Bachelor of Science in Computer Science, Bachelor of Science in Information Technology',
                'description': 'We are looking for an experienced Senior Python/Django developer to build and scale modern web applications, high-performance REST APIs, and microservices.',
                'requirements': '3+ years of professional backend experience with Python and Django. Solid proficiency in database design, REST APIs, and frontend integration.',
                'status': 'active'
            },
            {
                'title': 'Frontend UI/UX Engineer (React & TypeScript)',
                'employment_type': 'full-time',
                'location': 'Makati City / Hybrid',
                'salary_range': '₱65,000 - ₱95,000 / month',
                'skills_required': 'React, JavaScript, TypeScript, HTML, CSS, Figma, UI/UX Design, Git',
                'target_qualifications': 'Bachelor of Science in Information Technology, Bachelor of Science in Computer Science',
                'description': 'Join our digital product studio to create visually stunning, responsive, and intuitive web user experiences for global clients.',
                'requirements': 'Demonstrated experience crafting polished web interfaces with React, modern CSS, and state management. Strong eye for design details.',
                'status': 'active'
            },
            {
                'title': 'Data Analyst & BI Specialist',
                'employment_type': 'full-time',
                'location': 'Ortigas / Hybrid',
                'salary_range': '₱50,000 - ₱75,000 / month',
                'skills_required': 'Python, SQL, MySQL, Communication, Problem Solving, Project Management',
                'target_qualifications': 'Bachelor of Science in Accounting Information System, Bachelor of Science in Information Technology',
                'description': 'Transform complex business datasets into actionable executive insights, dashboards, and automated performance tracking reports.',
                'requirements': 'Proficiency with SQL querying, exploratory data analysis, and dashboard visualization tools.',
                'status': 'active'
            },
            {
                'title': 'Junior Web Developer',
                'employment_type': 'full-time',
                'location': 'Remote / Manila',
                'salary_range': '₱30,000 - ₱45,000 / month',
                'skills_required': 'Python, JavaScript, HTML, CSS, Git, Teamwork, Communication',
                'target_qualifications': 'Bachelor of Science in Information Technology, Bachelor of Science in Computer Science',
                'description': 'Great growth opportunity for an ambitious junior developer looking to work with modern Python and JavaScript web tech stacks.',
                'requirements': 'Strong foundational programming skills, familiarity with Git workflows, and eagerness to learn rapidly.',
                'status': 'active'
            }
        ]

        created_jobs = []
        for jdata in jobs_data:
            job_obj, _ = JobPosting.objects.get_or_create(
                title=jdata['title'],
                employer=employer_prof,
                defaults=jdata
            )
            created_jobs.append(job_obj)

        self.stdout.write(self.style.SUCCESS(f"[OK] {len(created_jobs)} Job Postings seeded."))

        # 6. DEMO APPLICATIONS
        alex_prof = created_users['jobseeker@gmail.com'].applicant_profile
        maria_prof = created_users['maria.santos@gmail.com'].applicant_profile

        if created_jobs:
            app1, _ = Application.objects.get_or_create(
                job=created_jobs[0],
                applicant=alex_prof,
                defaults={
                    'status': 'shortlisted',
                    'match_score': 88.50,
                    'cover_letter': 'I am thrilled to apply for the Senior Python/Django position. With 3+ years building robust web apps, I am confident I can make an immediate impact.',
                }
            )
            app1.add_remark('shortlisted', 'Strong background in Django and Python. Profile ranked in Excellent category.', employer_prof.display_name)
            app1.save()

            app2, _ = Application.objects.get_or_create(
                job=created_jobs[1],
                applicant=maria_prof,
                defaults={
                    'status': 'interviewed',
                    'match_score': 92.00,
                    'cover_letter': 'I have 4 years of UI/UX and React engineering experience with a deep passion for clean design systems.',
                }
            )
            app2.add_remark('interviewed', 'Scheduled for technical video interview.', employer_prof.display_name)
            app2.save()

            # Schedule demo interview
            InterviewSchedule.objects.get_or_create(
                application=app2,
                employer=employer_prof,
                defaults={
                    'interview_date': timezone.now().date() + timezone.timedelta(days=2),
                    'start_time': '10:00:00',
                    'end_time': '11:00:00',
                    'interview_type': 'video',
                    'meeting_link': 'https://meet.google.com/mbz-tech-interview',
                    'notes': 'Technical screening and design portfolio walkthrough.',
                    'status': 'scheduled'
                }
            )

        self.stdout.write(self.style.SUCCESS("[OK] Demo applications and interview appointments seeded."))

        self.stdout.write(self.style.SUCCESS("""
=====================================================
[OK] MULTIBIZ DJANGO MIGRATION SEED COMPLETED!
=====================================================
Default Accounts Available:
- Admin:     admin@gmail.com     / admin123
- Employer:  employer@gmail.com  / employer123
- Jobseeker: jobseeker@gmail.com / jobseeker123
=====================================================
        """))
