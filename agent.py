"""
Groq Function-Calling Agent
===========================
Top-level entrypoint and backward-compatibility shim.
Allows running `python agent.py` or importing from `agent`.
"""

from myagent.agent import (
    CALENDAR_SCOPES,
    MODEL,
    TOOL_REGISTRY,
    add_numbers,
    execute_tool,
    get_calendar_service,
    get_current_time,
    list_upcoming_events,
    run_agent,
    tool_declarations,
)
from myagent.cli import main

if __name__ == "__main__":
    main()
