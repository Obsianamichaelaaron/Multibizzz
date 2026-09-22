from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, ApplicantProfile, EmployerProfile

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('email', 'first_name', 'last_name', 'role', 'status', 'is_staff', 'created_at')
    list_filter = ('role', 'status', 'is_staff', 'created_at')
    ordering = ('-created_at',)
    search_fields = ('email', 'first_name', 'last_name')
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'phone')}),
        ('Permissions & Roles', {'fields': ('role', 'status', 'created_by_admin', 'is_active', 'is_staff', 'is_superuser')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'role', 'password', 'status'),
        }),
    )

@admin.register(ApplicantProfile)
class ApplicantProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'education_level', 'experience_years', 'employability_score', 'profile_completed')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'skills')

@admin.register(EmployerProfile)
class EmployerProfileAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'user', 'industry', 'company_size')
    search_fields = ('company_name', 'user__email', 'industry')
