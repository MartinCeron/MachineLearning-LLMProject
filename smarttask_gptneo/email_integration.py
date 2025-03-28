import os
import smtplib
import imaplib
import email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
import re
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime, timedelta

# Email configuration
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'true').lower() == 'true'
EMAIL_USERNAME = os.environ.get('EMAIL_USERNAME', '')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD', '')

def format_date_for_display(date_str: str) -> str:
    """Format ISO date string for display in emails."""
    try:
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return dt.strftime("%A, %B %d, %Y at %I:%M %p")
    except:
        return date_str

def send_email_reminder(task_data: Dict[str, Any]) -> bool:
    """
    Send an email reminder for a task.
    
    Args:
        task_data: Task details including description, date, etc.
        
    Returns:
        Boolean indicating success
    """
    if not EMAIL_USERNAME or not EMAIL_PASSWORD:
        print("Email credentials not configured")
        return False
    
    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = EMAIL_USERNAME
        
        # Set recipient
        if 'participants' in task_data and task_data['participants']:
            # Use first participant as recipient if it looks like an email
            recipient = task_data['participants'][0]
            if '@' not in recipient:
                recipient = EMAIL_USERNAME  # Fallback to self if not an email
        else:
            recipient = EMAIL_USERNAME  # Send to self if no participants
            
        msg['To'] = recipient
        msg['Subject'] = f"Reminder: {task_data['description']}"
        msg['Date'] = formatdate(localtime=True)
        
        # Create email body
        email_body = f"""
        <html>
        <body>
            <h2>Task Reminder</h2>
            <p><strong>Task:</strong> {task_data['description']}</p>
            <p><strong>Date:</strong> {format_date_for_display(task_data['date'])}</p>
            <p><strong>Priority:</strong> {task_data['priority'].capitalize()}</p>
            <p><strong>Category:</strong> {task_data['category'].capitalize()}</p>
        """
        
        # Add location if available
        if task_data.get('location'):
            email_body += f"<p><strong>Location:</strong> {task_data['location']}</p>"
            
        # Add participants if available
        if task_data.get('participants') and len(task_data['participants']) > 1:
            participants_str = ", ".join(task_data['participants'][1:])  # Skip first one (recipient)
            email_body += f"<p><strong>Participants:</strong> {participants_str}</p>"
            
        # Close the HTML
        email_body += """
        <p>This is an automated reminder from your SmartTask Assistant.</p>
        </body>
        </html>
        """
        
        # Attach body and send
        msg.attach(MIMEText(email_body, 'html'))
        
        with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
            if EMAIL_USE_TLS:
                server.starttls()
            server.login(EMAIL_USERNAME, EMAIL_PASSWORD)
            server.send_message(msg)
            
        return True
        
    except Exception as e:
        print(f"Failed to send email: {str(e)}")
        return False

def scan_inbox_for_tasks() -> List[Dict[str, Any]]:
    """
    Scan email inbox for messages that might contain tasks.
    
    Returns:
        List of potential task dictionaries extracted from emails
    """
    if not EMAIL_USERNAME or not EMAIL_PASSWORD:
        print("Email credentials not configured")
        return []
        
    tasks = []
    
    try:
        # Connect to inbox
        mail = imaplib.IMAP4_SSL(EMAIL_HOST)
        mail.login(EMAIL_USERNAME, EMAIL_PASSWORD)
        mail.select('inbox')
        
        # Search for recent unread emails
        date = (datetime.now() - timedelta(days=3)).strftime("%d-%b-%Y")
        status, data = mail.search(None, f'(UNSEEN SINCE {date})')
        
        if status != 'OK':
            print("No messages found")
            return []
            
        # Process each email
        for num in data[0].split():
            status, data = mail.fetch(num, '(RFC822)')
            if status != 'OK':
                continue
                
            raw_email = data[0][1]
            email_message = email.message_from_bytes(raw_email)
            
            # Extract subject and sender
            subject = email_message.get('Subject', '')
            sender = email.utils.parseaddr(email_message.get('From', ''))[1]
            
            # Skip if doesn't look task-related
            if not any(keyword in subject.lower() for keyword in 
                       ['task', 'reminder', 'meeting', 'appointment', 'schedule', 'todo']):
                continue
                
            # Extract body content
            body = ""
            if email_message.is_multipart():
                for part in email_message.walk():
                    content_type = part.get_content_type()
                    if content_type == 'text/plain' or content_type == 'text/html':
                        try:
                            body = part.get_payload(decode=True).decode()
                            break
                        except:
                            pass
            else:
                body = email_message.get_payload(decode=True).decode()
                
            # Extract potential task info using regex
            task = extract_task_from_email(subject, body, sender)
            if task:
                tasks.append(task)
                
        mail.close()
        mail.logout()
        
    except Exception as e:
        print(f"Failed to scan inbox: {str(e)}")
        
    return tasks

