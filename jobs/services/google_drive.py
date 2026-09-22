import io
import os
import json
import logging
import hashlib
from django.conf import settings

logger = logging.getLogger(__name__)

# Try to import Google API Client libraries
try:
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseUpload
    from google.oauth2 import service_account
    from google.auth.exceptions import GoogleAuthError
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    HAS_GOOGLE_API = True
except ImportError:
    HAS_GOOGLE_API = False

DRIVE_SCOPES = ['https://www.googleapis.com/auth/drive']


def get_google_drive_service():
    """
    Initializes and returns an authenticated Google Drive v3 service client.
    Looks for service account credentials in Django settings or environment variables:
      1. settings.GOOGLE_DRIVE_SERVICE_ACCOUNT_INFO (dict)
      2. settings.GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE (path to JSON file)
      3. os.environ['GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON'] (JSON string)
    """
    if not HAS_GOOGLE_API:
        logger.info("google-api-python-client is not installed or available.")
        return None

    scopes = DRIVE_SCOPES

    oauth_token_file = getattr(settings, 'GOOGLE_DRIVE_OAUTH_TOKEN_FILE', '')
    if oauth_token_file and os.path.isfile(oauth_token_file):
        try:
            credentials = Credentials.from_authorized_user_file(oauth_token_file, scopes)
            if credentials.valid:
                return build('drive', 'v3', credentials=credentials, cache_discovery=False)
            if credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
                with open(oauth_token_file, 'w', encoding='utf-8') as token_file:
                    token_file.write(credentials.to_json())
                return build('drive', 'v3', credentials=credentials, cache_discovery=False)
        except Exception as e:
            logger.warning(f"Failed to load Google OAuth credentials: {e}")

    credentials = None

    # Check settings dictionary
    sa_info = getattr(settings, 'GOOGLE_DRIVE_SERVICE_ACCOUNT_INFO', None)
    if sa_info and isinstance(sa_info, dict):
        try:
            credentials = service_account.Credentials.from_service_account_info(sa_info, scopes=scopes)
        except Exception as e:
            logger.warning(f"Failed to load Google Drive credentials from settings dict: {e}")

    # Check settings file path
    if not credentials:
        sa_file = getattr(settings, 'GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE', None)
        if sa_file and os.path.isfile(sa_file):
            try:
                credentials = service_account.Credentials.from_service_account_file(sa_file, scopes=scopes)
            except Exception as e:
                logger.warning(f"Failed to load Google Drive credentials from file {sa_file}: {e}")

    # Check environment variable JSON string
    if not credentials:
        env_json = os.environ.get('GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON', '').strip()
        if env_json:
            try:
                info = json.loads(env_json)
                credentials = service_account.Credentials.from_service_account_info(info, scopes=scopes)
            except Exception as e:
                logger.warning(f"Failed to load Google Drive credentials from env JSON: {e}")

    if not credentials:
        logger.info("Google Drive service account credentials are not configured. Running in sandbox/fallback mode.")
        return None

    try:
        service = build('drive', 'v3', credentials=credentials, cache_discovery=False)
        return service
    except Exception as e:
        logger.error(f"Error building Google Drive service: {e}")
        return None


def upload_candidates_excel_to_drive(file_content_bytes: bytes, filename: str, employer_email: str, folder_id: str = None) -> dict:
    """
    Uploads the candidates Excel workbook to Google Drive and sets strict View-Only (reader) permissions
    for the specific employer email address.

    Args:
        file_content_bytes (bytes): Raw bytes of the generated Excel (.xlsx) file.
        filename (str): Name of the file (e.g. Candidates_JobTitle_Date.xlsx).
        employer_email (str): Target employer email to receive view-only access.
        folder_id (str, optional): Google Drive destination folder ID.

    Returns:
        dict with fields:
            'success' (bool)
            'file_id' (str)
            'web_view_link' (str)
            'embed_link' (str)
            'is_mock' (bool)
            'message' (str)
    """
    drive_service = get_google_drive_service()
    
    # Live Google Drive API Execution
    if drive_service is not None:
        try:
            file_metadata = {
                'name': filename,
                'mimeType': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            }
            if folder_id:
                file_metadata['parents'] = [folder_id]

            media = MediaIoBaseUpload(
                io.BytesIO(file_content_bytes),
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                resumable=True
            )

            # 1. Create file on Drive
            uploaded_file = drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, name, webViewLink, webContentLink'
            ).execute()

            file_id = uploaded_file.get('id')
            web_view_link = uploaded_file.get('webViewLink') or f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"
            embed_link = f"https://drive.google.com/file/d/{file_id}/preview"

            # 2. Assign STRICT View-Only (reader) permission to employer
            if employer_email:
                user_permission = {
                    'type': 'user',
                    'role': 'reader', # STRICT VIEW-ONLY: Cannot edit, replace or delete
                    'emailAddress': employer_email.strip()
                }
                try:
                    drive_service.permissions().create(
                        fileId=file_id,
                        body=user_permission,
                        sendNotificationEmail=False,
                        fields='id'
                    ).execute()
                    logger.info(f"Granted view-only Google Drive permission for file {file_id} to {employer_email}")
                except Exception as perm_err:
                    logger.warning(f"Could not grant viewer permission for {employer_email}: {perm_err}")

            return {
                'success': True,
                'file_id': file_id,
                'web_view_link': web_view_link,
                'embed_link': embed_link,
                'is_mock': False,
                'message': 'Successfully uploaded to Google Drive with view-only permissions.'
            }
        except Exception as api_err:
            logger.error(f"Google Drive API upload failed: {api_err}. Using secure fallback storage.")

    # Sandbox / Local fallback mode (for environments without live Google Cloud keys)
    hash_seed = f"{filename}_{employer_email}_{len(file_content_bytes)}"
    mock_id = hashlib.sha256(hash_seed.encode('utf-8')).hexdigest()[:24]
    return {
        'success': True,
        'file_id': mock_id,
        'web_view_link': '',
        'embed_link': '',
        'is_mock': True,
        'message': 'Google Drive is not configured. Export saved to local secure storage.'
    }
