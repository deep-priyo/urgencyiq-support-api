# UrgencyIQ Support API — Backend

A production-ready Flask REST API that turns raw customer messages into prioritized support tickets using hybrid AI urgency scoring (OpenAI + smart keyword heuristics).

## ⚠️ Important Configuration Notes

1. **OpenAI API Key Required for LLM Urgency Scoring**: Without an OpenAI API key, the system falls back to keyword-based urgency scoring only. LLM scoring provides more accurate urgency detection.

2. **Database Auto-Fallback**: Without a PostgreSQL connection string, the application automatically creates a local SQLite database in `instance/app2.db`. This is ideal for local development.

## Overview

This backend provides REST endpoints for:
- Receiving and storing customer messages
- Intelligent urgency scoring (keyword-based + LLM-enhanced)
- Agent reply management
- Ticket assignment and resolution
- Customer profile retrieval
- Real-time message polling support

The urgency analyzer uses a hybrid approach:
- **Keyword-based scoring** (40%): Pattern matching for critical terms like "blocked", "fraud", "rejected"
- **LLM scoring** (60%): GPT-4 Mini contextual analysis for nuanced urgency detection
- **Fallback strategy**: Uses keyword-only scoring if OpenAI API is unavailable

## Tech Stack

- **Flask 3.1.2** - Web framework
- **SQLAlchemy 2.0.45** - ORM and database abstraction
- **Flask-CORS 6.0.2** - Cross-origin resource sharing
- **OpenAI 2.13.0** - LLM urgency analysis
- **PostgreSQL** (production) / **SQLite** (development)
- **Gunicorn 21.2.0** - Production WSGI server

## Project Structure

```
backend/
├── app.py                    # Main Flask application and routes
├── models.py                 # SQLAlchemy database models
├── db.py                     # Database initialization
├── urgency_analyzer.py       # Hybrid urgency scoring system
├── seed_data.py              # CSV data seeding utility
├── init_db.py                # Database table creation script
├── requirements.txt          # Python dependencies
├── .env.example              # Environment variable template
├── render.yaml               # Render.com deployment config
└── data/
    └── GeneralistRails_Project_MessageData.csv
```

## Database Schema

### Customer
- `id` (Integer, Primary Key)
- `messages` (Relationship to Message)

### Message
- `id` (Integer, Primary Key)
- `customer_id` (Foreign Key → Customer)
- `message_body` (Text)
- `timestamp` (DateTime)
- `urgency_score` (Float, 1.0-5.0)
- `status` (String: "open" | "resolved")
- `assigned_to` (String, nullable)
- `assigned_at` (DateTime, nullable)
- `replies` (Relationship to AgentReply)

### AgentReply
- `id` (Integer, Primary Key)
- `message_id` (Foreign Key → Message)
- `agent_name` (String)
- `reply_text` (Text)
- `timestamp` (DateTime)

## Setup Instructions

### Prerequisites
- Python 3.13+ (or 3.10+)
- pip
- (Optional) PostgreSQL database
- (Optional) OpenAI API key for enhanced urgency scoring

### Installation

1. Clone the repository
```bash
git clone <repository-url>
cd urgencyiq-support-api
```

2. Create virtual environment
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

3. Install dependencies
```bash
pip install -r requirements.txt
```

4. Configure environment variables
```bash
# Copy example file
cp .env.example .env

# Edit .env with your credentials
```

**.env Configuration:**
```env
# Optional: PostgreSQL connection (production)
DATABASE_URL=postgresql://user:password@host:port/database

# Optional: OpenAI API key (for LLM urgency scoring)
OPENAI_API_KEY=sk-your-key-here
```

**Note**: Both variables are optional. Without `DATABASE_URL`, SQLite is used. Without `OPENAI_API_KEY`, keyword-only scoring is used.

5. Initialize database
```bash
python init_db.py
```

6. (Optional) Seed with CSV data
```bash
# Place CSV file at: data/GeneralistRails_Project_MessageData.csv
# Then use the seed endpoint (see API section)
```

### Running the Application

**Development Mode:**
```bash
python app.py
```
Server runs at `http://localhost:5000`

**Production Mode:**
```bash
gunicorn app:app --bind 0.0.0.0:5000
```

## API Endpoints

### Message Management

#### Create Message
```http
POST /api/messages/send
Content-Type: application/json

{
  "user_id": 12345,
  "message": "Why was my loan rejected?"
}

Response: 201 Created
{
  "success": true,
  "message_id": 1,
  "urgency": 4.2
}
```

#### Get Messages
```http
GET /api/messages?status=open&sort=urgency&search=loan

Query Parameters:
- status: "open" | "resolved" | "all" (default: "open")
- sort: "urgency" | "time" (default: "urgency")
- user_id: Filter by customer ID
- search: Text search in message body

Response: 200 OK
[
  {
    "id": 1,
    "customer_id": 12345,
    "message": "Why was my loan rejected?",
    "timestamp": "2025-01-15T10:30:00",
    "urgency": 4.2,
    "status": "open",
    "assigned_to": "Agent John",
    "assigned_at": "2025-01-15T10:35:00",
    "replies": [
      {
        "agent_name": "Agent John",
        "reply": "Let me check your application...",
        "timestamp": "2025-01-15T10:36:00"
      }
    ]
  }
]
```

#### Reply to Message
```http
POST /api/messages/{message_id}/reply
Content-Type: application/json

{
  "agent_name": "Agent John",
  "reply": "Your application is under review."
}

Response: 201 Created
{
  "success": true
}
```

#### Resolve Message
```http
POST /api/messages/{message_id}/resolve

Response: 200 OK
{
  "success": true
}
```

