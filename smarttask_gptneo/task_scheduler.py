import os
import json
import time
import threading
import schedule
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable

from google_calendar import create_calendar_event, get_upcoming_events
from email_integration import send_email_reminder, scan_inbox_for_tasks

class TaskScheduler:
    """Task scheduling and management system for the SmartTask assistant."""
    
    def __init__(self, tasks_file="tasks.json"):
        """Initialize the task scheduler."""
        self.tasks_file = tasks_file
        self.scheduler_thread = None
        self.running = False
        self.scheduled_reminders = set()  # Track already scheduled reminders
        
        # Ensure tasks file exists
        if not os.path.exists(tasks_file):
            with open(tasks_file, "w") as f:
                json.dump([], f)
    
    def start(self):
        """Start the scheduler in a background thread."""
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            print("Scheduler already running")
            return
            
        self.running = True
        self.scheduler_thread = threading.Thread(target=self._run_scheduler)
        self.scheduler_thread.daemon = True  # Thread will exit when main program exits
        self.scheduler_thread.start()
        print("Task scheduler started")
    
    def stop(self):
        """Stop the scheduler."""
        self.running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=1.0)
        print("Task scheduler stopped")
    
    def _run_scheduler(self):
        """Run the scheduler loop."""
        # Schedule recurring jobs
        
        # Check for approaching task deadlines every hour
        schedule.every(1).hour.do(self._check_approaching_tasks)
        
        # Check for new tasks from email every 2 hours
        schedule.every(2).hours.do(self._import_tasks_from_email)
        
        # Sync with Google Calendar every 3 hours
        schedule.every(3).hours.do(self._sync_with_calendar)
        
        # Daily cleanup at 1 AM
        schedule.every().day.at("01:00").do(self._cleanup_old_tasks)
        
        # Run the scheduler loop
        while self.running:
            schedule.run_pending()
            
            # Also check for immediate tasks (run more frequently)
            self._schedule_immediate_reminders()
            
            # Sleep for a bit to avoid overloading the CPU
            time.sleep(60)  # Check every minute
    
    def _check_approaching_tasks(self):
        """Check for tasks approaching their deadlines and send reminders."""
        tasks = self.get_all_tasks()
        now = datetime.now()
        
        # Look for tasks within the next 24 hours that haven't had reminders sent
        for task in tasks:
            # Skip tasks without dates or that have already been reminded
            if 'date' not in task or task.get('reminded', False):
                continue
                
            try:
                task_date = datetime.fromisoformat(task['date'].replace('Z', '+00:00'))
                
                # Use a naive datetime for both for comparison
                task_date_naive = task_date.replace(tzinfo=None)
                now_naive = now.replace(tzinfo=None)
                
                time_until = task_date_naive - now_naive
                
                # If task is within the next day but more than 30 minutes away
                if timedelta(0) < time_until < timedelta(days=1):
                    # Send reminder based on priority
                    if task['priority'] == 'high' or time_until < timedelta(hours=2):
                        print(f"Sending reminder for high priority task: {task['description']}")
                        send_email_reminder(task)
                        
                        # Update task to mark as reminded
                        task['reminded'] = True
                        self.update_task(task)
            except Exception as e:
                logging.warning(f"Error processing task reminder: {str(e)}")
    
    def _schedule_immediate_reminders(self):
        """Schedule reminders for tasks happening very soon."""
        try:
            tasks = self.get_all_tasks()
            now = datetime.now()
            
            # Look for tasks within the next 30 minutes
            for task in tasks:
                # Skip tasks without dates
                if 'date' not in task:
                    continue
                    
                try:
                    task_id = task.get('id', str(hash(json.dumps(task, sort_keys=True))))
                    
                    # Skip if already scheduled
                    if task_id in self.scheduled_reminders:
                        continue
                    
                    # Fix datetime handling to avoid timezone issues
                    try:
                        # Convert to naive datetimes for comparison
                        task_date_str = task['date'].replace('Z', '+00:00')
                        task_date = datetime.fromisoformat(task_date_str)
                        task_date_naive = task_date.replace(tzinfo=None)
                        now_naive = now.replace(tzinfo=None)
                        
                        time_until = task_date_naive - now_naive
                        
                        # If task is within 30 minutes
                        if timedelta(0) < time_until < timedelta(minutes=30):
                            # Schedule exact reminder
                            reminder_time = now + (time_until - timedelta(minutes=15))
                            delay_seconds = max(0, (reminder_time - now).total_seconds())
                            
                            if delay_seconds > 0:
                                # Schedule reminder
                                def send_reminder(task_obj):
                                    print(f"Sending immediate reminder for: {task_obj['description']}")
                                    send_email_reminder(task_obj)
                                    if task_id in self.scheduled_reminders:
                                        self.scheduled_reminders.remove(task_id)
                                
                                # Use threading to schedule the reminder
                                threading.Timer(
                                    delay_seconds, 
                                    send_reminder, 
                                    args=[task]
                                ).start()
                                
                                # Mark as scheduled
                                self.scheduled_reminders.add(task_id)
                                print(f"Scheduled reminder for task in {delay_seconds//60} minutes: {task['description']}")
                    except Exception as inner_e:
                        # Just log instead of printing to console
                        logging.warning(f"Error in time calculation: {str(inner_e)}")
                        continue
                
                except Exception as e:
                    logging.warning(f"Error scheduling task: {str(e)}")
        except Exception as outer_e:
            logging.warning(f"Error in scheduler main loop: {str(outer_e)}")
        
        # Return normally to avoid blocking the main thread
        return
    
    def _import_tasks_from_email(self):
        """Import tasks from email messages."""
        try:
            email_tasks = scan_inbox_for_tasks()
            
            if email_tasks:
                print(f"Found {len(email_tasks)} tasks from email")
                
                for task in email_tasks:
                    # Generate a unique ID for the task
                    task['id'] = f"email_{int(time.time())}_{hash(task['description'])}"
                    task['source'] = 'email'
                    
                    # Save the task
                    self.add_task(task)
                    
                    # If it's an event, also add to Google Calendar
                    if task['type'] == 'event':
                        try:
                            event_id = create_calendar_event(task)
                            if event_id:
                                task['calendar_event_id'] = event_id
                                self.update_task(task)
                        except:
                            pass  # Calendar integration is optional
            
            return len(email_tasks)
        except Exception as e:
            print(f"Error importing tasks from email: {str(e)}")
            return 0
    
    def _sync_with_calendar(self):
        """Sync tasks with Google Calendar."""
        try:
            # Get events from Google Calendar
            calendar_events = get_upcoming_events(days=14)
            
            if not calendar_events:
                return 0
                
            # Get all current tasks
            tasks = self.get_all_tasks()
            
            # Track existing event IDs
            existing_event_ids = set()
            for task in tasks:
                if 'calendar_event_id' in task:
                    existing_event_ids.add(task['calendar_event_id'])
            
            # Add new events from calendar that aren't in tasks yet
            new_count = 0
            for event in calendar_events:
                if event['event_id'] not in existing_event_ids:
                    # Convert to task format
                    task = {
                        'id': f"calendar_{int(time.time())}_{hash(event['description'])}",
                        'type': 'event',
                        'description': event['description'],
                        'date': event['date'],
                        'priority': event.get('priority', 'medium'),
                        'category': event.get('category', 'calendar'),
                        'location': event.get('location', ''),
                        'calendar_event_id': event['event_id'],
                        'source': 'google_calendar'
                    }
                    
                    # Save the task
                    self.add_task(task)
                    new_count += 1
            
            return new_count
        except Exception as e:
            print(f"Error syncing with Google Calendar: {str(e)}")
            return 0
    
    def _cleanup_old_tasks(self):
        """Clean up completed and old tasks."""
        tasks = self.get_all_tasks()
        now = datetime.now()
        updated_tasks = []
        
        for task in tasks:
            # Keep task if:
            # 1. It's completed and less than 30 days old
            # 2. It's not completed and not more than 7 days in the past
            # 3. It doesn't have a date (persistent task)
            
            if 'date' not in task:
                # Keep undated tasks
                updated_tasks.append(task)
                continue
                
            try:
                task_date = datetime.fromisoformat(task['date'].replace('Z', '+00:00'))
                task_date_naive = task_date.replace(tzinfo=None)
                now_naive = now.replace(tzinfo=None)
                
                if task.get('completed', False):
                    # For completed tasks, keep for 30 days
                    if now_naive - task_date_naive < timedelta(days=30):
                        updated_tasks.append(task)
                else:
                    # For incomplete tasks, keep if not more than 7 days in the past
                    if task_date_naive > now_naive - timedelta(days=7):
                        updated_tasks.append(task)
            except:
                # If date parsing fails, keep the task
                updated_tasks.append(task)
        
        # Save the filtered tasks
        with open(self.tasks_file, "w") as f:
            json.dump(updated_tasks, f, indent=2)
            
        return len(tasks) - len(updated_tasks)  # Return number of removed tasks
    
    def add_task(self, task_data: Dict[str, Any]) -> str:
        """
        Add a new task to the system.
        
        Args:
            task_data: Task details
            
        Returns:
            Task ID
        """
        tasks = self.get_all_tasks()
        
        # Generate ID if not present
        if 'id' not in task_data:
            task_data['id'] = f"task_{int(time.time())}_{hash(task_data['description'])}"
        
        # Add creation timestamp
        task_data['created_at'] = datetime.now().isoformat()
        
        # Add to tasks list
        tasks.append(task_data)
        
        # Save to file
        with open(self.tasks_file, "w") as f:
            json.dump(tasks, f, indent=2)
            
        return task_data['id']
    
    def update_task(self, task_data: Dict[str, Any]) -> bool:
        """
        Update an existing task.
        
        Args:
            task_data: Updated task details with ID
            
        Returns:
            Boolean indicating success
        """
        if 'id' not in task_data:
            return False
            
        tasks = self.get_all_tasks()
        
        # Find and update the task
        found = False
        for i, task in enumerate(tasks):
            if 'id' in task and task['id'] == task_data['id']:
                # Update the task
                tasks[i] = task_data
                found = True
                break
        
        if not found:
            return False
        
        # Save to file
        with open(self.tasks_file, "w") as f:
            json.dump(tasks, f, indent=2)
            
        return True
    
    def delete_task(self, task_id: str) -> bool:
        """
        Delete a task by ID.
        
        Args:
            task_id: ID of the task to delete
            
        Returns:
            Boolean indicating success
        """
        tasks = self.get_all_tasks()
        
        # Find the task
        task_to_delete = None
        for task in tasks:
            if 'id' in task and task['id'] == task_id:
                task_to_delete = task
                break
        
        if not task_to_delete:
            return False
            
        # Try to delete from Google Calendar if it's a calendar event
        if 'calendar_event_id' in task_to_delete:
            try:
                from google_calendar import delete_calendar_event
                delete_calendar_event(task_to_delete['calendar_event_id'])
            except:
                pass  # Calendar integration is optional
        
        # Remove from tasks list
        tasks = [task for task in tasks if task.get('id') != task_id]
        
        # Save to file
        with open(self.tasks_file, "w") as f:
            json.dump(tasks, f, indent=2)
            
        return True
    
    def complete_task(self, task_id: str) -> bool:
        """
        Mark a task as completed.
        
        Args:
            task_id: ID of the task to complete
            
        Returns:
            Boolean indicating success
        """
        tasks = self.get_all_tasks()
        
        # Find the task
        for task in tasks:
            if 'id' in task and task['id'] == task_id:
                # Mark as completed
                task['completed'] = True
                task['completed_at'] = datetime.now().isoformat()
                
                # Save to file
                with open(self.tasks_file, "w") as f:
                    json.dump(tasks, f, indent=2)
                    
                return True
        
        return False
    
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a task by ID.
        
        Args:
            task_id: ID of the task to retrieve
            
        Returns:
            Task dictionary or None if not found
        """
        tasks = self.get_all_tasks()
        
        for task in tasks:
            if 'id' in task and task['id'] == task_id:
                return task
        
        return None
    
    def get_all_tasks(self) -> List[Dict[str, Any]]:
        """
        Get all tasks.
        
        Returns:
            List of all tasks
        """
        if not os.path.exists(self.tasks_file):
            return []
            
        try:
            with open(self.tasks_file, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"Error decoding {self.tasks_file}, returning empty list")
            return []
    
    def get_tasks_by_date(self, date: datetime) -> List[Dict[str, Any]]:
        """
        Get tasks for a specific date.
        
        Args:
            date: Date to filter tasks by
            
        Returns:
            List of tasks on the specified date
        """
        date_str = date.strftime('%Y-%m-%d')
        tasks = self.get_all_tasks()
        result = []
        
        for task in tasks:
            if 'date' in task:
                try:
                    task_date = datetime.fromisoformat(task['date'].replace('Z', '+00:00'))
                    if task_date.strftime('%Y-%m-%d') == date_str:
                        result.append(task)
                except:
                    pass
        
        return result
    
    def get_tasks_by_criteria(self, criteria: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Get tasks matching specified criteria.
        
        Args:
            criteria: Dictionary of fields to match
            
        Returns:
            List of matching tasks
        """
        tasks = self.get_all_tasks()
        result = []
        
        for task in tasks:
            matches = True
            for key, value in criteria.items():
                if key not in task or task[key] != value:
                    matches = False
                    break
            
            if matches:
                result.append(task)
        
        return result
    
    def get_upcoming_tasks(self, days: int = 7) -> List[Dict[str, Any]]:
        """
        Get tasks scheduled for the next N days.
        
        Args:
            days: Number of days to look ahead
            
        Returns:
            List of upcoming tasks
        """
        now = datetime.now()
        end_date = now + timedelta(days=days)
        tasks = self.get_all_tasks()
        result = []
        
        for task in tasks:
            if 'date' in task and not task.get('completed', False):
                try:
                    task_date = datetime.fromisoformat(task['date'].replace('Z', '+00:00'))
                    # Make both naive for comparison
                    task_date_naive = task_date.replace(tzinfo=None)
                    now_naive = now.replace(tzinfo=None)
                    end_date_naive = end_date.replace(tzinfo=None)
                    
                    if now_naive <= task_date_naive <= end_date_naive:
                        result.append(task)
                except:
                    pass
        
        # Sort by date
        result.sort(key=lambda x: x['date'])
        
        return result
    
    def get_overdue_tasks(self) -> List[Dict[str, Any]]:
        """
        Get tasks that are overdue (past their due date).
        
        Returns:
            List of overdue tasks
        """
        now = datetime.now()
        tasks = self.get_all_tasks()
        result = []
        
        for task in tasks:
            if 'date' in task and not task.get('completed', False):
                try:
                    task_date = datetime.fromisoformat(task['date'].replace('Z', '+00:00'))
                    # Make both naive for comparison
                    task_date_naive = task_date.replace(tzinfo=None)
                    now_naive = now.replace(tzinfo=None)
                    
                    if task_date_naive < now_naive:
                        result.append(task)
                except:
                    pass
        
        # Sort by date (oldest first)
        result.sort(key=lambda x: x['date'])
        
        return result