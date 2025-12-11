# Project Setup Guide

## Prerequisites

- Node.js 18+ (for frontend)
- Python 3.11+ (for backend)
- Docker & Docker Compose
- Git

---

## Quick Start

### 1. Clone the Repository

```bash
git clone <repository-url>
cd search-engine
```

### 2. Start Infrastructure Services

```bash
# Start PostgreSQL, Qdrant, MinIO, and Redis
docker-compose -f docker/docker-compose.dev.yml up -d
```

Verify services are running:
- PostgreSQL: `localhost:5432`
- Qdrant: `localhost:6333` (Dashboard: http://localhost:6333/dashboard)
- MinIO: `localhost:9000` (Console: http://localhost:9001)
- Redis: `localhost:6379`

### 3. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Copy environment file
cp .env.example .env.local

# Start development server
npm run dev
```

Frontend will be available at: http://localhost:5173

### 4. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file (if not exists)
cp .env.example .env

# Start development server
uvicorn app.main:app --reload --port 8000
```

Backend API will be available at: http://localhost:8000

**Note:** Database tables are automatically created on first startup. No manual migrations needed for initial setup.

### 5. Default Test User

After starting the backend, you can register a new user via:
- **Frontend:** Navigate to http://localhost:5174/register
- **API:** POST to http://localhost:8000/api/auth/register with JSON body:
  ```json
  {
    "email": "test@example.com",
    "password": "password123",
    "name": "Test User"
  }
  ```

---

## Service Credentials (Development)

### PostgreSQL
- Host: `localhost`
- Port: `5432`
- Database: `pdfmeta`
- User: `pdfuser`
- Password: `pdfpass`

### MinIO
- Endpoint: `localhost:9000`
- Console: `localhost:9001`
- Access Key: `minioadmin`
- Secret Key: `minioadmin`

### Qdrant
- Host: `localhost`
- Port: `6333`
- gRPC Port: `6334`

### Redis
- Host: `localhost`
- Port: `6379`

---

## Common Commands

### Docker

```bash
# Start all services
docker-compose -f docker/docker-compose.dev.yml up -d

# Stop all services
docker-compose -f docker/docker-compose.dev.yml down

# View logs
docker-compose -f docker/docker-compose.dev.yml logs -f

# Reset all data (caution: deletes all data)
docker-compose -f docker/docker-compose.dev.yml down -v
```

### Frontend

```bash
# Development
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview

# Run tests
npm run test

# Lint code
npm run lint
```

### Backend

```bash
# Run server
uvicorn app.main:app --reload

# Run Celery worker
python -m celery -A app.celery_worker worker --loglevel=info --pool=solo

# Run database migrations
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "description"
```

---

## Troubleshooting

### Port Already in Use

If a port is already in use, find and kill the process:

```bash
# Windows
netstat -ano | findstr :PORT
taskkill /PID <PID> /F

# macOS/Linux
lsof -i :PORT
kill -9 <PID>
```

### Docker Issues

```bash
# Rebuild containers
docker-compose -f docker/docker-compose.dev.yml up -d --build

# Remove all containers and volumes
docker-compose -f docker/docker-compose.dev.yml down -v --remove-orphans
```

### Database Connection Issues

1. Ensure PostgreSQL container is running
2. Check connection string in `.env`
3. Verify PostgreSQL is healthy: `docker logs search-postgres`
