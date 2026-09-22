from django import forms
from .models import JobPosting, EmployerRequest

EDUCATION_LEVEL_CHOICES = [
    ('', 'Select Minimum Education Level'),
    ('High School', 'High School Diploma'),
    ('Vocational', 'Vocational / Technical Diploma'),
    ('Associate', "Associate's Degree"),
    ("Bachelor's Degree", "Bachelor's Degree"),
    ("Master's Degree", "Master's Degree"),
    ('Doctorate / PhD', 'Doctorate / PhD'),
    ('Any', 'Any / No Preference'),
]

class TalentRequestForm(forms.ModelForm):
    education_level = forms.ChoiceField(
        choices=EDUCATION_LEVEL_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = EmployerRequest
        fields = [
            'title', 'employment_type', 'location', 'salary_range',
            'vacancies_count', 'skills_required', 'experience_required',
            'education_level', 'certifications', 'description'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Senior Full-Stack Python Developer', 'required': True}),
            'employment_type': forms.Select(attrs={'class': 'form-select'}),
            'location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Remote / Manila, Philippines / Hybrid'}),
            'salary_range': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. ₱70,000 - ₱100,000 / month'}),
            'vacancies_count': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'value': 1}),
            'skills_required': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Python, Django, PostgreSQL, Docker, React', 'required': True}),
            'experience_required': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 3+ years experience in backend web development'}),
            'certifications': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. AWS Certified Developer, PMP (optional)'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Outline the core responsibilities, day-to-day duties, and project scope...', 'required': True}),
        }


class JobPostingForm(forms.ModelForm):
    class Meta:
        model = JobPosting
        fields = [
            'employer', 'talent_request', 'title', 'employment_type', 'location', 'salary_range',
            'skills_required', 'min_experience_years', 'required_education', 'required_certifications',
            'target_qualifications', 'description', 'requirements', 'status'
        ]
        widgets = {
            'employer': forms.Select(attrs={'class': 'form-select'}),
            'talent_request': forms.Select(attrs={'class': 'form-select'}),
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Senior Full-Stack Developer', 'required': True}),
            'employment_type': forms.Select(attrs={'class': 'form-select'}),
            'location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Manila, Philippines / Hybrid / Remote'}),
            'salary_range': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. ₱50,000 - ₱80,000 / month'}),
            'skills_required': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Python, Django, React, SQL, Git'}),
            'min_experience_years': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'value': 0}),
            'required_education': forms.Select(choices=EDUCATION_LEVEL_CHOICES, attrs={'class': 'form-select'}),
            'required_certifications': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. AWS, Cisco, etc.'}),
            'target_qualifications': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. BS Computer Science, Information Technology'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Detailed job description and responsibilities...'}),
            'requirements': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Key requirements, qualifications, and prerequisites...'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }

