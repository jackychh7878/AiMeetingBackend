# AI Meeting Minutes - Offline Installation Guide

## Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- At least 16GB RAM (recommended for LLM workloads)
- 100GB+ free disk space
- NVIDIA GPU (optional, for GPU acceleration)

## Package Contents
- Docker images (`*.tar` files)
- Ollama LLM model archive (`ollama_storage.tar.gz` or `ollama_storage.zip`)
- `docker-compose-offline.yaml`
- `.env` file (edit with your configuration)
- Load scripts (`load-images.sh` or `load-images.ps1`)

## Installation Steps

### 1. Transfer Files
Copy the entire offline package directory to your on-premises (offline) system.

### 2. Load Docker Images
#### Linux/Mac:
```bash
cd docker-images-offline
chmod +x load-images.sh
./load-images.sh
```
#### Windows (PowerShell):
```powershell
cd docker-images-offline
./load-images.ps1
```

### 3. Restore Ollama LLM Model Files
#### Linux/Mac:
```bash
tar xzf ollama_storage.tar.gz
# This will create an 'ollama_storage' directory with the model files
```
#### Windows (PowerShell):
```powershell
Expand-Archive -Path ollama_storage.zip -DestinationPath ollama_storage
```

#### Initialize Docker Volume with Model Files
If you are using Docker named volumes (as in the compose file), copy the extracted `ollama_storage` contents into the Docker volume:

##### Linux/Mac:
```bash
docker volume create ollama_storage
# Find the mount point for the volume:
VOLUME_PATH=$(docker volume inspect ollama_storage -f '{{ .Mountpoint }}')
sudo cp -r ollama_storage/* "$VOLUME_PATH/"
```
##### Windows (PowerShell):
```powershell
docker volume create ollama_storage
$volumePath = docker volume inspect ollama_storage -f '{{ .Mountpoint }}'
Copy-Item -Path ".\ollama_storage\*" -Destination $volumePath -Recurse
```

> **Note:** If you use a bind mount instead of a named volume, just point the mount to your extracted `ollama_storage` directory.

### 4. Configure Environment
Copy the provided `.env` file to the same directory as your `docker-compose-offline.yaml` and edit as needed:
```bash
cp .env.example .env
# Edit .env with your configuration
# Set VITE_N8N_BASE_URL to the base URL for your n8n workflow engine (default: http://localhost:5678)
```

### 5. Start Services
```bash
# For CPU-only deployment
docker-compose -f docker-compose-offline.yaml --profile cpu up -d

# For NVIDIA GPU deployment
docker-compose -f docker-compose-offline.yaml --profile gpu-nvidia up -d

# For AMD GPU deployment
docker-compose -f docker-compose-offline.yaml --profile gpu-amd up -d
```

### 6. Verify Installation
- Backend API: http://localhost:8000/health
- Frontend: http://localhost:3000
- n8n Workflows: http://localhost:5678
- MinIO Console: http://localhost:9001
- Qdrant: http://localhost:6333
- Ollama LLM: http://localhost:11434

## Service Ports

| Service | Port | Description |
|---------|------|-------------|
| Backend API | 8000 | Main application API |
| Frontend | 3000 | Web interface |
| n8n | 5678 | Workflow automation |
| MinIO API | 9000 | Object storage API |
| MinIO Console | 9001 | Object storage web UI |
| PostgreSQL (pgvector) | 5432 | Vector database |
| PostgreSQL (n8n) | 5433 | n8n database |
| Qdrant | 6333 | Vector database |
| Ollama | 11434 | AI model server |

## Troubleshooting

### Check Service Status
```bash
docker-compose ps
```

### View Logs
```bash
docker-compose logs -f [service-name]
```

### Reset Everything
```bash
docker-compose down -v
docker-compose up -d
```

## Security Notes
- Change default passwords in `.env` file
- Configure firewall rules
- Use HTTPS in production
- Regularly update images when possible

## Notes
- If you add new LLM models in the future, repeat the model packaging steps and update the offline package.
- For large models, ensure your disk and RAM are sufficient for inference. 