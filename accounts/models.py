from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager

class CustomUserManager(BaseUserManager):
    """Custom user manager where email is the unique identifier for auth."""
    def normalize_email(self, email):
        email = (email or '').strip()
        return super().normalize_email(email).lower()

    def get_by_natural_key(self, email):
        return self.get(**{f'{self.model.EMAIL_FIELD}__iexact': email})

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'admin')
        extra_fields.setdefault('status', 'active')

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)

class User(AbstractUser):
    """Custom user model for Multibiz supporting applicant, employer, and admin roles."""
    username = None
    email = models.EmailField('email address', unique=True)
    
    ROLE_CHOICES = (
        ('applicant', 'Applicant / Jobseeker'),
        ('employer', 'Employer'),
        ('admin', 'Administrator'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='applicant')
    
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('suspended', 'Suspended'),
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    phone = models.CharField(max_length=30, blank=True, null=True)
    created_by_admin = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    objects = CustomUserManager()

    @property
    def is_applicant(self):
        return self.role == 'applicant'

    @property
    def is_employer(self):
        return self.role == 'employer'

    @property
    def is_admin_user(self):
        return self.role == 'admin' or self.is_superuser or self.is_staff

    @property
    def full_name(self):
        name = f"{self.first_name} {self.last_name}".strip()
        return name if name else self.email.split('@')[0]

    def clean(self):
        super().clean()
        if self.email:
            self.email = self.email.strip().lower()

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.full_name} ({self.email}) - {self.get_role_display()}"


class ApplicantProfile(models.Model):
    """Profile data for Jobseeker / Applicant."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='applicant_profile')
    resume_file = models.FileField(upload_to='uploads/resumes/', blank=True, null=True)
    skills = models.TextField(blank=True, null=True, help_text="Comma-separated skills")
    qualifications = models.TextField(blank=True, null=True)
    experience_years = models.IntegerField(default=0)
    education_level = models.CharField(max_length=150, blank=True, null=True)
    employability_score = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    profile_completed = models.BooleanField(default=False)
    profile_pic = models.ImageField(upload_to='uploads/profile_pics/', blank=True, null=True)

    def get_skills_list(self):
        if not self.skills:
            return []
        return [s.strip() for s in self.skills.split(',') if s.strip()]

    def calculate_completion(self):
        fields = [self.user.first_name, self.user.last_name, self.user.phone, self.skills, self.qualifications, self.education_level, self.resume_file]
        filled = sum(1 for f in fields if f)
        pct = int((filled / len(fields)) * 100)
        self.profile_completed = (pct >= 80)
        return pct

    def __str__(self):
        return f"Applicant Profile: {self.user.full_name}"


class EmployerProfile(models.Model):
    """Profile data for Company / Employer."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='employer_profile')
    company_name = models.CharField(max_length=255, blank=True, null=True)
    company_address = models.TextField(blank=True, null=True)
    company_website = models.CharField(max_length=255, blank=True, null=True)
    industry = models.CharField(max_length=150, blank=True, null=True)
    company_size = models.CharField(max_length=50, blank=True, null=True)
    company_logo = models.ImageField(upload_to='uploads/company_logos/', blank=True, null=True)

    @property
    def display_name(self):
        return self.company_name or self.user.full_name

    def __str__(self):
        return f"Employer Profile: {self.display_name}"
