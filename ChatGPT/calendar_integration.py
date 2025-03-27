import datetime
import os.path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Scopes define the permissions (read/write calendar)
SCOPES = ['https://www.googleapis.com/auth/calendar']

def get_calendar_service():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    else:
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    service = build('calendar', 'v3', credentials=creds)
    return service

def create_calendar_event(task):
    service = get_calendar_service()

    # Build event
    event = {
        'summary': task.get("description", "Untitled Task"),
        'start': {
            'dateTime': task.get("datetime"),
            'timeZone': 'UTC',
        },
        'end': {
            'dateTime': (datetime.datetime.fromisoformat(task["datetime"]) + datetime.timedelta(hours=1)).isoformat(),
            'timeZone': 'UTC',
        },
    }

    event = service.events().insert(calendarId='primary', body=event).execute()
    return event.get("htmlLink")
