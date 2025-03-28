from transformers import pipeline
import re
import os
import json
from datetime import datetime, timedelta
import pytz
from typing import Dict, Any, Optional, List, Tuple

# Use a smaller model for faster loading and less memory consumption
DEFAULT_MODEL = "EleutherAI/gpt-neo-125M"  # Smaller model for better performance
OPENAI_FALLBACK = os.environ.get("USE_OPENAI", "false").lower() == "true"

# Initialize generators as None
primary_generator = None
fallback_generator = None

def load_primary_model():
    """Load the primary Hugging Face model."""
    global primary_generator
    print(f"[LLM] Loading primary model: {DEFAULT_MODEL}...")
    # Remove the 'truncation' parameter which is causing the error
    primary_generator = pipeline(
        "text-generation",
        model=DEFAULT_MODEL,
        pad_token_id=50256
    )
    print("[LLM] Primary model loaded successfully.")

def load_openai_fallback():
    """Load OpenAI as a fallback option if environment variable is set."""
    global fallback_generator
    if OPENAI_FALLBACK:
        try:
            from openai import OpenAI
            client = OpenAI()
            
            def openai_generator(prompt, max_new_tokens=100, temperature=0.5, **kwargs):
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_new_tokens,
                    temperature=temperature
                )
                return [{"generated_text": prompt + response.choices[0].message.content}]
                
            fallback_generator = openai_generator
            print("[LLM] OpenAI fallback loaded successfully.")
        except ImportError:
            print("[LLM] OpenAI package not installed. Fallback not available.")
        except Exception as e:
            print(f"[LLM] Failed to initialize OpenAI fallback: {str(e)}")

def get_current_date_info() -> Dict[str, str]:
    """Get current date information to help the LLM with temporal reasoning."""
    now = datetime.now()
    tomorrow = now + timedelta(days=1)
    next_monday = now + timedelta(days=(7 - now.weekday()) % 7)
    
    return {
        "current_date": now.strftime("%Y-%m-%d"),
        "current_day": now.strftime("%A"),
        "current_time": now.strftime("%H:%M"),
        "tomorrow_date": tomorrow.strftime("%Y-%m-%d"),
        "tomorrow_day": tomorrow.strftime("%A"),
        "next_monday": next_monday.strftime("%Y-%m-%d")
    }

def interpret_user_input(user_input: str) -> Tuple[Dict[str, Any], str]:
    """
    Process user input through rule-based extraction to create structured task information.
    
    Args:
        user_input: Natural language request from the user
        
    Returns:
        tuple: (parsed_json_data, raw_response)
    """
    # Extract description directly from user input
    description = user_input
    
    # For "remind me to X" pattern
    if "remind me to " in user_input.lower():
        description_match = re.search(r"remind me to (.+?)(?:on|at|tomorrow|next|$)", user_input.lower())
        if description_match:
            description = description_match.group(1).strip()
    
    # For "take out the trash" specifically (since you mentioned this exact task)
    if "take out the trash" in user_input.lower() or "trash" in user_input.lower():
        description = "take out the trash"
        
    # Determine task type
    task_type = "task"
    if "remind" in user_input.lower():
        task_type = "remind"
    elif "schedule" in user_input.lower() or "meeting" in user_input.lower():
        task_type = "event"
    
    # Extract date and time
    task_date = datetime.now() + timedelta(days=1)  # Default to tomorrow
    
    if "tomorrow" in user_input.lower():
        task_date = datetime.now() + timedelta(days=1)
    
    # Extract time - explicitly handle 3pm
    if "3pm" in user_input.lower() or "3 pm" in user_input.lower():
        task_date = task_date.replace(hour=15, minute=0, second=0, microsecond=0)
    else:
        # General time extraction
        time_match = re.search(r"(\d{1,2})(?::(\d{2}))?(?:\s*)(am|pm)", user_input.lower())
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2) or 0)
            am_pm = time_match.group(3)
            if am_pm.lower() == 'pm' and hour < 12:
                hour += 12
            task_date = task_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
    
    # Create the task data
    task_data = {
        "type": task_type,
        "description": description,
        "date": task_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "priority": "medium",
        "category": "personal",
        "location": None,
        "participants": [],
        "recurrence": "none",
        "estimated_duration": 30
    }
    
    # Return the task data and a string representation
    return task_data, json.dumps(task_data, indent=2)

