from google.oauth2 import service_account
from googleapiclient.discovery import build
import logging


logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/drive.file']
SERVICE_ACCOUNT_FILE = './credentials.json'
FOLDER_ID = '1IxnCGa_dBfLaLHVZ8_jD5PGXsxzMNB1D'


def test_drive_service():
    try:
        # Initialize credentials and drive service
        credentials = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES
        )
        logger.info(f"Credentials initialized successfully:{credentials}")
        drive_service = build('drive', 'v3', credentials=credentials)

        # List files in the folder
        query = f"'{FOLDER_ID}' in parents"
        results = drive_service.files().list(
            q=query, pageSize=10, fields="files(id, name)").execute()
        files = results.get('files', [])
        if not files:
            print("No files found.")
        else:
            print("Files in folder:")
            for file in files:
                print(f"Name: {file['name']}, ID: {file['id']}")
    except Exception as e:
        print(f"Google Drive API error: {e}")


test_drive_service()
