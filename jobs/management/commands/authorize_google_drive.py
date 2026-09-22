from django.conf import settings
from django.core.management.base import BaseCommand
from google_auth_oauthlib.flow import InstalledAppFlow

from jobs.services.google_drive import DRIVE_SCOPES


class Command(BaseCommand):
    help = 'Authorize this app to upload candidate exports to Google Drive.'

    def handle(self, *args, **options):
        flow = InstalledAppFlow.from_client_secrets_file(
            settings.GOOGLE_DRIVE_OAUTH_CREDENTIALS_FILE,
            DRIVE_SCOPES,
        )
        credentials = flow.run_local_server(port=0, prompt='consent')
        with open(settings.GOOGLE_DRIVE_OAUTH_TOKEN_FILE, 'w', encoding='utf-8') as token_file:
            token_file.write(credentials.to_json())
        self.stdout.write(self.style.SUCCESS('Google Drive authorization saved successfully.'))
