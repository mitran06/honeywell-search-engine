# PDF Context Search Engine

Enterprise self-hosted PDF vector search engine with semantic search capabilities.

## Overview

This tool allows users to:
- Upload and manage PDF documents
- Perform semantic search across all documents
- Find relevant content even with paraphrased or analogous queries
- View results with highlighted text on the original PDF pages

## Tech Stack

| Component | Technology |
|-----------|------------|
| Frontend | React + TypeScript + pdf.js |
| Backend API | FastAPI |
| Background Jobs | Celery |
| Vector Database | Qdrant |
| File Storage | MinIO |
| Embeddings | BGE |
| Metadata DB | PostgreSQL |

## Project Structure

```
search-engine/
├── frontend/          # React frontend application
├── backend/           # FastAPI backend application
├── docker/            # Docker configurations
├── docs/              # Documentation
│   ├── API.md         # API documentation
│   └── SETUP.md       # Setup instructions
├── plan.md            # Frontend implementation plan
└── README.md          # This file
```

## Quick Start

1. **Start infrastructure services:**
   ```bash
   docker-compose -f docker/docker-compose.dev.yml up -d
   ```

2. **Start frontend:**
   ```bash
   cd frontend && npm install && npm run dev
   ```

3. **Start backend:**
   ```bash
   cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload
   ```

4. **Health checks:**
   - API: http://localhost:8000/health
   - Qdrant: http://localhost:8000/api/health/qdrant (verifies vector dim vs model)

See [docs/SETUP.md](docs/SETUP.md) for detailed setup instructions.

## Team

- **Frontend**: React application, PDF viewer, search UI
- **Backend**: FastAPI, Celery workers, database integrations

## Documentation

- [Setup Guide](docs/SETUP.md) - How to set up the development environment
- [API Documentation](docs/API.md) - Backend API endpoints and contracts
- [Frontend Plan](plan.md) - Detailed frontend implementation plan

Key endpoints:
- `/api/documents` for uploads/listing
- `/api/search` for semantic search (scoped to the authenticated user)
- `/api/health/qdrant` to verify Qdrant collection dimensions

## License

Internal use only.
