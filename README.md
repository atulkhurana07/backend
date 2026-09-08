# ChargeEase - Government EV Fleet Intelligence Platform

Welcome to the backend repository for ChargeEase, a comprehensive EV Fleet Intelligence Platform designed for government organizations. This platform provides real-time monitoring, intelligent alerting, department-level data isolation, and robust role-based access control for managing large-scale electric vehicle fleets.

## Architecture

```mermaid
graph TD
    subgraph Clients
        WebApp[Web Dashboard]
        Mobile[Mobile App]
        PublicApp[Public Citizen App]
        Chargers[EV Chargers & Vehicles]
    end

    subgraph Backend - FastAPI
        API[FastAPI Gateway]
        Auth[Auth & RBAC]
        Services[Business Services]
        WSEngine[WebSocket Engine]
        Alerts[Alert Engine]
        Ingest[Telemetry Ingestion]
        Simulator[Fleet Simulator]
    end

    subgraph Data Layer
        DB[(PostgreSQL)]
    end

    WebApp -->|HTTP/REST| API
    Mobile -->|HTTP/REST| API
    PublicApp -->|HTTP/REST| API
    Chargers -->|HTTP/REST / MQTT| Ingest
    WebApp <-->|WebSocket| WSEngine

    API --> Auth
    API --> Services
    Services --> DB
    Ingest --> DB
    Ingest --> Alerts
    Alerts --> WSEngine
    WSEngine --> Services
    Simulator --> Ingest
```

## Tech Stack

- **Language:** Python 3.12
- **Framework:** FastAPI
- **Database:** PostgreSQL
- **ORM:** SQLAlchemy 2.x (Async)
- **Migrations:** Alembic
- **Validation:** Pydantic v2
- **Authentication:** JWT (JSON Web Tokens), bcrypt for password hashing
- **Real-time:** WebSockets

## Key Features

- **Real-time EV Fleet Monitoring:** Track vehicle locations, battery levels (SoC), and charging status in real-time.
- **Role-Based Access Control (RBAC):** 6 distinct roles (Super Admin, Dept Admin, Dispatcher, Maintenance, Driver, Public API User).
- **Department-Level Data Isolation:** Strict data partitioning ensures departments only see their own fleet and infrastructure data.
- **Telemetry Ingestion & Validation:** High-throughput ingestion pipeline with strict data validation rules.
- **Intelligent Alert Engine:** 8 pre-defined alert types (e.g., Low Battery, Unauthorized Movement, Rapid Discharge).
- **Real-time WebSocket Updates:** Live dashboard updates filtered by department and role.
- **Public API:** Sanitized data endpoints for citizen apps and public dashboards.
- **MQTT-Ready Architecture:** Designed to easily integrate with MQTT brokers for IoT device communication.

## Quick Start

### Prerequisites
- Python 3.11+
- PostgreSQL

### 1. Clone & Setup
```bash
cd backend
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
```

### 2. Database Setup (Docker Option)
If you have Docker installed, you can easily spin up a PostgreSQL instance:
```bash
docker-compose up -d postgres
```

### 3. Migrations & Seeding
Apply database migrations and populate seed data (roles, test users, sample fleet):
```bash
alembic upgrade head
python -m scripts.seed
```

### 4. Run the Server
```bash
uvicorn app.main:app --reload --port 8000
```
- API Docs: `http://localhost:8000/docs`

### 5. Run the Fleet Simulator
To generate real-time telemetry data for testing:
```bash
python -m simulator
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/chargeease` | Database connection string |
| `SECRET_KEY` | `your-super-secret-key` | Key for JWT signing |
| `ALGORITHM` | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Access token lifespan |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token lifespan |
| `ENVIRONMENT` | `development` | Environment (`development`, `production`, `testing`) |

## Database Schema

The system uses 13 normalized tables:
1. **users**: System users and authentication credentials.
2. **roles**: RBAC definitions.
3. **departments**: Government department hierarchies.
4. **vehicles**: EV registry and metadata.
5. **chargers**: Charging station registry.
6. **locations**: Depots and parking locations.
7. **telemetry**: Timeseries vehicle data (SoC, GPS, speed).
8. **alerts**: Generated system and vehicle alerts.
9. **maintenance_logs**: Service history.
10. **charging_sessions**: Records of vehicle charging events.
11. **api_keys**: Keys for external integrations.
12. **audit_logs**: System-wide action tracking.
13. **settings**: Global configuration overrides.

