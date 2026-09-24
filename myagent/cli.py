"""
myagent CLI Entry Point
=======================
Provides command-line interface and interactive REPL for the agent.
"""

import argparse
import sys
from myagent import __version__
from myagent.agent import MODEL, run_agent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="myagent",
        description="Groq function-calling CLI agent with Google Calendar",
    )
    parser.add_argument(
        "-v", "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show program's version number and exit",
    )
    parser.add_argument(
        "query",
        nargs="*",
        help="Optional prompt to execute directly. If omitted, starts interactive chat mode.",
    )
    return parser


def print_welcome() -> None:
    """Show a compact terminal welcome screen."""
    print("\n╭─ MyAgent ─────────────────────────────────────╮")
    print(f"│ Model: {MODEL[:35]:<35} │")
    print("│ /help for commands                            │")
    print("╰───────────────────────────────────────────────╯\n")


def print_help() -> None:
    print("\nCommands:")
    print("  /help    Show this list")
    print("  /clear   Start a new conversation")
    print("  /status  Show the current model and chat status")
    print("  /exit    Quit MyAgent\n")


def start_interactive_loop():
    """Start an interactive chat loop with in-session conversation memory."""
    print_welcome()
    history: list[dict] = []

    while True:
        try:
            user_msg = input("You › ").strip()
            if not user_msg:
                continue
            command = user_msg.lower()
            if command in ("/exit", "exit", "quit", "q"):
                print("\nGoodbye!")
                break
            if command == "/help":
                print_help()
                continue
            if command == "/clear":
                history.clear()
                print("\nConversation cleared.\n")
                continue
            if command == "/status":
                turns = sum(1 for item in history if item["role"] == "user")
                print(f"\nModel: {MODEL}\nConversation turns: {turns}\n")
                continue
            if command.startswith("/"):
                print("Unknown command. Type /help to see available commands.\n")
                continue
            run_agent(user_msg, history)
        except (KeyboardInterrupt, EOFError):
            print("\n\nGoodbye!")
            break


def main():
    """Main CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()

    # 1. Direct query passed as command-line arguments
    if args.query:
        query_text = " ".join(args.query).strip()
        if query_text:
            run_agent(query_text)
            return

    # 2. Interactive terminal mode
    if sys.stdin.isatty():
        start_interactive_loop()
        return

    # 3. Piped / non-interactive input
    piped_input = sys.stdin.read().strip()
    if piped_input:
        for line in piped_input.splitlines():
            line = line.strip()
            if line:
                run_agent(line)
    else:
        # Fallback default test query if empty non-interactive run
        run_agent("What are my upcoming events on Google Calendar?")


if __name__ == "__main__":
    main()
