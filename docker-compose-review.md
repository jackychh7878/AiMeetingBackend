# Docker Compose Review & Offline Deployment Guide

## Current Architecture Analysis

Your docker-compose file implements a comprehensive AI meeting minutes system with the following components:

### Core Services
1. **AI Meeting Backend** (`jccatomind/ai_meeting_backend:latest`)
   - Flask-based API server
   - Port: 8000
   - Dependencies: pgvector, minio, n8n

2. **AI Meeting Chatbot Frontend** (`jccatomind/ai_meeting_chatbot_frontend:latest`)
   - React/Vite frontend
   - Port: 3000

### Database Layer
3. **pgvector** (`pgvector/pgvector:pg17`)
   - Vector database for AI embeddings
   - Port: 5432
   - Default credentials: your_pgvector_password

4. **PostgreSQL** (`postgres:16-alpine`)
   - Traditional database for n8n
   - Port: 5433
   - Credentials: your_postgres_password

### Storage & Object Storage
5. **MinIO** (`minio/minio:latest`)
   - S3-compatible object storage
   - Ports: 9000 (API), 9001 (Console)
   - Credentials: your_minio_root_password

### Workflow Automation
6. **n8n** (`n8nio/n8n:latest`)
   - Workflow automation platform
   - Port: 5678
   - Includes import service for demo data

### Vector Database
7. **Qdrant** (`qdrant/qdrant:latest`)
   - Vector similarity search engine
   - Port: 6333

### AI/ML Models
8. **Ollama** (`ollama/ollama:latest` & `ollama/ollama:rocm`)
   - Local LLM server
   - Port: 11434
   - Multiple profiles: CPU, NVIDIA GPU, AMD GPU

## Security Concerns & Recommendations

### 🔴 Critical Issues
1. **Hardcoded Passwords**
   ```yaml
   # pgvector service
   - POSTGRES_PASSWORD=your_pgvector_password
   
   # minio service
   - MINIO_ROOT_USER=minioadmin
   - MINIO_ROOT_PASSWORD=your_minio_root_password
   ```

2. **Missing Image Tags**
   - Most images use `:latest` tag
   - No version pinning for reproducible deployments

### 🟡 Medium Priority Issues
1. **Exposed Ports**
   - All services expose ports to host
   - Consider using internal networks only

2. **Health Check Dependencies**
   - Some services depend on health checks
   - Others use simple `depends_on`

## Offline Deployment Recommendations

### 1. Image Version Pinning
Replace `:latest` tags with specific versions:

```yaml
# Recommended versions
n8nio/n8n:1.28.0
pgvector/pgvector:pg17-0.5.1
postgres:16.2-alpine
minio/minio:RELEASE.2024-01-16T16-07-38Z
qdrant/qdrant:v1.7.4
ollama/ollama:0.1.29
ollama/ollama:0.1.29-rocm
```

### 2. Environment Variable Management
Create a comprehensive `.env` file:

```env
# Database Configuration
POSTGRES_USER=root
POSTGRES_PASSWORD=your_postgres_password
POSTGRES_DB=n8n

# pgvector Database
PGVECTOR_USER=sqladmin
PGVECTOR_PASSWORD=your_pgvector_password
PGVECTOR_DB=postgres

# MinIO Configuration
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=your_minio_root_password

# n8n Configuration
N8N_ENCRYPTION_KEY=your_n8n_encryption_key
N8N_USER_MANAGEMENT_JWT_SECRET=your_n8n_jwt_secret
N8N_DEFAULT_BINARY_DATA_MODE=filesystem

# Application Configuration
ON_PREMISES_MODE=on_cloud
VITE_N8N_BASE_URL=http://localhost:5678

# Azure Services (for cloud database and storage access)
AZURE_STT_API_KEY=your_azure_stt_api_key
AZURE_POSTGRES_CONNECTION=your_azure_postgres_connection
AZURE_CONTAINER_NAME=your_azure_container_name_here
AZURE_ACCOUNT_NAME=your_azure_account_name_here
AZURE_ACCOUNT_KEY=your_azure_account_key

# FanoLab Service (for ASR integration)
FANOLAB_HOST=https://portal-demo.fano.ai
FANOLAB_API_KEY=your_fanolab_api_key

# TFlow Service (for project management integration)
TFLOW_HOST=your_tflow_host_here

# Ngrok Configuration (for local development/debugging)
# ngrok exposes your local backend to the internet for cloud callbacks.
# - NGROK_PUBLIC_MODE: 'public' (use ngrok DNS) or 'private' (use local IP only)
# - NGROK_HOST: your ngrok public DNS
# - NGROK_ACCESS_KEY/NGROK_SECRET_KEY: your MinIO credentials
# To use ngrok, set ON_PREMISES_MODE=on_premises.
NGROK_PUBLIC_MODE=public
NGROK_HOST=your_ngrok_host_here
NGROK_ACCESS_KEY=your_minio_access_key
NGROK_SECRET_KEY=your_minio_secret_key

# On-premises DB (if used)
ON_PREMISES_POSTGRES_CONNECTION=postgresql+psycopg2://sqladmin:your_pgvector_password@localhost:5432/postgres
```