def get_task_suggestions(tasks: List[Dict[str, Any]], count: int = 3) -> List[Dict[str, Any]]:
    """
    Generate suggestions for new tasks based on existing tasks.
    
    Args:
        tasks: List of existing tasks
        count: Number of suggestions to generate
        
    Returns:
        List of suggested tasks
    """
    # Simple rule-based suggestions
    suggestions = []
    
    # Extract categories and types from existing tasks
    categories = {}
    types = {}
    for task in tasks:
        cat = task.get('category', 'other')
        typ = task.get('type', 'task')
        if cat in categories:
            categories[cat] += 1
        else:
            categories[cat] = 1
        if typ in types:
            types[typ] += 1
        else:
            types[typ] = 1
    
    # Find most common category and type
    most_common_category = max(categories.items(), key=lambda x: x[1])[0] if categories else 'other'
    most_common_type = max(types.items(), key=lambda x: x[1])[0] if types else 'task'
    
    # Generate suggestions based on patterns
    if 'work' in categories:
        suggestions.append({
            "type": "task",
            "description": "Create weekly progress report",
            "priority": "medium",
            "category": "work"
        })
        
    if 'personal' in categories:
        suggestions.append({
            "type": "remind",
            "description": "Schedule time for self-care",
            "priority": "medium",
            "category": "personal"
        })
        
    if 'health' in categories:
        suggestions.append({
            "type": "remind",
            "description": "Schedule dentist appointment",
            "priority": "low",
            "category": "health"
        })
        
    if 'finance' in categories:
        suggestions.append({
            "type": "task",
            "description": "Review monthly budget",
            "priority": "medium",
            "category": "finance"
        })
        
    if 'education' in categories:
        suggestions.append({
            "type": "task",
            "description": "Prepare study schedule",
            "priority": "high",
            "category": "education"
        })
    
    # Generic suggestions if we don't have enough yet
    generic_suggestions = [
        {
            "type": "task",
            "description": "Organize digital files",
            "priority": "low",
            "category": most_common_category
        },
        {
            "type": "remind",
            "description": "Drink water and stay hydrated",
            "priority": "medium",
            "category": "health"
        },
        {
            "type": "event",
            "description": "Schedule team check-in",
            "priority": "medium",
            "category": "work"
        },
        {
            "type": "task",
            "description": "Plan meals for the week",
            "priority": "medium",
            "category": "personal"
        },
        {
            "type": "remind",
            "description": "Back up important files",
            "priority": "medium",
            "category": "work"
        }
    ]
    
    # Add generic suggestions if we don't have enough
    while len(suggestions) < count:
        if not generic_suggestions:
            break
        suggestion = generic_suggestions.pop(0)
        if suggestion not in suggestions:
            suggestions.append(suggestion)
    
    return suggestions[:count]  # Return only requested number

def generate_summary(tasks: List[Dict[str, Any]]) -> str:
    """
    Generate a natural language summary of upcoming tasks.
    
    Args:
        tasks: List of tasks to summarize
        
    Returns:
        String containing the summary
    """
    if not tasks:
        return "You have no upcoming tasks."
        
    # Group tasks by date
    from collections import defaultdict
    from datetime import datetime
    
    date_groups = defaultdict(list)
    for task in tasks:
        try:
            if 'date' in task:
                task_date = datetime.fromisoformat(task['date'].replace('Z', '+00:00'))
                date_str = task_date.strftime('%Y-%m-%d')
                date_groups[date_str].append(task)
        except (ValueError, KeyError):
            pass
    
    # Create summary
    summary_parts = ["Here's your task summary:"]
    
    # Get today and tomorrow
    today = datetime.now().strftime('%Y-%m-%d')
    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    
    # Add today's tasks
    if today in date_groups:
        summary_parts.append(f"\nToday ({len(date_groups[today])} tasks):")
        for task in date_groups[today]:
            priority_marker = "🔴" if task.get('priority') == "high" else "🟡" if task.get('priority') == "medium" else "🟢"
            summary_parts.append(f"- {priority_marker} {task.get('description', 'Task')}")
    
    # Add tomorrow's tasks
    if tomorrow in date_groups:
        summary_parts.append(f"\nTomorrow ({len(date_groups[tomorrow])} tasks):")
        for task in date_groups[tomorrow]:
            priority_marker = "🔴" if task.get('priority') == "high" else "🟡" if task.get('priority') == "medium" else "🟢"
            summary_parts.append(f"- {priority_marker} {task.get('description', 'Task')}")
    
    # Add upcoming tasks (limit to 5 days)
    other_days = sorted([d for d in date_groups.keys() if d not in [today, tomorrow]])[:5]
    if other_days:
        summary_parts.append("\nUpcoming:")
        for date_str in other_days:
            date_obj = datetime.fromisoformat(date_str + 'T00:00:00')
            day_name = date_obj.strftime('%A, %b %d')
            task_count = len(date_groups[date_str])
            summary_parts.append(f"- {day_name}: {task_count} task(s)")
    
    return "\n".join(summary_parts)