# Automated Test Generation Frontend

React + Vite dashboard for the AI-powered automated test generation platform.

## Features
- Repository clone/index workflows
- Semantic search with metadata
- Diff pipeline and prompt generation
- Clean, responsive dashboard UI
- Docker-ready production build

## Local Development
```bash
npm install
npm run dev
```

## Environment
Create `.env` and set:
```
VITE_API_BASE_URL=http://localhost:8000
VITE_API_KEY=
```

## Docker
```bash
docker build -t atg-frontend .
docker run -p 8080:80 atg-frontend
```
