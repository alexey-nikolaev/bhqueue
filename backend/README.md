# BHQueue Backend

Real-time queue tracking API for Berlin nightclubs, starting with Berghain.

## Tech Stack

- **Framework**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL with SQLAlchemy (async)
- **Authentication**: JWT + OAuth (Google, Apple)
- **Data Sources**: Reddit API (PRAW), Telegram API (Telethon)

## Setup

### Prerequisites

- Python 3.11+
- PostgreSQL 14+
- Reddit API credentials
- Telegram API credentials

### Installation

1. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your credentials
```

4. Create database:
```bash
createdb bhqueue
```

5. Run migrations:
```bash
alembic upgrade head
```

6. Start development server:
```bash
uvicorn app.main:app --reload
```

The API will be available at http://localhost:8000

## API Documentation

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── config.py            # Settings management
│   ├── database.py          # Database connection
│   ├── models/              # SQLAlchemy models
│   ├── schemas/             # Pydantic schemas
│   ├── routers/             # API endpoints
│   ├── services/            # Business logic
│   └── auth/                # Authentication
├── alembic/                 # Database migrations
├── tests/                   # Test suite
├── requirements.txt
├── Procfile                 # Heroku deployment
└── README.md
```

## Deployment

Deployed on Heroku with PostgreSQL addon.

```bash
heroku create bhqueue-api
heroku addons:create heroku-postgresql:mini
git push heroku main
```