def extract_task_from_email(subject: str, body: str, sender: str) -> Optional[Dict[str, Any]]:
    """
    Extract task information from email content.
    
    Args:
        subject: Email subject
        body: Email body content
        sender: Email sender
        
    Returns:
        Task dictionary or None if no task identified
    """
    # Basic template for task
    task = {
        'type': 'task',
        'description': subject,
        'priority': 'medium',
        'category': 'email',
        'participants': [sender],
        'source': 'email'
    }
    
    # Strip HTML if present
    if '<html' in body.lower():
        # Very simple HTML stripping - in production you'd use a proper HTML parser
        body = re.sub('<[^<]+?>', ' ', body)
    
    # Look for date/time in the body
    date_patterns = [
        r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]* \d{1,2}(st|nd|rd|th)?,? \d{4}',
        r'\d{1,2}/\d{1,2}/\d{2,4}',
        r'\d{4}-\d{2}-\d{2}',
        r'(monday|tuesday|wednesday|thursday|friday|saturday|sunday)',
        r'(tomorrow|next week)'
    ]
    
    time_patterns = [
        r'\d{1,2}:\d{2}\s*(am|pm)',
        r'\d{1,2}\s*(am|pm)'
    ]
    
    # Try to find a date
    date_found = None
    for pattern in date_patterns:
        matches = re.search(pattern, body.lower())
        if matches:
            date_found = matches.group(0)
            break
            
    # Try to find a time
    time_found = None
    for pattern in time_patterns:
        matches = re.search(pattern, body.lower())
        if matches:
            time_found = matches.group(0)
            break
            
    # Set a default date/time if none found
    if not date_found:
        # Default to tomorrow at 9am
        tomorrow = datetime.now() + timedelta(days=1)
        task['date'] = tomorrow.replace(hour=9, minute=0, second=0).isoformat() + 'Z'
    else:
        # This is a simplified version - in production you'd use a more robust date parser
        try:
            # Very basic parsing
            now = datetime.now()
            
            if 'tomorrow' in date_found:
                task_date = now + timedelta(days=1)
            elif 'next week' in date_found:
                task_date = now + timedelta(days=7)
            elif date_found in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']:
                # Calculate days until next occurrence of this weekday
                day_map = {'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3, 
                          'friday': 4, 'saturday': 5, 'sunday': 6}
                target_day = day_map[date_found]
                days_ahead = (target_day - now.weekday()) % 7
                if days_ahead == 0:  # Today, so use next week
                    days_ahead = 7
                task_date = now + timedelta(days=days_ahead)
            else:
                # Try to parse a date string - very basic implementation
                # In a real app, you'd use a more robust date parser
                task_date = now  # Default to today if parsing fails
                
            # Set time if found
            hour, minute = 9, 0  # Default time
            if time_found:
                if ':' in time_found:
                    time_parts = re.search(r'(\d{1,2}):(\d{2})\s*(am|pm)', time_found.lower())
                    if time_parts:
                        hour = int(time_parts.group(1))
                        minute = int(time_parts.group(2))
                        if time_parts.group(3) == 'pm' and hour < 12:
                            hour += 12
                else:
                    time_parts = re.search(r'(\d{1,2})\s*(am|pm)', time_found.lower())
                    if time_parts:
                        hour = int(time_parts.group(1))
                        if time_parts.group(2) == 'pm' and hour < 12:
                            hour += 12
                
            task_date = task_date.replace(hour=hour, minute=minute, second=0)
            task['date'] = task_date.isoformat() + 'Z'
                
        except Exception as e:
            print(f"Date parsing error: {str(e)}")
            # Default to tomorrow at 9am
            tomorrow = datetime.now() + timedelta(days=1)
            task['date'] = tomorrow.replace(hour=9, minute=0, second=0).isoformat() + 'Z'
    
    # Look for priority keywords
    priority_words = {
        'high': ['urgent', 'important', 'critical', 'asap', 'high priority'],
        'low': ['low priority', 'whenever', 'if you have time', 'not urgent']
    }
    
    for priority, keywords in priority_words.items():
        if any(keyword in body.lower() for keyword in keywords):
            task['priority'] = priority
            break
    
    # Look for categories
    category_patterns = [
        (r'\b(work|job|office|business|project)\b', 'work'),
        (r'\b(personal|home|family|house)\b', 'personal'),
        (r'\b(health|doctor|medical|appointment|workout|exercise)\b', 'health'),
        (r'\b(finance|money|bank|payment|bill)\b', 'finance'),
        (r'\b(education|study|class|course|learn|school)\b', 'education')
    ]
    
    for pattern, category in category_patterns:
        if re.search(pattern, body.lower()):
            task['category'] = category
            break
    
    # Extract potential participants
    # This is a simplified version - in a real app you'd use NLP to extract names
    participant_pattern = r'with ([\w\s]+)'
    participant_match = re.search(participant_pattern, body.lower())
    if participant_match:
        potential_participant = participant_match.group(1).strip()
        if potential_participant and potential_participant not in ['me', 'you', 'a']:
            task['participants'].append(potential_participant)
    
    return task

