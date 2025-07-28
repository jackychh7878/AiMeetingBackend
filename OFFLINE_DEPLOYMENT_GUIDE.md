# AI Meeting Minutes - Offline Deployment Guide

## Docker Compose Review Summary

Your `docker-compose.yaml` is well-structured with the following components:

### Core Services
- **AI Meeting Backend** (`jccatomind/ai_meeting_backend:latest`) - Main application API
- **AI Meeting Frontend** (`jccatomind/ai_meeting_chatbot_frontend:latest`) - Web interface
- **n8n** (`n8nio/n8n:latest`) - Workflow automation platform

### Databases & Storage
- **PostgreSQL** (`postgres:16-alpine`) - n8n database
- **PgVector** (`pgvector/pgvector:pg17`) - Vector database for AI embeddings
- **Qdrant** (`qdrant/qdrant:v1.7.4`) - Vector search engine
- **MinIO** (`minio/minio:RELEASE.2025-06-13T11-33-47Z`) - Object storage

### AI/ML Services
- **Ollama** (`ollama/ollama:latest` or `ollama/ollama:rocm`) - LLM inference engine
- Supports CPU, NVIDIA GPU, and AMD GPU profiles

### Key Changes Made
✅ **Updated Ollama model** from `llama3.2` to `deepseek-r1:70b-llama-distill-q8_0` as requested

## Offline Packaging Solution

I've created two packaging scripts for your offline deployment needs:

### 1. Linux/macOS Script: `offline-package.sh`
- Bash script for Unix-like systems
- Comprehensive Docker image packaging
- Automatic Ollama model inclusion

### 2. Windows Script: `offline-package.ps1`
- PowerShell script for Windows environments
- Same functionality as bash version
- 7-Zip integration for better compression

## What Gets Packaged

### Docker Images (9 total):
1. `n8nio/n8n:latest`
2. `pgvector/pgvector:pg17`
3. `minio/minio:RELEASE.2025-06-13T11-33-47Z`
4. `postgres:16-alpine`
5. `qdrant/qdrant:v1.7.4`
6. `ollama/ollama:latest`
7. `ollama/ollama:rocm`
8. `jccatomind/ai_meeting_backend:latest`
9. `jccatomind/ai_meeting_chatbot_frontend:latest`

### Ollama Model:
- **deepseek-r1:70b-llama-distill-q8_0** (as requested)

### Configuration Files:
- `docker-compose.yaml`
- `env.template`
- `init-schema.sql`

## Usage Instructions

### Step 1: Create Offline Package
**On Windows:**
```powershell
.\offline-package.ps1
```

**On Linux/macOS:**
```bash
chmod +x offline-package.sh
./offline-package.sh
```

### Step 2: Transfer to Ubuntu Machine
```bash
# Using SCP
scp ai-meeting-offline-package.tar.gz user@ubuntu-host:~/

# Using rsync (with progress)
rsync -avz --progress ai-meeting-offline-package.tar.gz user@ubuntu-host:~/
```

### Step 3: Deploy on Ubuntu Machine
```bash
# Extract package
tar -xzf ai-meeting-offline-package.tar.gz

# Navigate to scripts
cd ai-meeting-offline-package/scripts

# Make scripts executable
chmod +x *.sh

# Run deployment
./deploy.sh
```

### Step 4: Choose Hardware Profile
After deployment setup, start the application:

**No Ollama (Default)**
```bash
# Start without any Ollama services (default behavior)
docker-compose up -d

# Or explicitly use the no-ollama profile
docker-compose --profile no-ollama up -d
```

**CPU Only:**
```bash
docker-compose --profile cpu up -d
```

**NVIDIA GPU:**
```bash
docker-compose --profile gpu-nvidia up -d
```

**AMD GPU:**
```bash
docker-compose --profile gpu-amd up -d
```

## Checking Status

After starting, you can verify which services are running:
```bash
docker-compose ps
```
### View Logs
```bash
docker-compose logs -f [service-name]
```


## Environment Variables and Container Recreation

When you update your `.env` file, Docker containers may not automatically pick up the new environment variables due to caching. To force containers to use the updated environment variables:

```sh
# Stop and remove existing containers
docker-compose down

# Remove any cached images (optional but recommended)
docker-compose pull

# Start services with fresh containers
docker-compose up -d --force-recreate
```

**Why this is necessary:**
- Docker containers cache environment variables at build time
- Simply updating the `.env` file doesn't automatically update running containers
- The `--force-recreate` flag ensures containers are rebuilt with the latest environment variables

### Reset Everything
```bash
docker-compose down -v
docker-compose up -d
```

## System Requirements

### Minimum Requirements:
- Ubuntu 22.04+
- Docker 20.10+
- Docker Compose 1.27+
- 16GB RAM
- 100GB free disk space

### Recommended for 70B Model:
- 32GB+ RAM
- GPU with 24GB+ VRAM (for GPU acceleration)
- NVMe SSD for faster model loading

## Access Points After Deployment

- **AI Meeting Backend**: http://localhost:8000
- **Frontend Application**: http://localhost:3000
- **n8n Workflows**: http://localhost:5678
- **MinIO Console**: http://localhost:9001
- **Qdrant Dashboard**: http://localhost:6333

## Package Contents Structure

```
ai-meeting-offline-package/
├── images/                     # Docker image tar files
│   ├── n8nio_n8n_latest.tar
│   ├── pgvector_pgvector_pg17.tar
│   └── ...
├── models/                     # Ollama model files
│   └── .ollama/
├── scripts/                    # Deployment scripts
│   ├── deploy.sh              # Main deployment script
│   ├── load-images.sh         # Load Docker images
│   └── setup-ollama.sh        # Setup Ollama models
├── docker-compose.yaml        # Application configuration
├── env.template              # Environment variables
├── init-schema.sql           # Database schema
└── README.md                 # Package documentation
```

## Troubleshooting

### Large Package Size
The package will be substantial (~50-100GB) due to:
- Multiple Docker images (~10-20GB)
- 70B parameter model (~40-80GB)

### Transfer Optimization
- Use `rsync` with `--progress` for resumable transfers
- Consider splitting large packages if network is unstable
- Compress individual components separately if needed

### GPU Acceleration
- Ensure NVIDIA drivers are installed for GPU profiles
- Verify Docker GPU runtime is configured
- Check GPU memory availability for the 70B model

## Environment Configuration

Before starting services, edit the `.env` file with your specific configuration:

```bash
# Database credentials
POSTGRES_USER=your_user
POSTGRES_PASSWORD=your_password
POSTGRES_DB=your_database

# n8n configuration
N8N_ENCRYPTION_KEY=your_encryption_key
N8N_USER_MANAGEMENT_JWT_SECRET=your_jwt_secret

# Storage configuration
MINIO_ROOT_USER=admin
MINIO_ROOT_PASSWORD=your_minio_password

# Application settings
ON_PREMISES_MODE=true
```

## Support

If you encounter issues during deployment:

1. Check Docker service status: `systemctl status docker`
2. Verify image loading: `docker images`
3. Check container logs: `docker-compose logs [service-name]`
4. Ensure sufficient disk space: `df -h`
5. Monitor system resources: `htop` or `top` 