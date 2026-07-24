# Backend
FROM python:3.12-slim AS backend
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .
COPY exercises-dataset-main /data/exercises-dataset-main
ENV EXERCISES_JSON_PATH=/data/exercises-dataset-main/data/exercises.json
ENV MEDIA_ROOT=/data/exercises-dataset-main
ENV ENVIRONMENT=production
ENV ENABLE_DOCS=false
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Frontend build
FROM node:22-alpine AS frontend-build
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ .
RUN npm run build

# Nginx serves SPA + proxies API
FROM nginx:1.27-alpine AS web
COPY --from=frontend-build /web/dist /usr/share/nginx/html
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD wget -qO- http://127.0.0.1/ || exit 1
