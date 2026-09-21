# Gemini Tool-Calling Agent

A simple Python AI agent built on the Gemini API's function-calling (tool use) capability. The agent can answer questions directly, or call registered tools — like checking the current time, doing math, or reading your Google Calendar — and use the results to form its answer.

## How it works

1. You send a message to the agent.
2. Gemini decides whether it needs a tool to answer, or can respond directly.
3. If it needs a tool, the agent executes the matching Python function locally.
4. The tool's result is sent back to Gemini.
5. Gemini turns the raw result into a natural-language answer.

## Available tools

- `get_current_time` — returns the current UTC time
- `add_numbers` — adds two numbers
- `list_upcoming_events` — lists your next N upcoming events from Google Calendar (read-only)

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/nethusara003/gemini-tool-agent.git
cd gemini-tool-agent
```

### 2. Create a virtual environment and install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Get a Gemini API key

1. Go to [Google AI Studio](https://aistudio.google.com)
2. Sign in and click **Get API key**
3. Create a key under a new or existing project (free tier, no card required)

Create a `.env` file in the project root:

```
GEMINI_API_KEY=your_key_here
```

### 4. Set up Google Calendar access (optional, only needed for the calendar tool)

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create or select a project, then enable the **Google Calendar API**
3. Go to **APIs & Services → Credentials → Create Credentials → OAuth client ID**
4. Choose **Desktop app**, download the JSON file, rename it `credentials.json`, and place it in the project root
5. Under **Google Auth Platform → Audience**, add your own Google account as a **test user** (required while the app is in "Testing" mode)

On first run that uses the calendar tool, a browser window will open asking you to log in and approve access. A `token.json` file will then be saved locally so you won't need to log in again.

### 5. Run the agent

```bash
.venv/bin/python agent.py
```

Type a question and press enter. Type `exit` to quit.

## Example prompts

- "What time is it right now?"
- "What is 1742 + 389?"
- "What's on my calendar this week?"

## Security notes

- `.env`, `credentials.json`, and `token.json` all contain sensitive credentials and are excluded via `.gitignore`. **Never commit these files.**
- If you fork or clone this repo, you'll need to create your own `.env` and `credentials.json` following the steps above — these are not included for security reasons.

## Roadmap / possible extensions

- Gmail integration (read, draft, send)
- Google Drive search
- Calendar event creation and updates
- Additional custom tools

## Requirements

- Python 3.9+
- A free Gemini API key
- (Optional) A Google Cloud project with the Calendar API enabled, for calendar features
