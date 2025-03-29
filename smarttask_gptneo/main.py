from fastapi import FastAPI, Request, Form, Depends, Query, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import json
import os
import re

from llm_agent import interpret_user_input, get_task_suggestions, generate_summary
from task_scheduler import TaskScheduler
from google_calendar import create_calendar_event, get_upcoming_events
from email_integration import send_email_reminder, send_task_report

# Flag to track if model has been loaded
model_loaded = False

app = FastAPI(title="SmartTask Productivity Assistant")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Initialize task scheduler
task_scheduler = TaskScheduler(tasks_file="tasks.json")

# Start the scheduler on app startup
@app.on_event("startup")
def startup_event():
    task_scheduler.start()

# Stop the scheduler on app shutdown
@app.on_event("shutdown")
def shutdown_event():
    task_scheduler.stop()

class TaskCreate(BaseModel):
    """Schema for task creation."""
    description: str
    date: str
    priority: str = "medium"
    category: str = "other"
    type: str = "task"
    location: Optional[str] = None
    participants: List[str] = []

class TaskUpdate(BaseModel):
    """Schema for task updates."""
    id: str
    description: Optional[str] = None
    date: Optional[str] = None
    priority: Optional[str] = None
    category: Optional[str] = None
    type: Optional[str] = None
    location: Optional[str] = None
    participants: Optional[List[str]] = None
    completed: Optional[bool] = None

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Render the main page."""
    global model_loaded
    tasks = task_scheduler.get_all_tasks()
    
    # Get upcoming tasks for next 7 days
    upcoming_tasks = task_scheduler.get_upcoming_tasks(days=7)
    
    # Get overdue tasks
    overdue_tasks = task_scheduler.get_overdue_tasks()
    
    # Generate summary only if there are tasks to summarize
    summary = "You have no upcoming tasks." if not tasks else generate_summary(tasks)
    
    # Get suggestions only if we have enough tasks - BUT DON'T DO THIS ON PAGE LOAD
    # This prevents the model from loading every time the page is visited
    suggestions = []
    
    # Check if Google Calendar is configured
    has_calendar = os.path.exists('token.json')
    
    return templates.TemplateResponse("index.html", {
        "request": request, 
        "tasks": tasks,
        "upcoming_tasks": upcoming_tasks,
        "overdue_tasks": overdue_tasks,
        "summary": summary,
        "suggestions": suggestions,
        "has_calendar": has_calendar
    })

@app.post("/submit-task", response_class=HTMLResponse)
async def submit_task(request: Request, message: str = Form(...)):
    """Process natural language input and create a task."""
    global model_loaded
    
    # Now we'll load the model when actually needed
    model_loaded = True
    
    task_data, raw_response = interpret_user_input(message)
    
    # Check for errors
    if "error" in task_data:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "error": f"⚠️ {task_data['error']}",
            "raw_response": raw_response,
            "tasks": task_scheduler.get_all_tasks()
        })
    
    # Save the task
    task_id = task_scheduler.add_task(task_data)
    
    # Add ALL tasks to Google Calendar, not just events
    calendar_event_id = None
    try:
        # Modified: Remove the type check so all tasks get added to calendar
        calendar_event_id = create_calendar_event(task_data)
        if calendar_event_id:
            task_data['calendar_event_id'] = calendar_event_id
            task_scheduler.update_task(task_data)
    except Exception as e:
        # Calendar integration is optional
        print(f"Calendar error: {str(e)}")
    
    # Now we can safely get suggestions since the model is already loaded
    suggestions = []
    tasks = task_scheduler.get_all_tasks()
    if len(tasks) >= 2 and model_loaded:
        suggestions = get_task_suggestions(tasks, count=3)
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "task": task_data,
        "task_id": task_id,
        "raw_response": raw_response,
        "calendar_event_id": calendar_event_id,
        "tasks": task_scheduler.get_all_tasks(),
        "upcoming_tasks": task_scheduler.get_upcoming_tasks(days=7),
        "overdue_tasks": task_scheduler.get_overdue_tasks(),
        "summary": generate_summary(tasks),
        "suggestions": suggestions,
        "has_calendar": os.path.exists('token.json')
    })

@app.post("/tasks/create", response_class=HTMLResponse)
async def create_task(
    request: Request,
    description: str = Form(...),
    date: str = Form(...),
    priority: str = Form("medium"),
    category: str = Form("other"),
    type: str = Form("task"),
    location: str = Form(None),
    participants: str = Form("")
):
    """Manually create a task."""
    # Convert participants string to list
    participants_list = []
    if participants:
        participants_list = [p.strip() for p in participants.split(',')]
    
    # Create task data
    task_data = {
        "description": description,
        "date": date,
        "priority": priority,
        "category": category,
        "type": type,
        "location": location,
        "participants": participants_list
    }
    
    # Save the task
    task_id = task_scheduler.add_task(task_data)
    
    # Add ALL tasks to Google Calendar, not just events
    try:
        # Modified: Remove the type check so all tasks get added to calendar
        calendar_event_id = create_calendar_event(task_data)
        if calendar_event_id:
            task_data['calendar_event_id'] = calendar_event_id
            task_scheduler.update_task(task_data)
    except Exception as e:
        print(f"Calendar error in create_task: {str(e)}")
    
    # Redirect to home page
    return RedirectResponse(url="/", status_code=303)

@app.post("/tasks/{task_id}/complete")
async def complete_task(task_id: str):
    """Mark a task as completed."""
    success = task_scheduler.complete_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "success"}

@app.post("/tasks/{task_id}/delete")
async def delete_task(task_id: str):
    """Delete a task."""
    success = task_scheduler.delete_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "success"}

@app.post("/tasks/{task_id}/update", response_class=HTMLResponse)
async def update_task(
    request: Request,
    task_id: str,
    description: str = Form(None),
    date: str = Form(None),
    priority: str = Form(None),
    category: str = Form(None),
    type: str = Form(None),
    location: str = Form(None),
    participants: str = Form(None)
):
    """Update a task."""
    # Get the existing task
    task = task_scheduler.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Update fields if provided
    if description:
        task['description'] = description
    if date:
        task['date'] = date
    if priority:
        task['priority'] = priority
    if category:
        task['category'] = category
    if type:
        task['type'] = type
    if location is not None:  # Allow empty string to clear location
        task['location'] = location
    if participants is not None:
        # Convert participants string to list
        task['participants'] = [p.strip() for p in participants.split(',') if p.strip()]
    
    # Update the task
    success = task_scheduler.update_task(task)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to update task")
    
    # If it has a calendar event, update the calendar
    if 'calendar_event_id' in task:
        try:
            from google_calendar import update_calendar_event
            update_calendar_event(task['calendar_event_id'], task)
        except Exception as e:
            print(f"Calendar update error: {str(e)}")
    # If it doesn't have a calendar event, create one
    else:
        try:
            calendar_event_id = create_calendar_event(task)
            if calendar_event_id:
                task['calendar_event_id'] = calendar_event_id
                task_scheduler.update_task(task)
        except Exception as e:
            print(f"Calendar creation error: {str(e)}")
    
    # Redirect to home page
    return RedirectResponse(url="/", status_code=303)

@app.get("/tasks", response_class=HTMLResponse)
async def get_tasks(
    request: Request,
    type: str = Query(None),
    priority: str = Query(None),
    category: str = Query(None),
    completed: bool = Query(None),
    days: int = Query(7)
):
    """Get tasks with optional filtering."""
    # Build criteria dictionary
    criteria = {}
    if type:
        criteria['type'] = type
    if priority:
        criteria['priority'] = priority
    if category:
        criteria['category'] = category
    if completed is not None:
        criteria['completed'] = completed
    
    # Get tasks based on criteria
    if criteria:
        tasks = task_scheduler.get_tasks_by_criteria(criteria)
    else:
        # Default to upcoming tasks
        tasks = task_scheduler.get_upcoming_tasks(days=days)
    
    return templates.TemplateResponse("tasks.html", {
        "request": request,
        "tasks": tasks,
        "type": type,
        "priority": priority,
        "category": category,
        "completed": completed,
        "days": days
    })

@app.get("/calendar", response_class=HTMLResponse)
async def get_calendar(request: Request, days: int = Query(14), setup: bool = Query(None)):
    """View calendar events."""
    try:
        if setup:
            # Redirect to setup page, which will redirect back after auth
            # This is handled by the Google API auth flow
            pass
        
        # Try to get events, but don't fail if calendar isn't set up
        try:
            events = get_upcoming_events(days=days)
            has_calendar = True
        except Exception as cal_error:
            print(f"Calendar error: {str(cal_error)}")
            events = []
            has_calendar = os.path.exists('token.json')
        
        # Add ALL tasks from our system to the calendar view, not just events
        tasks = task_scheduler.get_all_tasks()
        
        # If we have tasks, add them to the events list
        if tasks:
            for task in tasks:
                # Only add if not already from calendar and has a date
                if 'calendar_event_id' not in task and 'date' in task and not task.get('completed', False):
                    events.append({
                        'description': task.get('description', ''),
                        'date': task.get('date', ''),
                        'event_id': task.get('id', ''),
                        'priority': task.get('priority', 'medium'),
                        'location': task.get('location', ''),
                        'type': task.get('type', 'task')  # Include task type for display
                    })
        
        return templates.TemplateResponse("calendar.html", {
            "request": request,
            "events": events,
            "has_calendar": has_calendar,
            "days": days
        })
    except Exception as e:
        # Return a simpler page on error
        print(f"Calendar page error: {str(e)}")
        return templates.TemplateResponse("calendar.html", {
            "request": request,
            "events": [],
            "has_calendar": os.path.exists('token.json'),
            "days": days,
            "setup_error": str(e)
        })

@app.post("/send-reminder")
async def send_reminder(request: Request):
    data = await request.json()
    task = data.get("task")
    email = data.get("email")

    if not task or not email:
        return {"status": "error", "message": "Missing task or email"}

    task["participants"] = [email]
    success = send_email_reminder(task)
    
    if success:
        return {"status": "ok", "message": "Reminder sent"}
    else:
        return {"status": "error", "message": "Email sending failed"}

@app.post("/send-report")
async def send_report(email: str = Form(...)):
    """Send a task report to the specified email."""
    tasks = task_scheduler.get_all_tasks()
    success = send_task_report(email, tasks)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to send report")
    
    return {"status": "success"}

@app.get("/api/tasks")
async def api_get_tasks(
    type: str = Query(None),
    priority: str = Query(None),
    category: str = Query(None),
    completed: bool = Query(None),
    days: int = Query(7)
):
    """API endpoint to get tasks."""
    # Build criteria dictionary
    criteria = {}
    if type:
        criteria['type'] = type
    if priority:
        criteria['priority'] = priority
    if category:
        criteria['category'] = category
    if completed is not None:
        criteria['completed'] = completed
    
    # Get tasks based on criteria
    if criteria:
        tasks = task_scheduler.get_tasks_by_criteria(criteria)
    else:
        # Default to upcoming tasks
        tasks = task_scheduler.get_upcoming_tasks(days=days)
    
    return {"tasks": tasks}

@app.post("/api/tasks")
async def api_create_task(task: TaskCreate):
    """API endpoint to create a task."""
    task_data = task.dict()
    task_id = task_scheduler.add_task(task_data)
    
    # Add all tasks to Google Calendar
    try:
        calendar_event_id = create_calendar_event(task_data)
        if calendar_event_id:
            task_data['calendar_event_id'] = calendar_event_id
            task_data['id'] = task_id
            task_scheduler.update_task(task_data)
    except Exception as e:
        print(f"API calendar error: {str(e)}")
    
    return {"id": task_id, "task": task_scheduler.get_task(task_id)}

@app.put("/api/tasks/{task_id}")
async def api_update_task(task_id: str, task_update: TaskUpdate):
    """API endpoint to update a task."""
    # Get the existing task
    task = task_scheduler.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Update fields if provided
    update_data = task_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        if key != 'id' and value is not None:  # Skip 'id' and None values
            task[key] = value
    
    # Update the task
    success = task_scheduler.update_task(task)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to update task")
    
    # Update calendar if needed
    if 'calendar_event_id' in task:
        try:
            from google_calendar import update_calendar_event
            update_calendar_event(task['calendar_event_id'], task)
        except Exception as e:
            print(f"API update calendar error: {str(e)}")
    else:
        try:
            calendar_event_id = create_calendar_event(task)
            if calendar_event_id:
                task['calendar_event_id'] = calendar_event_id
                task_scheduler.update_task(task)
        except Exception as e:
            print(f"API create calendar error: {str(e)}")
    
    return {"task": task}

@app.delete("/api/tasks/{task_id}")
async def api_delete_task(task_id: str):
    """API endpoint to delete a task."""
    success = task_scheduler.delete_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "success"}

@app.get("/api/summary")
async def api_get_summary():
    """API endpoint to get a summary of tasks."""
    tasks = task_scheduler.get_all_tasks()
    summary = generate_summary(tasks)
    return {"summary": summary}

@app.get("/api/suggestions")
async def api_get_suggestions(count: int = Query(3)):
    """API endpoint to get task suggestions."""
    global model_loaded
    tasks = task_scheduler.get_all_tasks()
    
    if len(tasks) < 2 or not model_loaded:
        return {"suggestions": []}
    
    suggestions = get_task_suggestions(tasks, count=count)
    return {"suggestions": suggestions}

@app.post("/api/sync-calendar")
async def api_sync_calendar():
    """API endpoint to manually sync with Google Calendar."""
    try:
        new_count = task_scheduler._sync_with_calendar()
        return {"status": "success", "new_events": new_count}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/import-email-tasks")
async def api_import_email_tasks():
    """API endpoint to manually import tasks from email."""
    try:
        new_count = task_scheduler._import_tasks_from_email()
        return {"status": "success", "new_tasks": new_count}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)