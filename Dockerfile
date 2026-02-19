# Stage 1: Build frontend
FROM node:20-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python backend
FROM python:3.11-slim
WORKDIR /app

# Install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend + core + config + prompts (prompts needed only for seed script)
COPY backend/ ./backend/
COPY core/ ./core/
COPY config/ ./config/
COPY scripts/ ./scripts/

# Copy built frontend from stage 1
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

# Environment variables (set via Railway dashboard or .env):
#   SUPABASE_URL, SUPABASE_SERVICE_KEY — required
#   GOOGLE_API_KEY, FIRECRAWL_API_KEY — for LLM features

# Platform (Railway, Render, etc.) injects PORT env var
ENV PORT=8000
EXPOSE ${PORT}

CMD uvicorn backend.main:app --host 0.0.0.0 --port ${PORT}
