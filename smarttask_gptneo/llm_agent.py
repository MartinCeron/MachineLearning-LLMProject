from transformers import pipeline
import re

generator = None

def interpret_user_input(user_input: str) -> str:
    global generator

    if generator is None:
        print("[GPT-Neo] Loading model...")
        generator = pipeline(
            "text-generation",
            model="EleutherAI/gpt-neo-125M",
            truncation=True,
            pad_token_id=50256
        )
        print("[GPT-Neo] Model loaded.")

    prompt = f"""
You are a task planning assistant. Return only one JSON object with:
- type (remind, email, event)
- description
- date (ISO 8601)
- priority (low, medium, high)

Do not include any explanation or formatting. Just output valid JSON.

Examples:

User input: "Remind me to submit my assignment on Monday at 9am"
JSON:
{{
  "type": "remind",
  "description": "submit my assignment",
  "date": "2025-03-31T09:00:00Z",
  "priority": "medium"
}}

User input: "Schedule a call with Sarah tomorrow at 3pm"
JSON:
{{
  "type": "event",
  "description": "call with Sarah",
  "date": "2025-03-28T15:00:00Z",
  "priority": "medium"
}}

User input: "{user_input}"
JSON:
"""


    result = generator(
    prompt,
    max_new_tokens=100,  # ✅ generates 100 new tokens on top of input
    do_sample=True,      # 🔄 matches `temperature=0.5` usage
    temperature=0.5,
    truncation=True
)[0]["generated_text"]


    match = re.search(r'\{[\s\S]*?\}', result)
    if match:
        return match.group(0)
    return result