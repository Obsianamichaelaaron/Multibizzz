from django import forms
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from .models import User, ApplicantProfile, EmployerProfile


DISPOSABLE_EMAIL_DOMAINS = {
    '10minutemail.com', 'mailinator.com', 'tempmail.com', 'guerrillamail.com',
    'yopmail.com', 'trashmail.com', 'sharklasers.com', 'tmailor.com',
    'fakeinbox.com', 'maildrop.cc', 'getnada.com', 'tmpmail.org',
    'emailondeck.com', 'mailnesia.com', 'mintemail.com', 'throwawaymail.com',
    'dispostable.com', 'spam4.me', 'temp-mail.org', 'mailtemp.org', 'moakt.com'
}


def clean_email_value(value):
    email = (value or '').strip().lower()
    if not email:
        raise forms.ValidationError('Email is required.')

    try:
        validate_email(email)
    except ValidationError:
        raise forms.ValidationError('Enter a valid email address.')

    domain = email.split('@')[-1] if '@' in email else ''
    if domain in DISPOSABLE_EMAIL_DOMAINS:
        raise forms.ValidationError('Disposable or temporary email addresses are not allowed.')

    return email

class LoginForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={
        'class': 'form-control',
        'placeholder': 'Enter your email address',
        'required': True
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'form-control',
        'placeholder': 'Enter your password',
        'required': True
    }))

    def clean_email(self):
        email = self.cleaned_data.get('email')
        return (email or '').strip().lower()

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get('email')
        password = cleaned_data.get('password')

        if email and password:
            user = authenticate(username=email, password=password)
            if not user:
                raise forms.ValidationError("Invalid email address or password.")
            if user.status != 'active':
                raise forms.ValidationError(f"This account is {user.status}. Please contact support.")
            cleaned_data['user'] = user
        return cleaned_data


class ApplicantRegistrationForm(forms.ModelForm):
    resume_file = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.pdf,.docx,.doc'
        })
    )
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'form-control',
        'placeholder': 'Create password',
        'required': True
    }))
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'form-control',
        'placeholder': 'Confirm password',
        'required': True
    }))

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone', 'password']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name', 'required': True}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name', 'required': True}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email Address', 'required': True}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone Number (optional)'}),
        }

    def clean_email(self):
        normalized = clean_email_value(self.cleaned_data.get('email'))
        if User.objects.filter(email__iexact=normalized).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return normalized

    def clean(self):
        cleaned_data = super().clean()
        pwd = cleaned_data.get('password')
        confirm_pwd = cleaned_data.get('confirm_password')

        if pwd and confirm_pwd and pwd != confirm_pwd:
            raise forms.ValidationError("Passwords do not match.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = 'applicant'
        user.status = 'active'
        user.email = (self.cleaned_data.get('email') or '').strip().lower()
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
            profile, _ = ApplicantProfile.objects.get_or_create(user=user)
            if self.cleaned_data.get('resume_file'):
                profile.resume_file = self.cleaned_data['resume_file']
                profile.save(update_fields=['resume_file'])
        return user


class EmployerRegistrationForm(forms.ModelForm):
    company_name = forms.CharField(max_length=255, widget=forms.TextInput(attrs={
        'class': 'form-control',
        'placeholder': 'Company Name',
        'required': True
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'form-control',
        'placeholder': 'Create password',
        'required': True
    }))
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'form-control',
        'placeholder': 'Confirm password',
        'required': True
    }))

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone', 'password']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Contact Person First Name', 'required': True}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Contact Person Last Name', 'required': True}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Business Email Address', 'required': True}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone Number'}),
        }

    def clean_email(self):
        normalized = clean_email_value(self.cleaned_data.get('email'))
        if User.objects.filter(email__iexact=normalized).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return normalized

    def clean(self):
        cleaned_data = super().clean()
        pwd = cleaned_data.get('password')
        confirm_pwd = cleaned_data.get('confirm_password')

        if pwd and confirm_pwd and pwd != confirm_pwd:
            raise forms.ValidationError("Passwords do not match.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = 'employer'
        user.status = 'active'
        user.email = (self.cleaned_data.get('email') or '').strip().lower()
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
            company_name = self.cleaned_data.get('company_name')
            EmployerProfile.objects.get_or_create(user=user, defaults={'company_name': company_name})
        return user


class ApplicantProfileForm(forms.ModelForm):
    first_name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class': 'form-control'}))
    phone = forms.CharField(max_length=30, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))

    class Meta:
        model = ApplicantProfile
        fields = ['skills', 'qualifications', 'experience_years', 'education_level', 'resume_file']
        widgets = {
            'skills': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'e.g. Python, Django, React, SQL, Project Management'}),
            'qualifications': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. BS Computer Science'}),
            'experience_years': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 50}),
            'education_level': forms.Select(choices=[
                ('', 'Select Education Level'),
                ('High School', 'High School'),
                ('Vocational', 'Vocational / Diploma'),
                ('Associate', 'Associate Degree'),
                ('Bachelor', 'Bachelor Degree'),
                ('Master', 'Master Degree'),
                ('Doctorate', 'Doctorate / PhD'),
            ], attrs={'class': 'form-select'}),
            'resume_file': forms.FileInput(attrs={'class': 'form-control', 'accept': '.pdf,.docx,.doc'}),
        }


class EmployerProfileForm(forms.ModelForm):
    first_name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class': 'form-control'}))
    phone = forms.CharField(max_length=30, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))

    class Meta:
        model = EmployerProfile
        fields = ['company_name', 'company_address', 'company_website', 'industry', 'company_size', 'company_logo']
        widgets = {
            'company_name': forms.TextInput(attrs={'class': 'form-control'}),
            'company_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'company_website': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'https://example.com'}),
            'industry': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Information Technology'}),
            'company_size': forms.Select(choices=[
                ('', 'Select Company Size'),
                ('1-10 employees', '1-10 employees'),
                ('11-50 employees', '11-50 employees'),
                ('51-200 employees', '51-200 employees'),
                ('201-500 employees', '201-500 employees'),
                ('500+ employees', '500+ employees'),
            ], attrs={'class': 'form-select'}),
            'company_logo': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
        }
