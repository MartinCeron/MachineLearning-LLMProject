from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from llm_agent import interpret_user_input
from db import save_task, get_all_tasks
from calendar_integration import create_calendar_event
# from notifier import send_email_notification

import json
import re

app = FastAPI()

# HTML templates & static files
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# ----- API ENDPOINTS -----

class UserInput(BaseModel):
    message: str

@app.post("/ask")
async def handle_user_input(user_input: UserInput):
    llm_response = interpret_user_input(user_input.message)
    try:
        cleaned = llm_response.strip()

        if cleaned.startswith("```json"):
            cleaned = re.sub(r"^```json|```$", "", cleaned).strip()

        task_data = json.loads(cleaned)
        save_task(task_data)
        event_link = create_calendar_event(task_data)

        return {"status": "Task saved and calendar event created", "task": task_data, "calendar_event": event_link}
    except json.JSONDecodeError:
        return {"error": "Failed to parse LLM response", "raw_response": llm_response}


@app.get("/tasks")
async def list_tasks():
    return {"tasks": get_all_tasks()}


# ----- WEB INTERFACE -----

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    tasks = get_all_tasks()
    return templates.TemplateResponse("index.html", {"request": request, "tasks": tasks})


@app.post("/submit-task", response_class=HTMLResponse)
async def submit_task(request: Request, message: str = Form(...)):
    llm_response = interpret_user_input(message)

    try:
        cleaned = llm_response.strip()

        if cleaned.startswith("```json"):
            cleaned = re.sub(r"^```json|```$", "", cleaned).strip()

        task_data = json.loads(cleaned)
        save_task(task_data)
        event_link = create_calendar_event(task_data)
        task_data["link"] = event_link

        return templates.TemplateResponse("index.html", {
            "request": request,
            "task": task_data,
            "tasks": get_all_tasks()
        })

    except Exception as e:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "error": f"⚠️ Failed to parse response: {e}",
            "raw_response": llm_response,
            "tasks": get_all_tasks()
        })
