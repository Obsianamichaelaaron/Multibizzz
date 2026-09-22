import json
from django.db import models
from django.conf import settings
from django.utils import timezone

from jobs.models import JobPosting
from accounts.models import ApplicantProfile, EmployerProfile

class Application(models.Model):
    """Job application submitted by an applicant."""
    STATUS_CHOICES = (
        ('applied', 'Applied'),
        ('qualified', 'Qualified'),
        ('not_qualified', 'Not Qualified'),
        ('under_review', 'Under Review'),
        ('shortlisted', 'Shortlisted'),
        ('interviewed', 'Interview Scheduled'),
        ('selected', 'Selected / Hired'),
        ('accepted', 'Accepted / Hired'),
        ('rejected', 'Rejected'),
        ('pending', 'Pending Review'),
        ('reviewed', 'Reviewed'),
    )

    QUALIFICATION_CHOICES = (
        ('pending', 'Pending Evaluation'),
        ('qualified', 'Qualified'),
        ('under_qualified', 'Under Qualified'),
        ('not_qualified', 'Not Qualified'),
    )

    EMPLOYER_DECISION_CHOICES = (
        ('none', 'Pending Employer Review'),
        ('shortlisted', 'Shortlisted'),
        ('rejected', 'Rejected'),
        ('selected', 'Selected / Hired'),
    )

    job = models.ForeignKey(JobPosting, on_delete=models.CASCADE, related_name='applications')
    applicant = models.ForeignKey(ApplicantProfile, on_delete=models.CASCADE, related_name='applications')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='applied')
    
    # Automated qualification result & scoring
    qualification_status = models.CharField(max_length=30, choices=QUALIFICATION_CHOICES, default='pending')
    qualification_reason = models.TextField(blank=True, null=True, help_text="Internal evaluation and criteria match summary")
    match_score = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    skills_match_score = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    exp_match_score = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    edu_match_score = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    radar_rank = models.IntegerField(null=True, blank=True, help_text="Talent Radar Ranking position (e.g. 1 for Top Match)")

    # Notification tracking
    notification_sent = models.BooleanField(default=False)
    notification_sent_at = models.DateTimeField(null=True, blank=True)

    # Employer candidate submission & review
    sent_to_employer = models.BooleanField(default=False)
    sent_to_employer_at = models.DateTimeField(null=True, blank=True)
    employer_decision = models.CharField(max_length=30, choices=EMPLOYER_DECISION_CHOICES, default='none')
    employer_decision_at = models.DateTimeField(null=True, blank=True)
    employer_decision_notes = models.TextField(blank=True, null=True)

    remarks_history = models.TextField(blank=True, null=True, help_text="JSON list of status changes and employer remarks")
    applicant_remarks_history = models.TextField(blank=True, null=True)
    reviewed_by_employer_id = models.IntegerField(blank=True, null=True)
    reviewed_by_name = models.CharField(max_length=255, blank=True, null=True)
    cover_letter = models.TextField(blank=True, null=True)
    resume_file = models.FileField(upload_to='uploads/resumes/', blank=True, null=True)
    applied_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    classification = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        ordering = ['-applied_at']
        unique_together = ('job', 'applicant')

    def get_remarks_list(self):
        if not self.remarks_history:
            return []
        try:
            return json.loads(self.remarks_history)
        except Exception:
            return []

    def add_remark(self, status, remarks_text, reviewer_name):
        history = self.get_remarks_list()
        entry = {
            'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status': status,
            'remarks': remarks_text,
            'reviewed_by': reviewer_name
        }
        history.append(entry)
        self.remarks_history = json.dumps(history)
        self.status = status
        self.reviewed_by_name = reviewer_name

    def __str__(self):
        return f"{self.applicant.user.full_name} -> {self.job.title} ({self.status})"


class CandidateFeedback(models.Model):
    """Employer feedback on candidate application."""
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='feedbacks')
    applicant = models.ForeignKey(ApplicantProfile, on_delete=models.CASCADE, related_name='feedbacks_received')
    employer = models.ForeignKey(EmployerProfile, on_delete=models.CASCADE, related_name='feedbacks_given')
    employability_score = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    feedback_message = models.TextField()
    feedback_type = models.CharField(max_length=20, default='automatic', choices=(('automatic', 'Automatic'), ('manual', 'Manual')))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Feedback for {self.applicant.user.full_name}"


class InterviewSchedule(models.Model):
    """Scheduled interview between candidate and employer."""
    STATUS_CHOICES = (
        ('scheduled', 'Scheduled'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('rescheduled', 'Rescheduled'),
    )

    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='interviews')
    employer = models.ForeignKey(EmployerProfile, on_delete=models.CASCADE, related_name='interviews')
    interview_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    interview_type = models.CharField(max_length=50, default='video', help_text="in-person, phone, video")
    location = models.CharField(max_length=255, blank=True, null=True)
    meeting_link = models.CharField(max_length=255, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['interview_date', 'start_time']

    def __str__(self):
        return f"Interview: {self.application.applicant.user.full_name} on {self.interview_date} ({self.status})"
