# SmartTask - Agentic AI Productivity Assistant

SmartTask is an intelligent productivity assistant that demonstrates autonomous, goal-driven behavior by leveraging Large Language Models (LLMs). It helps users manage tasks, reminders, and events through natural language understanding and integration with external services like Google Calendar and email.

## Features

- **Natural Language Processing**: Understand user requests in natural language to create tasks, reminders, and events
- **Task Management**: Create, edit, complete, and delete tasks with various attributes (priority, category, etc.)
- **Google Calendar Integration**: Sync events with Google Calendar for a unified scheduling experience
- **Email Integration**: Import tasks from emails and send email reminders/reports
- **Intelligent Suggestions**: Get AI-powered suggestions for new tasks based on your existing ones
- **Automated Scheduling**: Schedule reminders and notifications for upcoming tasks
- **Task Categorization**: Organize tasks by type, priority, and category
- **Overdue Task Tracking**: Identify and highlight tasks that have passed their due date
- **Summary Generation**: Get natural language summaries of your upcoming tasks and schedule

## Architecture

The system is built with a modular architecture:

- **Core Components**:
  - `llm_agent.py`: LLM integration for natural language understanding
  - `task_scheduler.py`: Task management and scheduling system
  - `google_calendar.py`: Google Calendar API integration
  - `email_integration.py`: Email sending and processing
  - `main.py`: FastAPI web server and API endpoints

- **User Interface**:
  - Web interface built with FastAPI, Jinja2 templates, and modern CSS
  - Responsive design that works on desktop and mobile devices

- **External Integrations**:
  - Google Calendar API for event synchronization
  - Email sending/receiving for notifications and task imports

## Technology Stack

- **Backend**:
  - Python 3.8+
  - FastAPI web framework
  - Hugging Face Transformers (GPT-Neo)
  - Schedule library for task scheduling
  - Google API Client for Calendar integration

- **Frontend**:
  - Jinja2 templates
  - HTML5/CSS3
  - JavaScript (vanilla)
  - Font Awesome icons

## Setup Instructions

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Google account (for Calendar integration)

### Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/smarttask-assistant.git
   cd smarttask-assistant
   ```

2. Create a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   Create a `.env` file in the project root with the following variables:
   ```
   # Optional: Set to "true" to use OpenAI as a fallback
   USE_OPENAI=false
   
   # Email configuration (for sending reminders)
   EMAIL_HOST=smtp.gmail.com
   EMAIL_PORT=587
   EMAIL_USE_TLS=true
   EMAIL_USERNAME=your-email@gmail.com
   EMAIL_PASSWORD=your-app-password
   ```

5. Set up Google Calendar API (optional):
   - Go to the [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project
   - Enable the Google Calendar API
   - Create OAuth 2.0 credentials (Desktop application)
   - Download the credentials JSON file and save it as `credentials.json` in the project root

### Running the Application

1. Start the server:
   ```
   uvicorn main:app --reload
   ```

2. Open your browser and navigate to:
   ```
   http://localhost:8000
   ```

3. The first time you try to use Google Calendar features, you'll be prompted to authenticate and grant permissions.

## Usage Guide

### Creating Tasks

You can create tasks in multiple ways:

1. **Natural Language Input**: Type commands like "Remind me to call mom tomorrow at 10am" in the main input field.

2. **Task Form**: Use the "New Task" button to manually fill out task details.

3. **Email Import**: Tasks can be automatically imported from your email inbox.

4. **Calendar Sync**: Events from Google Calendar will appear as tasks.

### Task Management

- View tasks on the home page, organized by "Overdue" and "Upcoming"
- Filter tasks by type, priority, category, and completion status on the Tasks page
- Edit, complete, or delete tasks using the action buttons
- Send reminders for specific tasks manually

### Calendar Integration

- Connect your Google Calendar to sync events in both directions
- Create events in SmartTask and they'll appear in your Google Calendar
- Import events from your Google Calendar to SmartTask

### Email Features

- Receive email reminders for upcoming tasks
- Send task reports to any email address
- Import tasks from email messages (configured email account required)

## Agentic Behavior

The system demonstrates agentic capabilities in several ways:

1. **Autonomous Decision Making**: The LLM determines task types, priorities, and categories based on natural language input.

2. **Goal-Driven Actions**: The task scheduler automatically sends reminders, syncs with external services, and cleans up old tasks.

3. **Adaptive Planning**: The system suggests new tasks based on patterns in existing tasks.

4. **Environmental Awareness**: Integration with calendar and email systems to maintain awareness of external events and communications.

5. **Natural Language Understanding**: Processing user inputs to extract intentions, dates, priorities, and other task attributes.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgements

- Built using GPT-Neo by EleutherAI
- Google Calendar API
- FastAPI and Jinja2
- The open-source community for various libraries and tools