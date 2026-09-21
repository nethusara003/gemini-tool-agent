"""
Gemini Interactions API — Function-Calling Agent
=================================================
Demonstrates the full manual tool-use loop:
  1. Send a user message with tool declarations
  2. Detect function_call steps in the response
  3. Execute the matching local function
  4. Send the function_result back to the model
  5. Print the final natural-language answer

Uses stateless mode (store=False) with client-side history management
so every request carries the complete conversation context.
"""

import json
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from google import genai
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# ──────────────────────────────────────────────
# 0. Configuration
# ──────────────────────────────────────────────
load_dotenv()

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
MODEL = "gemini-3.6-flash"

# Google Calendar OAuth Settings
CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.json"


def get_calendar_service():
    """
    Authenticate and return a Google Calendar API service instance.
    Uses token.json if valid; otherwise opens a browser via InstalledAppFlow
    to authorize and saves the resulting credentials to token.json.
    """
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, CALENDAR_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                raise FileNotFoundError(
                    f"'{CREDENTIALS_FILE}' not found in project root. "
                    "Please provide Google OAuth client credentials."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_FILE, CALENDAR_SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    return build("calendar", "v3", credentials=creds)


# ──────────────────────────────────────────────
# 1. Tool implementations
# ──────────────────────────────────────────────

def get_current_time() -> dict:
    """Return the current UTC date/time as an ISO-8601 string."""
    now = datetime.now(timezone.utc)
    return {"current_time": now.isoformat()}


def add_numbers(a: float, b: float) -> dict:
    """Add two numbers and return the result."""
    return {"sum": a + b}


def list_upcoming_events(max_results: int = 5) -> dict:
    """
    Fetch the next `max_results` upcoming events from the user's primary calendar.
    Returns a list of events with summary and start time.
    """
    try:
        service = get_calendar_service()
        now = datetime.now(timezone.utc).isoformat()
        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=now,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        items = events_result.get("items", [])
        if not items:
            return {"events": [], "message": "No upcoming events found."}

        events = []
        for item in items:
            start = item.get("start", {}).get("dateTime", item.get("start", {}).get("date"))
            events.append({
                "summary": item.get("summary", "(No title)"),
                "start_time": start,
            })
        return {"events": events}
    except Exception as exc:
        return {"error": f"Failed to list calendar events: {str(exc)}"}


# Registry: maps function name → callable
TOOL_REGISTRY = {
    "get_current_time": get_current_time,
    "add_numbers": add_numbers,
    "list_upcoming_events": list_upcoming_events,
}

# ──────────────────────────────────────────────
# 2. Tool declarations for the Interactions API
# ──────────────────────────────────────────────

tool_declarations = [
    {
        "type": "function",
        "name": "get_current_time",
        "description": "Returns the current date and time in UTC as an ISO-8601 string.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "type": "function",
        "name": "add_numbers",
        "description": "Adds two numbers together and returns the sum.",
        "parameters": {
            "type": "object",
            "properties": {
                "a": {"type": "number", "description": "The first number."},
                "b": {"type": "number", "description": "The second number."},
            },
            "required": ["a", "b"],
        },
    },
    {
        "type": "function",
        "name": "list_upcoming_events",
        "description": "Fetches the next upcoming events from the user's primary Google Calendar. Returns the summary and start time for each event.",
        "parameters": {
            "type": "object",
            "properties": {
                "max_results": {
                    "type": "integer",
                    "description": "The maximum number of upcoming events to return. Defaults to 5.",
                },
            },
            "required": [],
        },
    },
]

# ──────────────────────────────────────────────
# 3. Execute a function call step locally
# ──────────────────────────────────────────────

def execute_tool(name: str, arguments: dict) -> dict:
    """Look up `name` in TOOL_REGISTRY and call it with `arguments`."""
    func = TOOL_REGISTRY.get(name)
    if func is None:
        return {"error": f"Unknown tool: {name}"}
    try:
        return func(**arguments)
    except TypeError as exc:
        return {"error": f"Bad arguments for {name}: {exc}"}

# ──────────────────────────────────────────────
# 4. The agent loop
# ──────────────────────────────────────────────

def run_agent(user_message: str) -> str:
    """
    Send `user_message` to Gemini, handle any function calls, and
    return the model's final text answer.
    """
    print(f"\n{'='*60}")
    print(f"🧑 User: {user_message}")
    print(f"{'='*60}")

    # --- Turn 1: initial request -------------------------------------------
    history = [
        {
            "type": "user_input",
            "content": [{"type": "text", "text": user_message}],
        }
    ]

    interaction = client.interactions.create(
        model=MODEL,
        store=False,
        input=history,
        tools=tool_declarations,
    )

    # Append every model step to history (thought, function_call, text, etc.)
    for step in interaction.steps:
        history.append(step.model_dump())

    # --- Check if the model wants to call tools ---------------------------
    fc_steps = [s for s in interaction.steps if s.type == "function_call"]

    if not fc_steps:
        # No tool calls — the model answered directly
        print(f"\n🤖 Gemini: {interaction.output_text}")
        return interaction.output_text

    # --- Execute each requested function call -----------------------------
    for fc in fc_steps:
        print(f"\n🔧 Tool call detected:")
        print(f"   Function : {fc.name}")
        print(f"   Arguments: {fc.arguments}")
        print(f"   Call ID  : {fc.id}")

        result = execute_tool(fc.name, fc.arguments)
        print(f"   Result   : {result}")

        # Append the function result to the conversation history
        history.append({
            "type": "function_result",
            "name": fc.name,
            "call_id": fc.id,
            "result": [{"type": "text", "text": json.dumps(result)}],
        })

    # --- Turn 2: send results back to get final answer --------------------
    final_interaction = client.interactions.create(
        model=MODEL,
        store=False,
        input=history,
        tools=tool_declarations,
    )

    final_text = final_interaction.output_text
    print(f"\n🤖 Gemini: {final_text}")
    return final_text


# ──────────────────────────────────────────────
# 5. Interactive CLI loop
# ──────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    # If query passed as CLI arguments, run it directly
    if len(sys.argv) > 1:
        run_agent(" ".join(sys.argv[1:]))
    elif sys.stdin.isatty():
        # Interactive CLI loop
        print("\n🤖 Google Calendar Agent is ready! Ask calendar, time, or math questions.")
        print("   Type 'quit' or 'exit' to end the session.")
        while True:
            try:
                user_msg = input("\n🧑 You: ").strip()
                if not user_msg:
                    continue
                if user_msg.lower() in ("exit", "quit"):
                    print("Goodbye!")
                    break
                run_agent(user_msg)
            except (KeyboardInterrupt, EOFError):
                print("\nGoodbye!")
                break
    else:
        # Non-interactive mode (e.g. piped input or test)
        piped_input = sys.stdin.read().strip()
        if piped_input:
            for line in piped_input.splitlines():
                if line.strip():
                    run_agent(line.strip())
        else:
            run_agent("What are my upcoming events on Google Calendar?")
