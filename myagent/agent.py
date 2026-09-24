"""Groq function-calling agent with Google Calendar integration."""

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# ──────────────────────────────────────────────
# 0. Path Resolution & Environment Configuration
# ──────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent
USER_CONFIG_DIR = Path.home() / ".config" / "myagent"

# Load environment variables from cwd, repo root, or ~/.config/myagent
load_dotenv()  # CWD or parent directories
if (REPO_ROOT / ".env").exists():
    load_dotenv(REPO_ROOT / ".env")
if (USER_CONFIG_DIR / ".env").exists():
    load_dotenv(USER_CONFIG_DIR / ".env")

# Groq model can be overridden without changing the source.
MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


def resolve_config_path(filename: str, for_writing: bool = False) -> Path:
    """
    Locate a configuration or credential file (credentials.json, token.json).
    Looks in:
      1. Current working directory
      2. Project repository root
      3. ~/.config/myagent/
    """
    # 1. Current working directory
    cwd_path = Path.cwd() / filename
    if cwd_path.exists():
        return cwd_path

    # 2. Repo root
    repo_path = REPO_ROOT / filename
    if repo_path.exists():
        return repo_path

    # 3. User config directory
    user_config_path = USER_CONFIG_DIR / filename
    if user_config_path.exists():
        return user_config_path

    # If writing a new file (e.g. token.json)
    if for_writing:
        if (REPO_ROOT / "credentials.json").exists():
            return repo_path
        if (Path.cwd() / "credentials.json").exists():
            return cwd_path
        USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        return user_config_path

    return cwd_path


def get_groq_client() -> Groq:
    """Return an initialized Groq client with API key validation."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY is not set. Please set it in your environment or in a .env file."
        )
    return Groq(api_key=api_key)


# ──────────────────────────────────────────────
# 1. Google Calendar Authentication Service
# ──────────────────────────────────────────────

_calendar_service = None


def get_calendar_service():
    """
    Authenticate and return a Google Calendar API service instance.
    Lazily initialized ONLY when called by a calendar tool, and cached
    for subsequent calls within the session.
    Uses token.json if valid; otherwise opens a browser via InstalledAppFlow
    to authorize and saves the resulting credentials to token.json.
    """
    global _calendar_service
    if _calendar_service is not None:
        return _calendar_service

    token_path = resolve_config_path("token.json", for_writing=False)
    creds = None

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), CALENDAR_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            cred_path = resolve_config_path("credentials.json")
            if not cred_path.exists():
                raise FileNotFoundError(
                    f"Google Calendar credentials not found. Looked in:\n"
                    f" - {Path.cwd() / 'credentials.json'}\n"
                    f" - {REPO_ROOT / 'credentials.json'}\n"
                    f" - {USER_CONFIG_DIR / 'credentials.json'}\n"
                    "Please place credentials.json in one of these locations."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(cred_path), CALENDAR_SCOPES
            )
            creds = flow.run_local_server(port=0)

        # Save credentials for future runs
        save_path = resolve_config_path("token.json", for_writing=True)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, "w") as token_file:
            token_file.write(creds.to_json())

    _calendar_service = build("calendar", "v3", credentials=creds)
    return _calendar_service


# ──────────────────────────────────────────────
# 2. Tool Implementations
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
        if isinstance(max_results, str):
            max_results = int(max_results)

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
                "start": start,
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
# 3. Tool Declarations for Groq Chat Completions
# ──────────────────────────────────────────────

tool_declarations = [
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Returns the current date and time in UTC as an ISO-8601 string.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
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
    },
    {
        "type": "function",
        "function": {
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
    },
]


# ──────────────────────────────────────────────
# 4. Tool Execution & Agent Loop
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


def run_agent(user_message: str, history: list[dict] | None = None) -> str:
    """
    Send `user_message` to Groq, handle any function calls, and return
    the model's final text answer.
    """
    client = get_groq_client()

    print(f"\n{'='*60}")
    print(f"🧑 User: {user_message}")
    print(f"{'='*60}")
    print("\nThinking...", flush=True)

    # Callers can pass a list to retain conversation context across turns.
    # A separate list is created for one-off CLI requests.
    if history is None:
        history = []
    history.append({"role": "user", "content": user_message})

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=history,
            tools=tool_declarations,
        )
    except Exception as exc:
        print(f"\n❌ Error contacting Groq API: {exc}")
        return f"Error: {exc}"

    message = response.choices[0].message
    history.append({
        "role": "assistant",
        "content": message.content,
        "tool_calls": [
            {
                "id": tool_call.id,
                "type": "function",
                "function": {
                    "name": tool_call.function.name,
                    "arguments": tool_call.function.arguments,
                },
            }
            for tool_call in (message.tool_calls or [])
        ],
    })

    if not message.tool_calls:
        text_output = message.content or ""
        history.append({"role": "assistant", "content": text_output})
        print("\n🤖 Groq: ", end="", flush=True)
        for token in re.split(r"(\s+)", text_output):
            sys.stdout.write(token)
            sys.stdout.flush()
            time.sleep(0.015)
        print()
        return text_output

    for tool_call in message.tool_calls:
        name = tool_call.function.name
        arguments = json.loads(tool_call.function.arguments or "{}")
        print(f"\n🔧 Tool call detected:")
        print(f"   Function : {name}")
        print(f"   Arguments: {arguments}")
        print(f"   Call ID  : {tool_call.id}")

        result = execute_tool(name, arguments)
        print(f"   Result   : {result}")

        history.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": json.dumps(result),
        })

    print("\nThinking...", flush=True)

    try:
        final_response = client.chat.completions.create(
            model=MODEL,
            messages=history,
        )
        final_text = final_response.choices[0].message.content or ""
        history.append({"role": "assistant", "content": final_text})
        print(f"\n🤖 Groq: {final_text}")
        return final_text
    except Exception as exc:
        print(f"\n❌ Error contacting Groq API: {exc}")
        return f"Error: {exc}"