#### Assign Message
```http
POST /api/messages/{message_id}/assign
Content-Type: application/json

{
  "agent_name": "Agent Sarah"
}

Response: 200 OK
{
  "success": true,
  "assigned_to": "Agent Sarah",
  "assigned_at": "2025-01-15T14:20:00"
}
```

#### Unassign Message
```http
POST /api/messages/{message_id}/unassign

Response: 200 OK
{
  "success": true
}
```

### Customer Management

#### Get Customer Profile
```http
GET /api/customers/{customer_id}

Response: 200 OK
{
  "id": 12345,
  "total_messages": 15,
  "open_messages": 3,
  "resolved_messages": 12,
  "avg_urgency": 3.4,
  "first_contact": "2024-11-01T08:00:00",
  "last_contact": "2025-01-15T10:30:00"
}
```

### Admin & Utility

#### Health Check
```http
GET /api/health

Response: 200 OK
{
  "status": "ok"
}
```

#### Seed Database from CSV
```http
POST /admin/seed

Response: 200 OK
{
  "success": true,
  "seeded": {
    "rows": 150,
    "messages": 150,
    "customers": 48
  }
}
```

## Urgency Scoring System

### Urgency Levels
- **5.0 (Critical)**: Account blocked, fraud, unauthorized access
- **4.0 (High)**: Loan rejection, disbursement issues, CRB problems
- **3.0 (Medium)**: Payment difficulties, extension requests
- **2.0 (Low)**: General questions, account updates
- **1.0 (Minimal)**: Thank you messages, acknowledgments

### Scoring Algorithm

**With OpenAI API Key:**
```text
final_score = (0.6 * llm_score) + (0.4 * keyword_score)
```

**Without OpenAI API Key:**
```text
final_score = keyword_score  # Falls back to keyword-only
```

### Keyword Categories
The keyword scorer uses 5 tiers of urgency patterns:

**Critical (5.0)**: "blocked", "fraud", "can't access", "stolen", "hacked"
**High (4.0)**: "rejected", "approved", "crb", "disbursed", "waiting"
**Medium (3.0)**: "will pay", "promise", "delay", "overdue"
**Low (2.0)**: "how to", "update", "change", "clarify"
**Minimal (1.0)**: "thank", "okay", "cleared my loan"

Additional patterns like multiple question marks (`???`) or all-caps pleas (`PLEASE`) add urgency modifiers.

## Database Configuration

### Local Development (SQLite)
```python
# Automatic if no DATABASE_URL is set
DATABASE_URI = "sqlite:///instance/app2.db"
```

### Production (PostgreSQL)
```bash
# Set in .env or environment
DATABASE_URL=postgresql://user:password@host:port/database
```

The application automatically:
1. Detects PostgreSQL connection strings
2. Converts legacy `postgres://` to `postgresql://`
3. Falls back to SQLite if no connection string exists
4. Creates necessary directories (`instance/`)

## Deployment

### Render.com (Included Config)

The `render.yaml` file provides one-click deployment:

```yaml
services:
  - type: web
    name: urgencyiq-support-api
    env: python
    buildCommand: pip install -r requirements.txt && python init_db.py
    startCommand: gunicorn app:app
    envVars:
      - key: PYTHON_VERSION
        value: 3.13.0
```

**Required Environment Variables on Render:**
- `DATABASE_URL`: Your PostgreSQL connection string (auto-provided by Render)
- `OPENAI_API_KEY`: Your OpenAI API key (set manually)

### Other Platforms

**Heroku:**
```bash
heroku create urgencyiq-support-api
heroku addons:create heroku-postgresql:mini
heroku config:set OPENAI_API_KEY=sk-your-key
git push heroku main
```

**Railway:**
```bash
railway up
railway variables set OPENAI_API_KEY=sk-your-key
```

## CSV Data Format

Expected CSV structure for seeding:

```csv
User ID,Message Body,Timestamp (UTC)
12345,"Why was my loan rejected?","2025-01-15 10:30:00"
12346,"Thank you for your help","2025-01-15 11:00:00"
```

Place file at: `data/GeneralistRails_Project_MessageData.csv`

## Error Handling

All endpoints return consistent error responses:

```json
{
  "error": "Description of what went wrong"
}
```

Common HTTP status codes:
- `200`: Success
- `201`: Created
- `400`: Bad request (missing parameters)
- `404`: Resource not found
- `500`: Server error

## Development

### Running Tests
```bash
# Test urgency analyzer
python urgency_analyzer.py
```

### Database Migrations
```bash
# Reset database
rm instance/app2.db
python init_db.py

# Re-seed data
curl -X POST http://localhost:5000/admin/seed
```

### Checking API Status
```bash
curl http://localhost:5000/api/health
```

## Performance Considerations

- **LLM Calls**: Each message with `use_llm=True` makes an OpenAI API call. For high-volume deployments, consider caching or batch processing.
- **Database Indexing**: Consider adding indexes on `status`, `urgency_score`, and `timestamp` for large datasets.
- **CORS**: Currently allows all origins (`CORS(app)`). Configure for specific domains in production.

## Security Notes

- No authentication implemented (kept minimal for demo purposes)
- Agent names are used for identification only
- CORS is wide open - restrict in production
- API keys should never be committed to version control
- Use environment variables for all sensitive configuration

## Feature Highlights

✅ RESTful endpoints for messages, replies, and customer profiles  
✅ Hybrid urgency detection: keyword heuristics + LLM scoring  
✅ Search, sort, and filter across urgency, time, and text  
✅ CSV seeding for instant realistic datasets  
✅ Multi-agent assignment and resolution workflow  
✅ Production-friendly config: PostgreSQL/SQLite auto-detect, Gunicorn ready  
✅ Easy deploy on Render/Heroku/Railway

---

— Built as a personal project to showcase full-stack backend design  
Last updated: March 2026