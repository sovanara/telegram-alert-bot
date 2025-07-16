# Telegram Stock/Crypto Alert Bot

A Serverless AWS Lambda–powered Telegram bot that:
- ⚡️ Tracks price drops for stocks & crypto
- 📊 Builds custom “squad mixes” (indexes)
- 🚨 Sends real-time alerts based on user-set thresholds
- 🤙 Speaks Gen-Z—because why not?

## Features

- **!set** SYMBOL %DROP MINUTES — set an alert
- **!price** SYMBOL — get current price & stats
- **!list**, **!delete**, **!reset** — manage alerts
- **!createindex**, **!index**, **!indexes**, **!deleteindex** — custom indexes
- **!commands** — see all commands

## Repo Structure

- `src/handler.py` — Lambda entrypoint & command dispatch
- `src/bot_helpers.py` — all data-fetching & formatting utilities
- `serverless.yml` — deploy config with price‐checker schedule
- `requirements.txt` — Python deps (boto3, urllib3)
- `tests/` — unit tests for both handler and helpers

## Setup & Deployment

1. **Clone & install**  
   ```bash
   git clone https://github.com/your-org/telegram-alert-bot.git
   cd telegram-alert-bot
   npm install -g serverless
   pip install -r requirements.txt