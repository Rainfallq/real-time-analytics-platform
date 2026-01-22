# Real-Time Analytics Platform - Project Context

**Магистерская диссертация:** Development of High-Performance Microservices Architecture for Real-Time Stream Data Processing

**Статус:** В разработке (Foundation phase)  
**Дата начала:** Декабрь 2024  
**Разработчик:** Backend Developer (Python/Django background)  
**Окружение:** Windows 11, VS Code, Docker Desktop

---

## 📋 Table of Contents

1. [Project Overview](#project-overview)
2. [Technology Stack](#technology-stack)
3. [Project Goals](#project-goals)
4. [Architecture Design](#architecture-design)
5. [Current Project Structure](#current-project-structure)
6. [Development Phases](#development-phases)
7. [Setup Instructions](#setup-instructions)
8. [Key Technical Decisions](#key-technical-decisions)
9. [API Design Patterns](#api-design-patterns)
10. [Database Schema](#database-schema)
11. [Common Issues & Solutions](#common-issues--solutions)
12. [Next Steps](#next-steps)

---

## 🎯 Project Overview

### Description
Real-Time Analytics Platform - высокопроизводительная микросервисная система для обработки потоковых данных в реальном времени. Платформа предназначена для приема, обработки и анализа больших объемов событий (логов, IoT-данных, метрик).

### Core Features
- **Real-time data ingestion** - прием событий через REST API
- **Stream processing** - обработка потоков с Apache Kafka
- **Analytics & Aggregation** - аналитика и агрегация данных
- **WebSocket notifications** - real-time уведомления
- **Time-series storage** - TimescaleDB для временных рядов
- **Authentication & Authorization** - JWT-based auth

### Use Cases
1. Мониторинг логов приложений в реальном времени
2. Анализ финансовых транзакций для детекции аномалий
3. IoT платформа для обработки данных с сенсоров
4. Real-time метрики и дашборды

---

## 🛠 Technology Stack

### Backend Core
- **Python 3.11** - основной язык разработки
- **FastAPI 0.115.5** - современный async web framework
- **Pydantic 2.10+** - валидация данных и settings management
- **SQLAlchemy 2.0.36** - async ORM для работы с БД
- **Alembic 1.14.0** - миграции базы данных

### Databases
- **PostgreSQL 16 + TimescaleDB** - основная БД с поддержкой time-series
- **Redis 7** - кеширование, сессии, rate limiting
- **MongoDB** (future) - для неструктурированных логов

### Message Broker & Stream Processing
- **Apache Kafka 7.5.0** - message broker для потоков данных
- **Faust** или **Kafka Streams** - stream processing
- **Celery + Redis** - background tasks и периодические задачи

### Authentication & Security
- **python-jose** - JWT token management
- **passlib[bcrypt]** - password hashing
- **python-multipart** - form data handling

### Development Tools
- **pytest** - тестирование
- **black** - code formatting
- **ruff** - linting
- **mypy** - type checking

### Infrastructure
- **Docker & Docker Compose** - контейнеризация
- **Prometheus + Grafana** - мониторинг и метрики
- **Kubernetes** (future) - оркестрация в продакшене

### Testing & Quality
- **pytest-asyncio** - async tests
- **pytest-cov** - code coverage
- **httpx** - async HTTP client для тестов

---

## 🎓 Project Goals

### Академические цели (для диссертации)
1. Исследовать паттерны высокопроизводительной обработки потоков
2. Сравнить различные подходы (sync vs async, разные message brokers)
3. Провести benchmark производительности
4. Анализ масштабируемости архитектуры
5. Написать научные статьи по результатам

### Практические цели (для резюме и работы)
1. Получить опыт с современным стеком (FastAPI, Kafka, микросервисы)
2. Создать portfolio проект с реальной архитектурой
3. Освоить stream processing - редкий и востребованный навык
4. Практика с distributed systems и event-driven architecture

---

## 🏗 Architecture Design

### High-Level Architecture

```
[Clients] → [API Gateway] → [Auth Service]
                ↓
         [Ingestion Service] → [Kafka Topics]
                                    ↓
                    ┌───────────────┼───────────────┐
                    ↓               ↓               ↓
            [Stream Processor] [Batch Processor] [ML Service]
                    ↓               ↓               ↓
            [TimescaleDB] ← [Analytics Service] → [Redis]
                    ↓
         [Notification Service] → [WebSocket] → [Dashboard]
                    ↓
            [Prometheus/Grafana]
```

### Microservices Breakdown

#### 1. API Gateway (Port 8000)
- **Responsibility:** Единая точка входа, routing, rate limiting
- **Tech:** FastAPI
- **Dependencies:** Auth Service

#### 2. Auth Service (Port 8001)
- **Responsibility:** Authentication, authorization, user management
- **Tech:** FastAPI + JWT
- **Database:** PostgreSQL (users table)
- **Features:** 
  - User registration/login
  - JWT access + refresh tokens
  - API key management
  - Role-based access control (RBAC)

#### 3. Ingestion Service (Port 8002)
- **Responsibility:** Прием и валидация входящих событий
- **Tech:** FastAPI + Kafka Producer
- **Features:**
  - REST API для приема событий
  - Batch ingestion endpoint
  - Webhook endpoints
  - Валидация с Pydantic
  - Rate limiting

#### 4. Stream Processor
- **Responsibility:** Real-time обработка потоков
- **Tech:** Faust (or FastAPI + aiokafka)
- **Features:**
  - Windowing (tumbling, hopping, sliding)
  - Aggregations в реальном времени
  - Stateful processing
  - Pattern detection (spikes, anomalies)
  - Writing to TimescaleDB

#### 5. Batch Processor
- **Responsibility:** Тяжелые аналитические задачи
- **Tech:** Celery + Redis
- **Features:**
  - Периодические задачи (Celery Beat)
  - Heavy analytics
  - Data cleanup
  - Report generation

#### 6. ML Service (Port 8003)
- **Responsibility:** Anomaly detection, pattern recognition
- **Tech:** FastAPI + scikit-learn
- **Features:**
  - Isolation Forest для anomaly detection
  - Pattern recognition
  - Alert triggering

#### 7. Analytics Service (Port 8004)
- **Responsibility:** Запросы и аналитика
- **Tech:** FastAPI
- **Features:**
  - Query API для агрегированных данных
  - Caching с Redis
  - Query optimization

#### 8. Notification Service (Port 8005)
- **Responsibility:** Real-time уведомления
- **Tech:** FastAPI + WebSocket
- **Features:**
  - WebSocket connections
  - Push notifications
  - Email/Slack интеграция (optional)

### Data Flow

```
1. Client отправляет event → Ingestion Service
2. Ingestion Service → validates → Kafka (topic: raw-data)
3. Stream Processor subscribes → processes → writes to DB
4. Analytics Service reads from DB → caches in Redis
5. Notification Service pushes updates → WebSocket → Client
```

---

## 📁 Current Project Structure

```
realtime-analytics-platform/
├── .vscode/                      # VS Code settings
│   ├── settings.json            # Python interpreter, formatters
│   └── launch.json              # Debug configurations
│
├── backend/                      # Main application
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI entry point ✅
│   │   ├── config.py            # App config (deprecated, use core/config.py)
│   │   │
│   │   ├── api/                 # API layer
│   │   │   ├── __init__.py
│   │   │   ├── deps.py          # Dependencies (get_db, get_current_user) ✅
│   │   │   ├── router.py        # Main API router ✅
│   │   │   │
│   │   │   └── v1/             # API version 1
│   │   │       ├── __init__.py
│   │   │       ├── router.py    # V1 router ✅
│   │   │       │
│   │   │       ├── endpoints/   # Endpoint modules
│   │   │       │   ├── __init__.py
│   │   │       │   ├── auth.py         # Auth endpoints (stub) ⚠️
│   │   │       │   ├── events.py       # Event ingestion (stub) ⚠️
│   │   │       │   └── analytics.py    # Analytics queries (stub) ⚠️
│   │   │       │
│   │   │       └── schemas/     # Pydantic schemas (TO CREATE) ❌
│   │   │           ├── __init__.py
│   │   │           ├── auth.py         # Auth request/response schemas
│   │   │           ├── event.py        # Event schemas
│   │   │           └── analytics.py    # Analytics schemas
│   │   │
│   │   ├── core/                # Core functionality
│   │   │   ├── __init__.py
│   │   │   ├── config.py        # Settings (Pydantic) ✅
│   │   │   └── security.py      # JWT, password hashing (TO CREATE) ❌
│   │   │
│   │   ├── models/              # SQLAlchemy models
│   │   │   ├── __init__.py
│   │   │   ├── user.py          # User model ✅
│   │   │   └── event.py         # Event model ✅
│   │   │
│   │   ├── services/            # Business logic layer (TO CREATE) ❌
│   │   │   ├── __init__.py
│   │   │   ├── auth_service.py       # Auth logic
│   │   │   └── event_service.py      # Event processing logic
│   │   │
│   │   └── db/                  # Database layer
│   │       ├── __init__.py
│   │       ├── base.py          # Base model, mixins ✅
│   │       └── session.py       # Async session, get_db ✅
│   │
│   ├── tests/                   # Tests (TO CREATE) ❌
│   │   ├── __init__.py
│   │   ├── conftest.py          # Pytest fixtures
│   │   ├── test_auth.py
│   │   └── test_events.py
│   │
│   ├── alembic/                 # Database migrations (TO INIT) ❌
│   │   └── versions/
│   │
│   └── requirements.txt         # Python dependencies ✅
│
├── infrastructure/              # Infrastructure configs
│   ├── docker/
│   │   ├── Dockerfile           # Production dockerfile
│   │   └── Dockerfile.dev       # Development dockerfile
│   │
│   ├── sql/
│   │   └── init.sql            # Initial DB setup ✅
│   │
│   └── monitoring/
│       ├── prometheus/
│       │   └── prometheus.yml
│       └── grafana/
│           ├── dashboards/
│           └── datasources/
│
├── docs/                        # Documentation
│   └── api/                     # API documentation
│
├── .env                         # Environment variables ✅
├── .env.example                 # Example env file ✅
├── .gitignore                   # Git ignore ✅
├── docker-compose.dev.yml       # Development compose ✅
├── docker-compose.yml           # Production compose (TO CREATE)
└── README.md                    # Project readme

Legend:
✅ - Created and working
⚠️ - Created but stub/incomplete
❌ - Not created yet
```

---

## 📊 Development Phases

### Phase 0: Setup (COMPLETED ✅)
**Duration:** 1 day  
**Status:** DONE

- [x] Create project structure
- [x] Setup virtual environment (Python 3.11)
- [x] Install dependencies
- [x] Setup Docker Compose with PostgreSQL + Redis
- [x] Create base FastAPI app
- [x] Configure settings with Pydantic
- [x] Setup database models and session
- [x] Test basic API (http://localhost:8000/docs works)

**Current State:**
- FastAPI app runs on http://localhost:8000
- PostgreSQL + Redis running in Docker
- Basic models (User, Event) created
- Stub endpoints in place

---

### Phase 1: Authentication & Core API (CURRENT) 🔄
**Duration:** 1-2 weeks  
**Priority:** HIGH

#### Week 1: Authentication System

**Tasks:**
1. **Create security utilities** (`backend/app/core/security.py`)
   - Password hashing with bcrypt
   - JWT token generation (access + refresh)
   - Token verification

2. **Create Pydantic schemas** (`backend/app/api/v1/schemas/auth.py`)
   - UserCreate, UserLogin
   - Token, TokenData
   - UserResponse, UserUpdate

3. **Implement auth endpoints** (`backend/app/api/v1/endpoints/auth.py`)
   - POST `/api/v1/auth/register` - user registration
   - POST `/api/v1/auth/login` - login with JWT tokens
   - POST `/api/v1/auth/refresh` - refresh access token
   - GET `/api/v1/auth/me` - get current user info
   - PUT `/api/v1/auth/me` - update user profile

4. **Create auth dependency** (`backend/app/api/deps.py`)
   - `get_current_user()` - dependency to inject current user
   - `get_current_active_user()` - only active users
   - Optional: `require_role()` - role-based access

5. **Write tests** (`backend/tests/test_auth.py`)
   - Test registration
   - Test login
   - Test token refresh
   - Test protected endpoints

**Success Criteria:**
- User can register via API
- User can login and receive JWT tokens
- Protected endpoints work with authentication
- All tests pass

---

#### Week 2: Event Ingestion

**Tasks:**
1. **Create event schemas** (`backend/app/api/v1/schemas/event.py`)
   - EventCreate, EventBatch
   - EventResponse, EventList

2. **Implement ingestion endpoints** (`backend/app/api/v1/endpoints/events.py`)
   - POST `/api/v1/events/ingest` - single event
   - POST `/api/v1/events/batch` - batch ingestion
   - GET `/api/v1/events` - list events (with filters)
   - GET `/api/v1/events/{id}` - get single event

3. **Add validation and rate limiting**
   - Pydantic validation
   - Rate limiting with slowapi
   - Size limits for batch requests

4. **Write to database**
   - Store events in PostgreSQL
   - Use bulk insert for batches

5. **Write tests**
   - Test single event ingestion
   - Test batch ingestion
   - Test validation errors
   - Test rate limiting

**Success Criteria:**
- Events can be submitted via API
- Validation works correctly
- Events stored in database
- Performance: 1000+ events/sec

---

### Phase 2: Kafka & Stream Processing (Weeks 3-5)
**Duration:** 3 weeks  
**Priority:** HIGH

#### Week 3: Kafka Integration

**Setup:**
1. Add Kafka to docker-compose
2. Install aiokafka / faust
3. Create Kafka topics (raw-data, processed-data, alerts)

**Tasks:**
1. **Modify ingestion service**
   - Write events to Kafka instead of direct DB
   - Keep REST API the same

2. **Create Kafka producer service**
   - Async producer with aiokafka
   - Error handling and retries
   - Monitoring (messages sent counter)

3. **Test Kafka integration**
   - Verify events reach Kafka
   - Check topic partitioning

---

#### Week 4-5: Stream Processor

**Option A: Faust (Recommended)**

Create `services/stream-processor/` with Faust app:

**Features:**
1. **Real-time aggregations**
   - Count events by type (tumbling window 1 min)
   - Calculate average severity
   - Detect spikes (count > threshold)

2. **Stateful processing**
   - Track event counts per source
   - Anomaly scores
   - Pattern detection

3. **Write to TimescaleDB**
   - Aggregated metrics table
   - Time-series data

4. **Trigger alerts**
   - When anomaly detected
   - When spike detected
   - Send to alerts topic

**Success Criteria:**
- Stream processor consumes from Kafka
- Aggregations calculated correctly
- Data written to TimescaleDB
- Alerts triggered on anomalies

---

### Phase 3: Analytics & Dashboards (Weeks 6-8)
**Duration:** 3 weeks

#### Week 6: Analytics Service

**Tasks:**
1. Create analytics endpoints
2. Query TimescaleDB efficiently
3. Implement caching with Redis
4. Pagination and filtering

**Endpoints:**
- GET `/api/v1/analytics/events/count` - event counts
- GET `/api/v1/analytics/events/distribution` - by type
- GET `/api/v1/analytics/timeline` - time-series data
- GET `/api/v1/analytics/anomalies` - anomaly list

---

#### Week 7: WebSocket Notifications

**Tasks:**
1. Setup WebSocket endpoint
2. Subscribe to alerts topic
3. Push to connected clients
4. Connection management

---

#### Week 8: Dashboard (Optional)

**Options:**
1. **Grafana** - use existing dashboards
2. **React SPA** - custom dashboard
3. **Streamlit** - quick dashboard for demo

---

### Phase 4: ML & Advanced Features (Weeks 9-10)
**Duration:** 2 weeks

1. **ML Service**
   - Isolation Forest for anomaly detection
   - Pattern recognition
   - Model training pipeline

2. **Batch Processor (Celery)**
   - Periodic aggregations
   - Report generation
   - Data cleanup tasks

---

### Phase 5: Production Ready (Weeks 11-12)
**Duration:** 2 weeks

1. **Monitoring**
   - Prometheus metrics in each service
   - Grafana dashboards
   - Distributed tracing (Jaeger)

2. **Testing**
   - Load testing with Locust
   - Integration tests
   - Coverage > 80%

3. **Documentation**
   - OpenAPI/Swagger docs
   - Architecture diagrams
   - Deployment guide

4. **CI/CD**
   - GitHub Actions
   - Automated tests
   - Docker image builds

5. **Deployment** (Optional)
   - Kubernetes manifests
   - Helm charts
   - Production config

---

## 🚀 Setup Instructions

### Prerequisites
- **Python 3.11** installed
- **Docker Desktop** running
- **VS Code** (recommended)
- **Git** installed

### Initial Setup

```powershell
# 1. Clone repository (or create if new)
git clone <repo-url>
cd realtime-analytics-platform

# 2. Create virtual environment
python -m venv venv

# 3. Activate virtual environment
# Windows PowerShell:
.\venv\Scripts\Activate.ps1

# Windows CMD:
venv\Scripts\activate.bat

# Linux/Mac:
source venv/bin/activate

# 4. Install dependencies
pip install --upgrade pip
pip install -r backend/requirements.txt

# 5. Create .env file
cp .env.example .env
# Edit .env and change SECRET_KEY!

# 6. Start databases
docker-compose -f docker-compose.dev.yml up -d

# 7. Wait for databases to be ready (check with)
docker ps

# 8. Run database migrations (when Alembic is setup)
# cd backend
# alembic upgrade head

# 9. Start FastAPI application
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 10. Open browser
# http://localhost:8000/docs - API documentation
# http://localhost:8000/health - health check
```

### Verify Setup

```powershell
# Check API is running
curl http://localhost:8000/health

# Expected response:
# {"status": "healthy", "version": "0.1.0", "environment": "development"}

# Check database connection
curl http://localhost:8000/ready

# Expected response:
# {"status": "ready"}
```

### Access Services

- **FastAPI:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs
- **PostgreSQL:** localhost:5432
- **Redis:** localhost:6379
- **PgAdmin:** http://localhost:5050 (admin@admin.com / admin)
- **Redis Commander:** http://localhost:8081

---

## 🔑 Key Technical Decisions

### 1. Why FastAPI?
- Modern async framework
- Automatic OpenAPI docs
- Type hints & validation (Pydantic)
- High performance (Starlette + Uvicorn)
- Growing ecosystem

### 2. Why PostgreSQL + TimescaleDB?
- TimescaleDB extends PostgreSQL for time-series
- Single database instead of multiple
- SQL queries for analytics
- JSONB for flexible schema

### 3. Why Kafka?
- Industry standard for streaming
- High throughput
- Fault tolerant
- Exactly-once semantics
- Large ecosystem

### 4. Why start as monolith then split?
- Faster initial development
- Easier debugging
- Can split into microservices later
- Iterate quickly on MVP

### 5. Python 3.11 vs 3.13?
- 3.11 is stable and well-supported
- All libraries work (no compilation issues)
- Good balance between new features and stability

---

## 📐 API Design Patterns

### RESTful Endpoints

```
/api/v1/auth/*          - Authentication
/api/v1/events/*        - Event management
/api/v1/analytics/*     - Analytics queries
/api/v1/users/*         - User management (admin)
```

### Standard Response Format

**Success:**
```json
{
  "data": {...},
  "meta": {
    "page": 1,
    "page_size": 20,
    "total": 100
  }
}
```

**Error:**
```json
{
  "detail": "Error message",
  "error_code": "VALIDATION_ERROR",
  "timestamp": "2024-12-17T10:30:00Z"
}
```

### Authentication Flow

```
1. POST /api/v1/auth/register
   Request: {email, password, full_name}
   Response: {user object}

2. POST /api/v1/auth/login
   Request: {email, password}
   Response: {access_token, refresh_token, token_type}

3. Use access_token in headers:
   Authorization: Bearer <access_token>

4. When access_token expires:
   POST /api/v1/auth/refresh
   Request: {refresh_token}
   Response: {new access_token, new refresh_token}
```

---

## 🗄 Database Schema

### Core Tables

```sql
-- Users table
CREATE TABLE users (
    id UUID PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    role VARCHAR(50) NOT NULL DEFAULT 'user',
    is_active BOOLEAN NOT NULL DEFAULT true,
    is_verified BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    last_login TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role) WHERE is_active = true;

-- Events table (TimescaleDB hypertable)
CREATE TABLE events (
    id UUID PRIMARY KEY,
    event_type VARCHAR(100) NOT NULL,
    source_id UUID NOT NULL,
    event_time TIMESTAMP WITH TIME ZONE NOT NULL,
    ingested_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    payload JSONB NOT NULL,
    metadata JSONB,
    severity FLOAT NOT NULL DEFAULT 0.5,
    anomaly_score FLOAT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Convert to hypertable
SELECT create_hypertable('events', 'event_time');

-- Indexes
CREATE INDEX idx_events_type_time ON events(event_type, event_time DESC);
CREATE INDEX idx_events_source_time ON events(source_id, event_time DESC);
CREATE INDEX idx_events_severity ON events(severity) WHERE severity > 0.7;
CREATE INDEX idx_events_payload_gin ON events USING gin(payload);

-- Aggregated metrics table
CREATE TABLE aggregated_metrics (
    id UUID PRIMARY KEY,
    metric_name VARCHAR(100) NOT NULL,
    window_start TIMESTAMP WITH TIME ZONE NOT NULL,
    window_end TIMESTAMP WITH TIME ZONE NOT NULL,
    count INTEGER NOT NULL,
    sum_value FLOAT,
    avg_value FLOAT,
    min_value FLOAT,
    max_value FLOAT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

SELECT create_hypertable('aggregated_metrics', 'window_start');
CREATE INDEX idx_metrics_name_time ON aggregated_metrics(metric_name, window_start DESC);
```

---

## 🐛 Common Issues & Solutions

### Issue 1: Python 3.13 - pydantic-core compilation error
**Problem:** `pydantic-core` требует Rust compiler

**Solution:** Use Python 3.11
```powershell
# Remove old venv
Remove-Item -Recurse -Force venv

# Install Python 3.11 from python.org
# https://www.python.org/downloads/release/python-3119/

# Create new venv with 3.11
py -3.11 -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
```

### Issue 2: Docker containers not starting
**Problem:** Ports already in use

**Solution:**
```powershell
# Check what's using the ports
netstat -ano | findstr :5432
netstat -ano | findstr :6379

# Kill process or change ports in docker-compose.dev.yml
```

### Issue 3: ModuleNotFoundError
**Problem:** Python can't find app modules

**Solution:**
```powershell
# Make sure you're in backend/ directory
cd backend

# Set PYTHONPATH (if needed)
$env:PYTHONPATH = "."

# Or use python -m
python -m uvicorn app.main:app --reload
```

### Issue 4: SQLite vs PostgreSQL connection strings
**Problem:** Different connection strings for different DBs

**Solution:**
- SQLite (for quick tests): `sqlite+aiosqlite:///./analytics.db`
- PostgreSQL (production): `postgresql+asyncpg://user:pass@localhost:5432/analytics`

### Issue 5: Alembic not initialized
**Problem:** `alembic upgrade head` fails

**Solution:**
```powershell
cd backend
alembic init alembic

# Edit alembic.ini:
# sqlalchemy.url = postgresql+asyncpg://...

# Edit alembic/env.py:
# target_metadata = Base.metadata

# Create first migration:
alembic revision --autogenerate -m "Initial migration"
alembic upgrade head
```

---

## 📚 Learning Resources

### FastAPI
- Official docs: https://fastapi.tiangolo.com/
- Full Stack FastAPI Template: https://github.com/tiangolo/full-stack-fastapi-template

### Kafka & Stream Processing
- Kafka Streams Tutorial: https://kafka.apache.org/documentation/streams/
- Faust Docs: https://faust.readthedocs.io/

### SQLAlchemy 2.0
- Async ORM: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html

### Architecture Patterns
- Microservices Patterns: https://microservices.io/patterns/
- Event-Driven Architecture: https://aws.amazon.com/event-driven-architecture/

---

## 🎯 Next Steps (Development Order)

### Immediate (This Week)
1. ✅ Create `backend/app/core/security.py`
2. ✅ Create `backend/app/api/v1/schemas/auth.py`
3. ✅ Implement auth endpoints in `backend/app/api/v1/endpoints/auth.py`
4. ✅ Update `backend/app/api/deps.py` with `get_current_user()`
5. ✅ Test authentication flow manually via `/docs`

### Short Term (Next 2 Weeks)
1. Write pytest tests for auth
2. Implement event ingestion endpoints
3. Add Kafka to docker-compose
4. Create Kafka producer in ingestion service
5. Basic stream processor with Faust

### Medium Term (Weeks 3-8)
1. Advanced stream processing (windowing, aggregations)
2. Analytics API
3. WebSocket notifications
4. ML service for anomaly detection
5. Monitoring setup

### Long Term (Weeks 9-12)
1. Production deployment
2. Performance optimization
3. Load testing
4. Documentation
5. Dissertation writing

---

## 💡 Tips for AI Assistants

### When helping with this project:

1. **Always check current phase** - Don't jump ahead
2. **Follow the structure** - Maintain consistency
3. **Use async/await** - Everything should be async
4. **Type hints** - Always add proper type hints
5. **Docstrings** - Add docstrings to all functions
6. **Error handling** - Proper try/except blocks
7. **Logging** - Use Python logging, not print()
8. **Tests** - Suggest tests after implementing features
9. **Security** - Never hardcode secrets, always use env vars
10. **Performance** - Consider scalability in solutions

### Code Style
- Use **Black** formatting
- Follow **PEP 8**
- Max line length: 88 characters (Black default)
- Use **f-strings** for formatting
- Prefer **list comprehensions** over loops when simple

### Common Patterns
- **Dependency Injection** for services (FastAPI Depends)
- **Repository Pattern** for database access (optional)
- **Service Layer** for business logic
- **Pydantic** for ALL data validation
- **Async** for ALL I/O operations

---

## 📞 Contact & Support

**Developer:** Backend Developer