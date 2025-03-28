import os
import datetime
import json
from typing import Dict, Any, List, Optional
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/calendar']

def get_credentials():
    """Get valid user credentials from storage.
    
    Returns:
        Credentials, the obtained credential.
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_info(json.load(open('token.json')))
    
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                raise FileNotFoundError(
                    "You need to download credentials.json from Google Cloud Console")
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    
    return creds

def initialize_calendar_service():
    """Initialize the Calendar API service."""
    try:
        creds = get_credentials()
        service = build('calendar', 'v3', credentials=creds)
        return service
    except Exception as e:
        print(f"Failed to initialize Google Calendar: {str(e)}")
        return None

def create_calendar_event(task_data: Dict[str, Any]) -> Optional[str]:
    """
    Create an event in Google Calendar based on task data.
    
    Args:
        task_data: Task details including description, date, etc.
        
    Returns:
        event_id: ID of created event or None if failed
    """
    service = initialize_calendar_service()
    if not service:
        return None
        
    try:
        # Convert ISO date to datetime object
        start_time = datetime.datetime.fromisoformat(task_data['date'].replace('Z', '+00:00'))
        
        # Calculate end time based on estimated duration (default 30 minutes)
        duration = task_data.get('estimated_duration', 30)
        end_time = start_time + datetime.timedelta(minutes=duration)
        
        # Create event body
        event_body = {
            'summary': task_data['description'],
            'location': task_data.get('location', ''),
            'description': f"Priority: {task_data['priority']}\nCategory: {task_data['category']}",
            'start': {
                'dateTime': start_time.isoformat(),
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': end_time.isoformat(),
                'timeZone': 'UTC',
            },
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'email', 'minutes': 24 * 60},
                    {'method': 'popup', 'minutes': 15},
                ],
            },
        }
        
        # Add recurrence if specified
        if task_data.get('recurrence') and task_data['recurrence'] != 'none':
            freq = task_data['recurrence'].upper()
            event_body['recurrence'] = [f'RRULE:FREQ={freq}']
            
        # Add attendees if there are participants
        if task_data.get('participants') and len(task_data['participants']) > 0:
            # For simplicity, we're assuming participants might be email addresses
            # In a real app, you might have a contacts database to look up emails
            attendees = []
            for participant in task_data['participants']:
                if '@' in participant:
                    attendees.append({'email': participant})
                else:
                    # This is just a placeholder - in a real app you'd look up the email
                    attendees.append({'displayName': participant})
            
            if attendees:
                event_body['attendees'] = attendees
                
        # Insert the event
        event = service.events().insert(calendarId='primary', body=event_body).execute()
        return event.get('id')
        
    except Exception as e:
        print(f"Failed to create calendar event: {str(e)}")
        return None

def get_upcoming_events(days: int = 7) -> List[Dict[str, Any]]:
    """
    Retrieve upcoming events from Google Calendar.
    
    Args:
        days: Number of days to look ahead
        
    Returns:
        List of event dictionaries
    """
    service = initialize_calendar_service()
    if not service:
        return []
        
    try:
        # Calculate time bounds
        now = datetime.datetime.utcnow()
        time_min = now.isoformat() + 'Z'  # 'Z' indicates UTC time
        time_max = (now + datetime.timedelta(days=days)).isoformat() + 'Z'
        
        # Call the Calendar API
        events_result = service.events().list(
            calendarId='primary',
            timeMin=time_min,
            timeMax=time_max,
            maxResults=50,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        # Format events for our application
        formatted_events = []
        for event in events:
            # Skip events without start times
            if 'dateTime' not in event['start']:
                continue
                
            # Parse start time
            start_time = datetime.datetime.fromisoformat(
                event['start']['dateTime'].replace('Z', '+00:00'))
                
            # Format as task structure
            formatted_event = {
                'type': 'event',
                'description': event.get('summary', 'Unnamed event'),
                'date': event['start']['dateTime'],
                'priority': 'medium',  # Default priority
                'category': 'calendar',
                'location': event.get('location', ''),
                'source': 'google_calendar',
                'event_id': event['id']
            }
            
            # Try to extract priority and category from description if available
            if 'description' in event:
                desc_lines = event['description'].lower().split('\n')
                for line in desc_lines:
                    if line.startswith('priority:'):
                        priority = line.split(':', 1)[1].strip()
                        if priority in ['low', 'medium', 'high']:
                            formatted_event['priority'] = priority
                    elif line.startswith('category:'):
                        formatted_event['category'] = line.split(':', 1)[1].strip()
            
            formatted_events.append(formatted_event)
            
        return formatted_events
        
    except Exception as e:
        print(f"Failed to retrieve calendar events: {str(e)}")
        return []

def delete_calendar_event(event_id: str) -> bool:
    """
    Delete an event from Google Calendar.
    
    Args:
        event_id: ID of the event to delete
        
    Returns:
        Boolean indicating success
    """
    service = initialize_calendar_service()
    if not service:
        return False
        
    try:
        service.events().delete(calendarId='primary', eventId=event_id).execute()
        return True
    except Exception as e:
        print(f"Failed to delete calendar event: {str(e)}")
        return False

def update_calendar_event(event_id: str, task_data: Dict[str, Any]) -> bool:
    """
    Update an existing event in Google Calendar.
    
    Args:
        event_id: ID of the event to update
        task_data: Updated task details
        
    Returns:
        Boolean indicating success
    """
    service = initialize_calendar_service()
    if not service:
        return False
        
    try:
        # First get the existing event
        event = service.events().get(calendarId='primary', eventId=event_id).execute()
        
        # Update event fields
        event['summary'] = task_data['description']
        event['location'] = task_data.get('location', event.get('location', ''))
        event['description'] = f"Priority: {task_data['priority']}\nCategory: {task_data['category']}"
        
        # Update times
        start_time = datetime.datetime.fromisoformat(task_data['date'].replace('Z', '+00:00'))
        duration = task_data.get('estimated_duration', 30)
        end_time = start_time + datetime.timedelta(minutes=duration)
        
        event['start']['dateTime'] = start_time.isoformat()
        event['end']['dateTime'] = end_time.isoformat()
        
        # Update the event
        service.events().update(calendarId='primary', eventId=event_id, body=event).execute()
        return True
        
    except Exception as e:
        print(f"Failed to update calendar event: {str(e)}")
        return False