> **Note:** Do not use the example secrets in production. Replace all `your_...` values with strong, unique credentials.

### 3. ON_PREMISES_MODE Usage
- `ON_PREMISES_MODE=on_cloud`: disables ngrok, uses direct cloud connections.
- `ON_PREMISES_MODE=on_premises`: enables ngrok/local exposure for development or remote callbacks.

### 4. Network Security
Consider using internal networks for inter-service communication:

```yaml
networks:
  ai_network:
    driver: bridge
    internal: true  # No external access
  external_network:
    driver: bridge  # For services that need external access
```

### 5. Volume Security
Add proper volume permissions:

```yaml
volumes:
  pgvector_data:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /secure/path/to/pgvector_data
```

## Offline Packaging Process

### Step 1: Create Image Inventory
```bash
docker images --format "table {{.Repository}}:{{.Tag}}\t{{.Size}}" | grep -E "(n8nio|pgvector|postgres|minio|qdrant|ollama|jccatomind)"
```

### Step 2: Pull and Save Images
```bash
./offline-package.sh  # Linux/Mac
# or
.\offline-package.ps1  # Windows
```

### Step 3: Transfer Package
- Copy entire `docker-images-offline` directory
- Include all `.tar` files
- Include `load-images.sh`/`load-images.ps1`
- Include `docker-compose-offline.yaml`
- Include `INSTALLATION_GUIDE.md`

### Step 4: Deploy on Offline System
```bash
./load-images.sh
docker-compose -f docker-compose-offline.yaml --profile cpu up -d
```

## Performance Optimizations

### 1. Resource Limits
Add resource constraints:

```yaml
services:
  ai_meeting_backend:
    deploy:
      resources:
        limits:
          memory: 4G
          cpus: '2.0'
        reservations:
          memory: 2G
          cpus: '1.0'
```

### 2. Health Check Improvements
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s
```

### 3. Logging Configuration
```yaml
services:
  ai_meeting_backend:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

## Monitoring & Maintenance

### 1. Service Monitoring
```bash
docker-compose ps
docker-compose logs -f ai_meeting_backend
docker stats
```

### 2. Backup Strategy
```bash
docker exec pgvector pg_dump -U sqladmin postgres > backup.sql
docker run --rm -v pgvector_data:/data -v $(pwd):/backup alpine tar czf /backup/pgvector_backup.tar.gz -C /data .
```

### 3. Update Process
For offline updates:
1. Pull new images on internet-connected machine
2. Save images using packaging script
3. Transfer new images to offline system
4. Load new images
5. Restart services with new images

## Troubleshooting Guide

### Common Issues
1. **Port Conflicts**: Check if ports are already in use
2. **Memory Issues**: Increase Docker memory limits
3. **GPU Issues**: Ensure NVIDIA Docker runtime is installed
4. **Network Issues**: Check firewall settings

### Debug Commands
```bash
docker-compose logs [service-name]
docker inspect [container-name]
docker exec [container-name] ping [target-service]
docker system df
```

## Conclusion

Your docker-compose setup is well-structured and now reflects your actual environment. The offline packaging scripts provided will help you deploy this system in air-gapped environments. Focus on:

1. **Security**: Use strong, unique passwords and keys
2. **Versioning**: Pin image versions for reproducibility
3. **Monitoring**: Implement proper logging and health checks
4. **Backup**: Establish regular backup procedures
5. **Documentation**: Maintain deployment and troubleshooting guides 