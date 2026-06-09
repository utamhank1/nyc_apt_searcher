# NYC Apartment Searcher

Project to make everyone's lives easier when searching for an apartment in NYC.

Automated NYC apartment search agent that scrapes StreetEasy and Zillow, scores listings against your criteria, and sends interactive alerts via email + Telegram.

**Reply "Y" to a hot lead** → the system auto-emails the broker with you and your search partners CC'd.

## Features

- **Scrapes StreetEasy + Zillow** every 6 hours (Playwright + stealth mode)
- **Smart scoring** with hard filters (must-have amenities, budget, borough) and soft scoring (commute time, preferred amenities, price)
- **Interactive alerts** via email and Telegram with Y/N buttons
- **Auto broker outreach** — reply Y and the system emails the broker for you
- **Commute calculation** via Google Maps transit directions
- **CRM dashboard** — track leads, filter, sort, manage statuses
- **Custom email templates** with placeholder support
- **Search partner CC** — up to 3 partners on all broker emails

## Quick Start

### Backend

```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
playwright install chromium --with-deps
cp ../.env.example .env  # Edit with your API keys
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm run dev
```

Open http://localhost:3000, enter your API key, and configure your search criteria.

## Required API Keys

| Service | Purpose | Get it at |
|---------|---------|-----------|
| Resend | Email alerts + broker emails | https://resend.com |
| Telegram Bot | Instant alerts with Y/N buttons | Talk to @BotFather on Telegram |
| Google Maps | Commute time calculation | https://console.cloud.google.com |

## Deploy

**Backend** → Railway ($7/mo for Playwright memory)
**Frontend** → Vercel (free)

Set `NEXT_PUBLIC_API_URL` on Vercel to your Railway backend URL.
