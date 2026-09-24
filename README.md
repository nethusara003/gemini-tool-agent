# myagent

A command-line AI agent using the Groq Chat Completions API with function
calling and optional Google Calendar integration.

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Setup

Create a `.env` file in the project root:

```env
GROQ_API_KEY="your-groq-api-key"
```

Optionally, place Google Calendar OAuth client credentials in
`credentials.json` in the project directory or
`~/.config/myagent/credentials.json`.

## Usage

Run the interactive agent:

```bash
myagent
```

Run a single prompt:

```bash
myagent "What are my upcoming events?"
myagent "What is 1234 + 5678?"
myagent "What time is it right now?"
```

The available local tools are:

- `get_current_time` — returns the current UTC time
- `add_numbers` — adds two numbers
- `list_upcoming_events` — reads upcoming events from the primary Google Calendar

The default Groq model is `openai/gpt-oss-120b`. Override it with
`GROQ_MODEL` in `.env` if needed.

## Security

Never commit `.env`, `credentials.json`, or `token.json`. These files are
excluded by `.gitignore`. Use placeholder values in documentation and keep
real credentials only in your local environment.
