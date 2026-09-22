from django.contrib import admin
from .models import AuditTrail

@admin.register(AuditTrail)
class AuditTrailAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'admin_name', 'action_type', 'target_type', 'target_name', 'ip_address')
    list_filter = ('action_type', 'target_type', 'created_at')
    search_fields = ('admin_name', 'action_description', 'target_name', 'ip_address')
    readonly_fields = [f.name for f in AuditTrail._meta.fields]
