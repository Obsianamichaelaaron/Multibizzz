from django.db import models
from django.conf import settings
from accounts.models import EmployerProfile, ApplicantProfile

class Skill(models.Model):
    """Master taxonomy of skills."""
    skill_name = models.CharField(max_length=255, unique=True)
    category = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=20, default='active', choices=(('active', 'Active'), ('inactive', 'Inactive')))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['skill_name']

    def __str__(self):
        return self.skill_name


class Qualification(models.Model):
    """Master qualifications, degrees, and training fields."""
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, default='active', choices=(('active', 'Active'), ('inactive', 'Inactive')))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class EmployerRequest(models.Model):
    """Hiring / Talent Request submitted by Employer to Admin."""
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('under_admin_review', 'Under Admin Review'),
        ('approved', 'Approved'),
        ('changes_requested', 'Changes Requested'),
        ('job_posted', 'Job Posted'),
        ('candidates_found', 'Candidates Found'),
        ('candidates_sent', 'Candidates Sent'),
        ('employer_review', 'Employer Review'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
    )

    employer = models.ForeignKey(
        EmployerProfile,
        on_delete=models.CASCADE,
        related_name='talent_requests'
    )
    title = models.CharField(max_length=255, help_text="Position / Job Title")
    description = models.TextField(help_text="Detailed job description and responsibilities")
    skills_required = models.TextField(help_text="Comma-separated required skills")
    experience_required = models.CharField(max_length=100, default='1-3 years', help_text="e.g. 2+ years, Entry Level, 5 years")
    education_level = models.CharField(max_length=150, blank=True, null=True, help_text="e.g. Bachelor's Degree, Master's, High School")
    certifications = models.TextField(blank=True, null=True, help_text="Required or preferred certifications")
    location = models.CharField(max_length=255, default='Remote / Manila, Philippines')
    employment_type = models.CharField(max_length=50, choices=(
        ('full-time', 'Full-time'),
        ('part-time', 'Part-time'),
        ('contract', 'Contract'),
        ('internship', 'Internship'),
    ), default='full-time')
    salary_range = models.CharField(max_length=100, blank=True, null=True, default='Negotiable')
    vacancies_count = models.IntegerField(default=1, help_text="Number of candidates/applicants needed")
    other_requirements = models.TextField(blank=True, null=True, help_text="Other specific requirements or qualifications")
    additional_notes = models.TextField(blank=True, null=True, help_text="Additional notes for Admin")
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='submitted')
    admin_notes = models.TextField(blank=True, null=True, help_text="Feedback or remarks from Admin")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def get_skills_list(self):
        if not self.skills_required:
            return []
        return [s.strip() for s in self.skills_required.split(',') if s.strip()]

    @property
    def total_applicants_count(self):
        job = self.job_postings.first()
        return job.applications.count() if job else 0

    @property
    def qualified_candidates_count(self):
        job = self.job_postings.first()
        return job.applications.filter(qualification_status='qualified').count() if job else 0

    @property
    def sent_candidates_count(self):
        job = self.job_postings.first()
        return job.applications.filter(sent_to_employer=True).count() if job else 0

    def __str__(self):
        return f"Request #{self.id}: {self.title} ({self.employer.display_name}) - {self.get_status_display()}"


class JobPosting(models.Model):
    """Job listing posted by employer or admin."""
    EMPLOYMENT_TYPES = (
        ('full-time', 'Full-time'),
        ('part-time', 'Part-time'),
        ('contract', 'Contract'),
        ('internship', 'Internship'),
    )
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('closed', 'Closed'),
        ('draft', 'Draft'),
    )

    employer = models.ForeignKey(
        EmployerProfile,
        on_delete=models.CASCADE,
        related_name='job_postings',
        null=True,
        blank=True
    )
    talent_request = models.ForeignKey(
        EmployerRequest,
        on_delete=models.SET_NULL,
        related_name='job_postings',
        null=True,
        blank=True
    )
    title = models.CharField(max_length=255)
    description = models.TextField()
    requirements = models.TextField(blank=True, null=True)
    skills_required = models.TextField(blank=True, null=True, help_text="Comma-separated required skills")
    min_experience_years = models.IntegerField(default=0, help_text="Minimum required experience years")
    required_education = models.CharField(max_length=150, blank=True, null=True)
    required_certifications = models.TextField(blank=True, null=True)
    location = models.CharField(max_length=255, default='Remote / Manila, Philippines')
    employment_type = models.CharField(max_length=50, choices=EMPLOYMENT_TYPES, default='full-time')
    salary_range = models.CharField(max_length=100, blank=True, null=True, default='Negotiable')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    target_qualifications = models.TextField(blank=True, null=True, help_text="Comma-separated qualification names or IDs")
    created_by_admin = models.BooleanField(default=True)
    posted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-posted_at']

    @property
    def company_name(self):
        return self.employer.display_name if self.employer else "Multibiz Partner"

    def get_skills_list(self):
        if not self.skills_required:
            return []
        return [s.strip() for s in self.skills_required.split(',') if s.strip()]

    def __str__(self):
        return f"{self.title} @ {self.company_name}"


class SavedJob(models.Model):
    """Bookmarked job by an applicant."""
    applicant = models.ForeignKey(ApplicantProfile, on_delete=models.CASCADE, related_name='saved_jobs')
    job = models.ForeignKey(JobPosting, on_delete=models.CASCADE, related_name='saved_by')
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('applicant', 'job')
        ordering = ['-saved_at']

    def __str__(self):
        return f"{self.applicant.user.full_name} saved {self.job.title}"


class JobRecommendation(models.Model):
    """AI Job recommendation generated for applicant."""
    applicant = models.ForeignKey(ApplicantProfile, on_delete=models.CASCADE, related_name='recommendations')
    job = models.ForeignKey(JobPosting, on_delete=models.CASCADE, related_name='recommended_to')
    recommendation_score = models.DecimalField(max_digits=5, decimal_places=2)
    reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-recommendation_score', '-created_at']

    def __str__(self):
        return f"Rec {self.job.title} for {self.applicant.user.full_name} ({self.recommendation_score}%)"


class CandidateExport(models.Model):
    """
    Excel Candidate Export record uploaded to Google Drive with View-Only permissions for Employer.
    Contains both Qualified and Not Qualified candidate evaluations.
    """
    job = models.ForeignKey(JobPosting, on_delete=models.CASCADE, related_name='candidate_exports')
    employer = models.ForeignKey(EmployerProfile, on_delete=models.CASCADE, related_name='candidate_exports')
    talent_request = models.ForeignKey(EmployerRequest, on_delete=models.SET_NULL, null=True, blank=True, related_name='candidate_exports')
    excel_file = models.FileField(upload_to='candidate_exports/', blank=True, null=True)
    filename = models.CharField(max_length=255)
    google_drive_file_id = models.CharField(max_length=255, blank=True, null=True)
    google_drive_view_link = models.URLField(max_length=500, blank=True, null=True)
    google_drive_embed_link = models.URLField(max_length=500, blank=True, null=True)
    exported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='exported_candidate_batches')
    total_candidates = models.IntegerField(default=0)
    qualified_count = models.IntegerField(default=0)
    not_qualified_count = models.IntegerField(default=0)
    sent_to_employer = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    @property
    def exported_at(self):
        return self.created_at

    def __str__(self):
        return f"{self.filename} ({self.total_candidates} candidates) -> {self.employer.display_name}"

