from django.db import models
from django.conf import settings

class AuditTrail(models.Model):
    """Audit Trail for administrative and critical system actions."""
    admin_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs'
    )
    admin_name = models.CharField(max_length=255)
    action_type = models.CharField(max_length=100)
    action_description = models.TextField()
    target_type = models.CharField(max_length=50, blank=True, null=True, help_text="employer, applicant, user, job, cms, etc.")
    target_id = models.IntegerField(blank=True, null=True)
    target_name = models.CharField(max_length=255, blank=True, null=True)
    ip_address = models.CharField(max_length=45, blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.created_at:%Y-%m-%d %H:%M}] {self.admin_name} - {self.action_type}"
