from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from llm_agent import interpret_user_input
import json
import re
import os

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

tasks_file = "tasks.json"

def save_task(task_data):
    if not os.path.exists(tasks_file):
        with open(tasks_file, "w") as f:
            json.dump([], f)
    with open(tasks_file, "r") as f:
        tasks = json.load(f)
    tasks.append(task_data)
    with open(tasks_file, "w") as f:
        json.dump(tasks, f, indent=2)

def get_all_tasks():
    if not os.path.exists(tasks_file):
        return []
    with open(tasks_file, "r") as f:
        return json.load(f)

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    tasks = get_all_tasks()
    return templates.TemplateResponse("index.html", {"request": request, "tasks": tasks})

@app.post("/submit-task", response_class=HTMLResponse)
async def submit_task(request: Request, message: str = Form(...)):
    llm_response = interpret_user_input(message)
    raw_response = llm_response.strip()

    try:
        match = re.search(r'\{[\s\S]*?\}', raw_response)
        if not match:
            raise ValueError("No valid JSON object found in LLM response.")
        json_snippet = match.group(0)

        task_data = json.loads(json_snippet)
        save_task(task_data)

        return templates.TemplateResponse("index.html", {
            "request": request,
            "task": task_data,
            "raw_response": raw_response,
            "tasks": get_all_tasks()
        })

    except Exception as e:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "error": f"⚠️ Failed to parse response: {e}",
            "raw_response": raw_response,
            "tasks": get_all_tasks()
        })