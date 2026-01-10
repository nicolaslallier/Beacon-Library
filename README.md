# Beacon Library - Electronic Document Management System

A full-stack electronic document management system built with React, TypeScript, FastAPI, and PostgreSQL.

## Project Structure

```
Beacon-Library/
├── backend/          # Python FastAPI backend
├── frontend/         # React TypeScript frontend
├── docker-compose.yml # PostgreSQL database setup
└── .env.example      # Environment variables template
```

## Prerequisites

- Python 3.11+
- Node.js 18+
- Docker and Docker Compose
- Poetry (for Python dependency management)

## Getting Started

### 1. Clone the Repository

```bash
git clone <repository-url>
cd Beacon-Library
```

### 2. Set Up Environment Variables

```bash
cp .env.example .env
# Edit .env with your configuration
```

### 3. Start PostgreSQL Database

```bash
docker-compose up -d postgres
```

### 4. Set Up Backend

```bash
cd backend

# Install Poetry if you haven't already
curl -sSL https://install.python-poetry.org | python3 -

# Install dependencies
poetry install

# Activate virtual environment
poetry shell

# Run database migrations (when Alembic is configured)
# alembic upgrade head

# Start the FastAPI server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The backend API will be available at `http://localhost:8000`
API documentation: `http://localhost:8000/docs`

### 5. Set Up Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

The frontend will be available at `http://localhost:5173`

## Development

### Backend Development

- FastAPI with async SQLAlchemy
- Database migrations with Alembic
- Pydantic for data validation
- Python 3.11+

### Frontend Development

- React 18 with TypeScript
- Vite for fast development
- React Router for navigation
- TanStack Query for API state management
- Tailwind CSS for styling
- Axios for HTTP client

### Debugging

Use the debug configurations in `.vscode/launch.json`:

- **Python: FastAPI** - Debug the backend
- **Chrome: Launch Frontend** - Debug the frontend
- **Launch Full Stack** - Debug both simultaneously

## Recommended VS Code Extensions

Install the recommended extensions from `.vscode/extensions.json`:

- Python (ms-python.python)
- Pylance (ms-python.vscode-pylance)
- ESLint (dbaeumer.vscode-eslint)
- Prettier (esbenp.prettier-vscode)
- Tailwind CSS IntelliSense (bradlc.vscode-tailwindcss)

## Database

PostgreSQL 16 is used as the database. The Docker Compose setup includes:

- Persistent data storage
- Health checks
- Network isolation

To reset the database:

```bash
docker-compose down -v
docker-compose up -d postgres
```

## API Documentation

Once the backend is running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## License

[Add your license here]
