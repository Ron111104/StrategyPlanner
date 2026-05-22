# Deployment Documentation

> Local setup, pip install, Docker, docker-compose, production deployment, reverse proxy, and operational considerations.

---

## 1. Local Development

### Prerequisites

- Python 3.12+ (required for `type` union syntax used throughout)
- pip (no npm, no node, no frontend build tools)
- Git

### Setup Steps

```bash
# 1. Clone repository
git clone <repository-url>
cd StrategyPlanner

# 2. Create and activate virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/macOS
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create environment file
copy .env.example .env    # Windows
cp .env.example .env      # Linux/macOS

# 5. Edit .env with your configuration
# At minimum, set QH_API_BASE_URL and QH_API_KEY

# 6. Run the application
python run.py
```

The application starts on `http://localhost:8000` with hot-reload enabled.

### Development Settings

```env
APP_ENV=development
APP_DEBUG=true
LOG_LEVEL=DEBUG
LOG_FORMAT=console
```

---

## 2. Docker Deployment

### Dockerfile

**File:** `Dockerfile`

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["python", "run.py"]
```

Key features:
- `python:3.12-slim` base image (minimal attack surface)
- Dependencies installed in a separate layer (cached across rebuilds)
- Health check pings `/health` every 30 seconds
- Entry point is `python run.py` (which starts uvicorn)

### docker-compose.yml

**File:** `docker-compose.yml`

```yaml
version: '3.8'
services:
  strategy-planner:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env
    volumes:
      - ./app/config:/app/app/config:ro
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
```

Key features:
- Port 8000 exposed
- `.env` file loaded for environment variables
- `app/config/` mounted as read-only volume (allows config changes without rebuild)
- `restart: unless-stopped` for resilience
- Health check configuration

### Build and Run

```bash
# Build and start in detached mode
docker-compose up --build -d

# View logs
docker-compose logs -f strategy-planner

# Stop
docker-compose down

# Rebuild after code changes
docker-compose up --build -d
```

### Config Hot-Reload with Docker

Because `app/config/` is mounted as a volume, you can modify `contracts.yaml` or `strategy_settings.yaml` on the host machine. However, because the config loader uses `@lru_cache`, changes require either:

1. Restart the container: `docker-compose restart strategy-planner`
2. Call the reload endpoint (if implemented): `POST /admin/reload-config`

---

## 3. Production Deployment

### Gunicorn + Uvicorn Workers

For production, use Gunicorn as the process manager with Uvicorn workers:

```bash
pip install gunicorn

gunicorn app.main:app \
    -w 4 \
    -k uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
```

| Flag | Value | Description |
|---|---|---|
| `-w 4` | 4 workers | Number of worker processes (2× CPU cores is typical) |
| `-k uvicorn.workers.UvicornWorker` | Uvicorn | ASGI worker class |
| `--bind 0.0.0.0:8000` | Port 8000 | Network binding |
| `--timeout 120` | 120 seconds | Worker timeout (increase for slow API calls) |

**Important:** With multiple workers, each worker has its own in-memory cache. This means cache is not shared across workers. For shared state, migrate to Redis (see `docs/caching.md`).

### Production Environment Variables

```env
APP_ENV=production
APP_DEBUG=false
LOG_LEVEL=INFO
LOG_FORMAT=json
QH_API_BASE_URL=https://your-actual-api.com
QH_API_KEY=your-production-key
```

---

## 4. Reverse Proxy (Nginx)

For production, place Nginx in front of the application:

### Nginx Configuration

```nginx
upstream strategy_planner {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name strategy-planner.internal.example.com;

    location / {
        proxy_pass http://strategy_planner;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support (for future real-time features)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    location /static/ {
        alias /path/to/StrategyPlanner/app/static/;
        expires 1d;
        add_header Cache-Control "public, immutable";
    }
}
```

### HTTPS with Let's Encrypt

```nginx
server {
    listen 443 ssl;
    server_name strategy-planner.internal.example.com;

    ssl_certificate /etc/letsencrypt/live/strategy-planner.internal.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/strategy-planner.internal.example.com/privkey.pem;

    # ... same location blocks as above
}
```

---

## 5. Docker Compose Production

For production Docker deployment, add Redis and Nginx:

```yaml
version: '3.8'
services:
  strategy-planner:
    build: .
    environment:
      - APP_ENV=production
      - APP_DEBUG=false
      - LOG_FORMAT=json
    env_file:
      - .env.production
    volumes:
      - ./app/config:/app/app/config:ro
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
      interval: 30s
      timeout: 10s
      retries: 3

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./certs:/etc/nginx/certs:ro
    depends_on:
      - strategy-planner
    restart: unless-stopped

  # Future: Redis for shared cache
  # redis:
  #   image: redis:7-alpine
  #   ports:
  #     - "6379:6379"
  #   restart: unless-stopped
```

---

## 6. Health Monitoring

### Health Endpoint

```
GET /health
```

Returns:
```json
{
  "status": "healthy",
  "app": "StrategyPlanner",
  "env": "production"
}
```

### Docker Health Check

The Docker health check pings `/health` every 30 seconds. If it fails 3 times, Docker marks the container as unhealthy and (with `restart: unless-stopped`) restarts it.

### Monitoring Recommendations

- **Uptime:** Monitor `/health` endpoint with external tools (UptimeRobot, Pingdom)
- **Logs:** Ship structured JSON logs to ELK/Splunk/CloudWatch
- **Metrics:** Add Prometheus `/metrics` endpoint in Phase 2
- **Alerts:** Alert on health check failures, high error rates, slow response times

---

## 7. Operational Considerations

### Log Rotation

In production with `LOG_FORMAT=json`, logs are written to stdout/stderr. Docker captures these with its log driver. Configure log rotation:

```yaml
services:
  strategy-planner:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

### Backup

Since all data is ephemeral (in-memory cache), there is nothing to back up in the current architecture. When PostgreSQL persistence is added (Phase 2), regular database backups will be required.

### Security

- Run behind a firewall or VPN (no public internet exposure)
- Use HTTPS in production
- Restrict CORS origins to specific domains
- Rotate API keys regularly
- Use Docker secrets for sensitive environment variables
