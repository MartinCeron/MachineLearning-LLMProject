import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def interpret_user_input(user_input: str) -> str:
    prompt = f"""
You are a productivity assistant. Take the user's request and convert it into a JSON object using this structure:

{{
  "intent": "reminder" | "calendar_event" | "task",
  "description": "string",
  "datetime": "ISO 8601 formatted string (e.g., 2025-03-25T14:00:00)",
  "priority": "low" | "medium" | "high" | null
}}

User input: "{user_input}"

Return only valid JSON. Do not include explanations or any text outside of the JSON.
"""

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5,
    )

    return response.choices[0].message.content.strip()
