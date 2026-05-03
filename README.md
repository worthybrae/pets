# AI Pet Voxel World

An autonomous AI pet that lives in a 3D voxel world. Users create pets that evolve autonomously using Claude AI, build their own voxel worlds, and interact with users via chat. Everything costs "food" (AI credits).

## Architecture

- **Backend:** FastAPI (Python) with Supabase for persistence and Redis for caching
- **Frontend:** React + Vite + TypeScript + Tailwind CSS + Three.js for 3D rendering
- **AI:** Claude (Anthropic) for pet intelligence, memory, and world-building
- **Database:** Supabase (PostgreSQL) with pgvector for embeddings

## Project Structure

```
pets/
├── backend/
│   ├── main.py          # FastAPI app entrypoint
│   ├── api/             # Route handlers
│   ├── models/          # Pydantic models
│   ├── migrations/      # SQL migrations for Supabase
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/       # React pages
│   │   ├── components/  # Shared components
│   │   └── lib/         # Utilities (Supabase client, etc.)
│   └── package.json
├── docker-compose.yml   # Local Redis
└── .env.example
```

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker (for Redis)
- A Supabase project
- An Anthropic API key

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Local Services

```bash
# Start Redis
docker-compose up -d
```

### Environment Variables

Copy `.env.example` to `.env` and fill in your keys:

```bash
cp .env.example .env
```

## Database Setup

Run the SQL migrations in `backend/migrations/` against your Supabase project in order (001, 002, etc.) via the Supabase SQL editor or CLI.
