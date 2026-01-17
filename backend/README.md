# KlubFlow Backend

*Keep the night moving*

Real-time queue tracking API for Berlin nightclubs, starting with Berghain.

## Tech Stack

- **Framework**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL with SQLAlchemy (async)
- **Authentication**: JWT + OAuth (planned: Google, Apple)
- **Data Sources**:
  - **Reddit**: Devvit app (pushes data to our backend)
  - **Telegram**: Telethon API
  - **Users**: Mobile app submissions

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Reddit Posts   │     │ Telegram Group  │     │  Mobile Apps    │
│  r/Berghain_    │     │ @berghainberlin │     │  iOS / Android  │
│  Community      │     │                 │     │                 │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Devvit App    │     │ Telegram Monitor│     │   User Auth     │
│ (on PostCreate) │     │   (Telethon)    │     │   (JWT)         │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 ▼
                    ┌─────────────────────────┐
                    │   KlubFlow Backend API  │
                    │   POST /api/queue/*     │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │   Queue Parser          │
                    │   (spatial markers,     │
                    │    wait time estimates) │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │   PostgreSQL Database   │
                    └─────────────────────────┘
```

## Setup

### Prerequisites

- Python 3.11+
- PostgreSQL 14+
- Telegram API credentials (optional, for monitoring)

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
cp env.example .env
# Edit .env with your credentials
```

4. Create database:
```bash
createdb klubflow
```

5. Run migrations:
```bash
alembic upgrade head
```

6. Seed initial data:
```bash
python -m scripts.seed_data
```

7. Start development server:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at http://localhost:8000

## API Endpoints

### Public Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/clubs` | List all clubs |
| `GET /api/clubs/{slug}/status` | Club status (open/closed) |
| `GET /api/clubs/{slug}/queues` | Queue types |
| `GET /api/clubs/{slug}/markers` | Spatial markers with wait estimates |
| `GET /api/queue/status` | Aggregated queue status |

### User Endpoints (requires auth)

| Endpoint | Description |
|----------|-------------|
| `POST /api/queue/join` | Start queue session |
| `POST /api/queue/position` | Submit GPS position |
| `POST /api/queue/checkpoint` | Confirm passing a marker |
| `POST /api/queue/result` | Report admitted/rejected |
| `POST /api/queue/leave` | Leave queue |

### Admin Endpoints (requires admin auth)

| Endpoint | Description |
|----------|-------------|
| `POST /api/admin/markers` | Create marker |
| `PATCH /api/admin/markers/{id}` | Update wait time estimates |
| `DELETE /api/admin/markers/{id}` | Delete marker |

### Data Ingestion (internal)

| Endpoint | Source | Description |
|----------|--------|-------------|
| `POST /api/queue/reddit-update` | Devvit | Receives Reddit posts/comments |
| `POST /api/queue/telegram-update` | Telegram bot | Receives Telegram messages |

## API Documentation

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Project Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI application
│   ├── config.py            # Settings management
│   ├── database.py          # Database connection
│   ├── models/              # SQLAlchemy models
│   ├── schemas/             # Pydantic schemas
│   ├── routers/             # API endpoints
│   │   ├── auth.py          # Authentication
│   │   ├── clubs.py         # Club & marker data (public)
│   │   ├── queue.py         # Queue submissions & status
│   │   └── admin.py         # Admin operations
│   ├── services/            # Business logic
│   │   ├── queue_parser.py  # Message parsing
│   │   └── event_service.py # Klubnacht detection
│   └── auth/                # JWT & dependencies
├── alembic/                 # Database migrations
├── scripts/                 # Utility scripts
│   ├── seed_data.py         # Initial data
│   └── test_parser.py       # Parser testing
├── requirements.txt
├── Procfile                 # Heroku deployment
└── README.md
```

## Deployment

### Heroku

```bash
heroku create klubflow-api
heroku addons:create heroku-postgresql:mini
git push heroku main
```

### Environment Variables

Required in production:
- `DATABASE_URL` - PostgreSQL connection string
- `SECRET_KEY` - App secret key
- `JWT_SECRET_KEY` - JWT signing key
- `ADMIN_API_KEY` - Admin API access key

## Related Projects

- **devvit-app/** - Reddit Devvit app that monitors r/Berghain_Community
- **frontend/** - React Native mobile app (iOS/Android)
