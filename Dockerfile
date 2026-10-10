# One image for the API and the browser workers.
FROM node:22-slim AS frontend
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Playwright's image ships Chromium and its system libraries for the pinned version.
FROM mcr.microsoft.com/playwright/python:v1.63.0-noble
WORKDIR /app
COPY backend/pyproject.toml backend/
COPY backend/tripwright backend/tripwright
RUN pip install --no-cache-dir ./backend
COPY --from=frontend /frontend/dist frontend/dist
ENV DATA_DIR=/app/data
EXPOSE 8000
CMD ["uvicorn", "tripwright.api:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000"]
