# Local Business Opening Tracker

Track confirmed new business openings anywhere in the world using the CatchAll Web Search API. Results route to terminal, email, or a FastAPI dashboard.

## Setup

```bash
pip install newscatcher-catchall-sdk python-dotenv pydantic[email] rapidfuzz
cp .env.example .env
# Add your CATCHALL_API_KEY to .env
```

## Run

```bash
python3 tracker.py
```

The tracker prompts you for:
- Business type (restaurant, gym, clinic, etc.)
- Country
- City
- Days to look back (1–30)
- Email for alerts (optional)

## Email alerts

To receive results by email, add your Gmail credentials to `.env`:

```
GMAIL_ADDRESS=you@gmail.com
GMAIL_APP_PASSWORD=your_app_password
```

Generate a Gmail app password at: https://myaccount.google.com/apppasswords

## Get your API key

Sign up for 2,000 free credits at [platform.newscatcherapi.com](https://platform.newscatcherapi.com)