def send_task_report(email: str, tasks: List[Dict[str, Any]]) -> bool:
    """
    Send a summary report of tasks to a specified email.
    
    Args:
        email: Email address to send the report to
        tasks: List of tasks to include in the report
        
    Returns:
        Boolean indicating success
    """
    if not EMAIL_USERNAME or not EMAIL_PASSWORD:
        print("Email credentials not configured")
        return False
    
    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = EMAIL_USERNAME
        msg['To'] = email
        msg['Subject'] = f"SmartTask Assistant - Task Report"
        msg['Date'] = formatdate(localtime=True)
        
        # Group tasks by date
        from collections import defaultdict
        date_groups = defaultdict(list)
        for task in tasks:
            try:
                task_date = datetime.fromisoformat(task['date'].replace('Z', '+00:00'))
                date_str = task_date.strftime('%Y-%m-%d')
                date_groups[date_str].append(task)
            except (ValueError, KeyError):
                # If date parsing fails, group under "Undated"
                date_groups["Undated"].append(task)
        
        # Create email body
        email_body = """
        <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; }
                h1 { color: #2c3e50; }
                h2 { color: #3498db; }
                table { border-collapse: collapse; width: 100%; }
                th, td { padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }
                th { background-color: #f2f2f2; }
                .high { color: #e74c3c; }
                .medium { color: #f39c12; }
                .low { color: #27ae60; }
            </style>
        </head>
        <body>
            <h1>SmartTask Assistant - Task Report</h1>
        """
        
        # Today's date for reference
        today = datetime.now().strftime('%Y-%m-%d')
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        
        # Add today's tasks
        if today in date_groups:
            email_body += "<h2>Today's Tasks</h2>"
            email_body += "<table><tr><th>Task</th><th>Time</th><th>Priority</th><th>Category</th></tr>"
            
            for task in date_groups[today]:
                try:
                    task_time = datetime.fromisoformat(task['date'].replace('Z', '+00:00')).strftime('%I:%M %p')
                except:
                    task_time = "All day"
                    
                email_body += f"""
                <tr>
                    <td>{task['description']}</td>
                    <td>{task_time}</td>
                    <td class="{task['priority']}">{task['priority'].capitalize()}</td>
                    <td>{task['category'].capitalize()}</td>
                </tr>
                """
            
            email_body += "</table>"
        
        # Add tomorrow's tasks
        if tomorrow in date_groups:
            email_body += "<h2>Tomorrow's Tasks</h2>"
            email_body += "<table><tr><th>Task</th><th>Time</th><th>Priority</th><th>Category</th></tr>"
            
            for task in date_groups[tomorrow]:
                try:
                    task_time = datetime.fromisoformat(task['date'].replace('Z', '+00:00')).strftime('%I:%M %p')
                except:
                    task_time = "All day"
                    
                email_body += f"""
                <tr>
                    <td>{task['description']}</td>
                    <td>{task_time}</td>
                    <td class="{task['priority']}">{task['priority'].capitalize()}</td>
                    <td>{task['category'].capitalize()}</td>
                </tr>
                """
            
            email_body += "</table>"
        
        # Add upcoming tasks (next 7 days)
        upcoming_days = sorted([d for d in date_groups.keys() 
                              if d not in [today, tomorrow, "Undated"] 
                              and d <= (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')])
        
        if upcoming_days:
            email_body += "<h2>Upcoming Tasks</h2>"
            
            for date_str in upcoming_days:
                try:
                    date_obj = datetime.fromisoformat(date_str + 'T00:00:00')
                    day_name = date_obj.strftime('%A, %B %d')
                    
                    email_body += f"<h3>{day_name}</h3>"
                    email_body += "<table><tr><th>Task</th><th>Time</th><th>Priority</th><th>Category</th></tr>"
                    
                    for task in date_groups[date_str]:
                        try:
                            task_time = datetime.fromisoformat(task['date'].replace('Z', '+00:00')).strftime('%I:%M %p')
                        except:
                            task_time = "All day"
                            
                        email_body += f"""
                        <tr>
                            <td>{task['description']}</td>
                            <td>{task_time}</td>
                            <td class="{task['priority']}">{task['priority'].capitalize()}</td>
                            <td>{task['category'].capitalize()}</td>
                        </tr>
                        """
                    
                    email_body += "</table>"
                except:
                    pass
        
        # Close HTML
        email_body += """
            <p>This is an automated report from your SmartTask Assistant.</p>
        </body>
        </html>
        """
        
        # Attach body and send
        msg.attach(MIMEText(email_body, 'html'))
        
        with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
            if EMAIL_USE_TLS:
                server.starttls()
            server.login(EMAIL_USERNAME, EMAIL_PASSWORD)
            server.send_message(msg)
            
        return True
        
    except Exception as e:
        print(f"Failed to send task report: {str(e)}")
        return False