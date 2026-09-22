from django.test import TestCase

from accounts.forms import ApplicantRegistrationForm


class EmailValidationTests(TestCase):
    def test_rejects_disposable_email_domains(self):
        form = ApplicantRegistrationForm(
            data={
                'first_name': 'Jane',
                'last_name': 'Doe',
                'email': 'jane@yopmail.com',
                'phone': '1234567890',
                'password': 'StrongPass123!',
                'confirm_password': 'StrongPass123!',
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)
        self.assertIn('disposable', str(form.errors['email']).lower())

    def test_accepts_real_email_domains(self):
        form = ApplicantRegistrationForm(
            data={
                'first_name': 'Jane',
                'last_name': 'Doe',
                'email': 'jane@gmail.com',
                'phone': '1234567890',
                'password': 'StrongPass123!',
                'confirm_password': 'StrongPass123!',
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