## API Endpoints

### Auth
- `POST /api/v1/auth/login` - Authenticate and get JWT
- `POST /api/v1/auth/refresh` - Refresh access token

### Admin
- `GET /api/v1/admin/users` - Manage users
- `POST /api/v1/admin/departments` - Manage departments

### Operator
- `GET /api/v1/fleet/vehicles` - List department vehicles
- `GET /api/v1/fleet/chargers` - List department chargers
- `GET /api/v1/alerts` - Active alerts

### Ingest
- `POST /api/v1/ingest/telemetry` - Submit vehicle telemetry
- `POST /api/v1/ingest/charger` - Submit charger status

### Public
- `GET /api/v1/public/chargers` - Available public chargers
- `GET /api/v1/public/stats` - Sanitized fleet statistics

### WebSocket
- `WS /api/v1/ws/dashboard` - Real-time updates stream

## Authentication & RBAC

The platform uses JWT for stateless authentication.
- **Access Tokens:** Short-lived (30 mins) for API access.
- **Refresh Tokens:** Long-lived (7 days) for maintaining sessions.

### Roles & Permissions

| Role | Access Level | Description |
|------|-------------|-------------|
| **Super Admin** | Global | Full system access, cross-department visibility. |
| **Dept Admin** | Department | Manage users, vehicles, and settings within their department. |
| **Dispatcher** | Department | Assign vehicles, monitor real-time location and SoC. |
| **Maintenance** | Department | View health alerts, log service records, clear faults. |
| **Driver** | Assigned | View assigned vehicle status, find chargers. |
| **Public API** | Read-Only | Access anonymized data endpoints. |

## Department Isolation
Data isolation is enforced at the database query level. Every API request passes through a dependency that injects the user's `department_id`. All subsequent SQLAlchemy queries are automatically filtered using this ID, ensuring users cannot query or modify data belonging to other departments.

## Telemetry Pipeline

```mermaid
graph LR
    A[Vehicle / Simulator] -->|JSON Payload| B(Ingest API)
    B --> C{Validation}
    C -->|Invalid| D[Reject 400]
    C -->|Valid| E[Save to DB]
    E --> F{Alert Rules Engine}
    F -->|Match| G[Generate Alert]
    F -->|No Match| H[Skip]
    E --> I[Broadcast via WebSocket]
    G --> I
```

## Alert Types

| Alert Type | Condition | Severity |
|------------|-----------|----------|
| **Low Battery** | SoC < 15% while active | High |
| **Critical Battery** | SoC < 5% | Critical |
| **Rapid Discharge** | > 10% drop in 5 mins | Warning |
| **Unauthorized Movement** | GPS change while status=parked | High |
| **Geofence Exit** | GPS outside department bounds | Warning |
| **Charger Fault** | Error code from charger | High |
| **Missed Maintenance** | Odometer > Service Interval | Warning |
| **Offline** | No telemetry for > 15 mins | Medium |

## Public API Sanitization
To protect sensitive government operations, the Public API:
- Strips precise GPS coordinates (rounded to generic blocks or hidden entirely for unmarked vehicles).
- Hides VINs and license plates.
- Only exposes aggregated statistics (e.g., "5 available chargers at Location X").

## WebSocket Real-time Engine
Connect to the WebSocket endpoint for live updates.
- **URL:** `ws://localhost:8000/api/v1/ws/dashboard?token=<JWT>`
- **Authentication:** Token passed as a query parameter.
- **Filtering:** The connection automatically subscribes the client only to events (telemetry, alerts, status changes) relevant to their `department_id`.

## Testing
Run the test suite using pytest:
```bash
pytest
```

## Docker Compose
A `docker-compose.yml` is provided for the complete stack (Postgres + FastAPI application):
```bash
docker-compose up --build
```

## Future Roadmap
- Native MQTT broker integration for lighter telemetry payloads.
- Redis caching for frequent API queries and WebSocket session state.
- SSO integration (SAML/OIDC) for government AD networks.
- Mobile App SDK development.

## Seed Data Accounts
If you ran `python -m scripts.seed`, the following accounts are available (Password for all: `password123`):
- **Super Admin:** `super@chargeease.gov`
- **Police Admin:** `admin@police.gov`
- **Police Dispatcher:** `dispatch@police.gov`
- **Parks Admin:** `admin@parks.gov`
