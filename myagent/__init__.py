"""myagent - Groq function-calling CLI agent."""

from myagent.agent import (
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

__version__ = "0.1.0"

__all__ = [
    "MODEL",
    "TOOL_REGISTRY",
    "tool_declarations",
    "execute_tool",
    "run_agent",
    "get_current_time",
    "add_numbers",
    "list_upcoming_events",
    "get_calendar_service",
]
