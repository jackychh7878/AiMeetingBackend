#!/bin/bash

# Offline Docker Image Packaging Script for AI Meeting Minutes
# This script packages all required Docker images for offline installation

set -e

# Configuration
PACKAGE_DIR="docker-images-offline"
IMAGES_FILE="required-images.txt"
TAR_FILE="ai-meeting-images.tar.gz"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== AI Meeting Minutes - Offline Image Packaging ===${NC}"

# Create package directory
mkdir -p "$PACKAGE_DIR"
cd "$PACKAGE_DIR"

# Create list of required images
cat > "$IMAGES_FILE" << 'EOF'
# Core Application Images
jccatomind/ai_meeting_backend:latest
jccatomind/ai_meeting_chatbot_frontend:latest

# Database Images
pgvector/pgvector:pg17
postgres:16-alpine

# Storage and Object Storage
minio/minio:latest

# Workflow Automation
n8nio/n8n:latest

# Vector Database
qdrant/qdrant:latest

# AI/ML Models
ollama/ollama:latest
ollama/ollama:rocm
EOF

echo -e "${YELLOW}📋 Required images list created: $IMAGES_FILE${NC}"

# Function to pull and save images
pull_and_save_images() {
    echo -e "${YELLOW}🔍 Pulling and saving Docker images...${NC}"
    
    while IFS= read -r line; do
        # Skip comments and empty lines
        [[ $line =~ ^[[:space:]]*# ]] && continue
        [[ -z "${line// }" ]] && continue
        
        echo -e "${GREEN}📥 Pulling: $line${NC}"
        docker pull "$line"
        
        # Create safe filename
        safe_name=$(echo "$line" | sed 's/[^a-zA-Z0-9._-]/-/g')
        echo -e "${GREEN}💾 Saving: $line -> $safe_name.tar${NC}"
        docker save "$line" -o "$safe_name.tar"
        
    done < "$IMAGES_FILE"
}

# Function to create load script
create_load_script() {
    cat > "load-images.sh" << 'EOF'
#!/bin/bash

# Docker Image Loading Script for Offline Installation
# Run this script on the target system to load all images

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=== Loading Docker Images ===${NC}"

# Load all .tar files
for tar_file in *.tar; do
    if [ -f "$tar_file" ]; then
        echo -e "${YELLOW}📦 Loading: $tar_file${NC}"
        docker load -i "$tar_file"
    fi
done

echo -e "${GREEN}✅ All images loaded successfully!${NC}"
echo -e "${YELLOW}💡 You can now run: docker-compose up -d${NC}"
EOF

    chmod +x "load-images.sh"
}

# Function to create installation guide
create_installation_guide() {
    cat > "INSTALLATION_GUIDE.md" << 'EOF'
# AI Meeting Minutes - Offline Installation Guide

## Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- At least 8GB RAM
- 50GB+ free disk space
- NVIDIA GPU (optional, for GPU acceleration)

## Installation Steps

### 1. Transfer Files
Copy the entire package directory to your offline system.

### 2. Load Docker Images
```bash
cd docker-images-offline
chmod +x load-images.sh
./load-images.sh
```

### 3. Configure Environment
Copy the `.env` file to the same directory as your `docker-compose.yaml`:
```bash
cp .env.example .env
# Edit .env with your configuration
```

### 4. Start Services
```bash
# For CPU-only deployment
docker-compose --profile cpu up -d

# For NVIDIA GPU deployment
docker-compose --profile gpu-nvidia up -d

# For AMD GPU deployment
docker-compose --profile gpu-amd up -d
```

### 5. Verify Installation
- Backend API: http://localhost:8000/health
- Frontend: http://localhost:3000
- n8n Workflows: http://localhost:5678
- MinIO Console: http://localhost:9001
- Qdrant: http://localhost:6333

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
EOF
}

# Function to create offline docker-compose
create_offline_compose() {
    cat > "docker-compose-offline.yaml" << 'EOF'
version: '3.8'

x-n8n: &service-n8n
  image: n8nio/n8n:latest
  networks: ['ai_network']
  environment:
    - DB_TYPE=postgresdb
    - DB_POSTGRESDB_HOST=postgres
    - DB_POSTGRESDB_PORT=5432
    - DB_POSTGRESDB_USER=${POSTGRES_USER}
    - DB_POSTGRESDB_PASSWORD=${POSTGRES_PASSWORD}
    - DB_POSTGRESDB_DATABASE=${POSTGRES_DB}
    - N8N_DIAGNOSTICS_ENABLED=false
    - N8N_PERSONALIZATION_ENABLED=false
    - OLLAMA_HOST=ollama:11434
    - N8N_ENCRYPTION_KEY=${N8N_ENCRYPTION_KEY}
    - N8N_USER_MANAGEMENT_JWT_SECRET=${N8N_USER_MANAGEMENT_JWT_SECRET}
    - N8N_DEFAULT_BINARY_DATA_MODE=${N8N_DEFAULT_BINARY_DATA_MODE}
  env_file:
    - .env

x-ollama: &service-ollama
  image: ollama/ollama:latest
  container_name: ollama
  networks: ['ai_network']
  restart: unless-stopped
  ports:
    - 11434:11434
  volumes:
    - ollama_storage:/root/.ollama

x-init-ollama: &init-ollama
  image: ollama/ollama:latest
  container_name: ollama-pull-llama
  networks: ['ai_network']
  volumes:
    - ollama_storage:/root/.ollama
  entrypoint: /bin/sh
  environment:
    - OLLAMA_HOST=ollama:11434
  command:
    - "-c"
    - "sleep 3; ollama pull llama3.2"

services:
  ai_meeting_backend:
    image: jccatomind/ai_meeting_backend:latest
    container_name: ai_meeting_backend
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      - PORT=8000
      - FLASK_APP=app.py
      - FLASK_ENV=production
      - GUNICORN_CMD_ARGS=--timeout=300 --workers=2 --threads=4 --worker-class=gthread
      - AZURE_STT_API_KEY=${AZURE_STT_API_KEY}
      - FANOLAB_HOST=${FANOLAB_HOST}
      - FANOLAB_API_KEY=${FANOLAB_API_KEY}
      - AZURE_POSTGRES_CONNECTION=${AZURE_POSTGRES_CONNECTION}
      - AZURE_CONTAINER_NAME=${AZURE_CONTAINER_NAME}
      - AZURE_ACCOUNT_NAME=${AZURE_ACCOUNT_NAME}
      - AZURE_ACCOUNT_KEY=${AZURE_ACCOUNT_KEY}
      - ON_PREMISES_MODE=${ON_PREMISES_MODE}
      - NGROK_PUBLIC_MODE=${NGROK_PUBLIC_MODE}
      - NGROK_HOST=${NGROK_HOST}
      - NGROK_ACCESS_KEY=${NGROK_ACCESS_KEY}
      - NGROK_SECRET_KEY=${NGROK_SECRET_KEY}
      - TFLOW_HOST=${TFLOW_HOST}
      - ON_PREMISES_POSTGRES_CONNECTION=${ON_PREMISES_POSTGRES_CONNECTION}
    env_file:
      - .env
    depends_on:
      - pgvector
      - minio
      - n8n
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 30s
      retries: 3
      start_period: 5s
    networks:
      - ai_network

  pgvector:
    image: pgvector/pgvector:pg17
    container_name: pgvector
    environment:
      - POSTGRES_USER=sqladmin
      - POSTGRES_PASSWORD=P@ssw0rd
      - POSTGRES_DB=postgres
    ports:
      - "5432:5432"
    volumes:
      - pgvector_data:/var/lib/postgresql/data
      - ./init-schema.sql:/docker-entrypoint-initdb.d/init-schema.sql:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U sqladmin"]
      interval: 30s
      timeout: 30s
      retries: 3
      start_period: 5s
    networks:
      - ai_network

  minio:
    image: minio/minio:latest
    container_name: minio
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      - MINIO_ROOT_USER=minioadmin
      - MINIO_ROOT_PASSWORD=minioadmin
    command: server /data --console-address ":9001"
    volumes:
      - minio_data:/data
      - minio_config:/root/.minio
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 30s
      timeout: 30s
      retries: 3
      start_period: 5s
    networks:
      - ai_network

  postgres:
    image: postgres:16-alpine
    container_name: postgres
    environment:
      - POSTGRES_USER=${POSTGRES_USER}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      - POSTGRES_DB=${POSTGRES_DB}
    ports:
      - "5433:5432"
    volumes:
      - postgres_n8n_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -h localhost -U $${POSTGRES_USER} -d $${POSTGRES_DB}"]
      interval: 5s
      timeout: 5s
      retries: 10
    networks:
      - ai_network

  n8n-import:
    <<: *service-n8n
    container_name: n8n-import
    hostname: n8n-import
    entrypoint: /bin/sh
    command:
      - "-c"
      - "n8n import:credentials --separate --input=/demo-data/credentials && n8n import:workflow --separate --input=/demo-data/workflows"
    volumes:
      - ./n8n/demo-data:/demo-data
    depends_on:
      postgres:
        condition: service_healthy

  n8n:
    <<: *service-n8n
    container_name: n8n
    hostname: n8n
    restart: unless-stopped
    ports:
      - 5678:5678
    volumes:
      - n8n_storage:/home/node/.n8n
      - ./n8n/demo-data:/demo-data
      - ./n8n/shared:/data/shared
      - ./n8n/exports:/home/node/.n8n/exports
    depends_on:
      postgres:
        condition: service_healthy
      n8n-import:
        condition: service_completed_successfully

  qdrant:
    image: qdrant/qdrant
    container_name: qdrant
    restart: unless-stopped
    ports:
      - 6333:6333
    volumes:
      - qdrant_storage:/qdrant/storage
    networks:
      - ai_network

  ollama-cpu:
    profiles: ["cpu"]
    <<: *service-ollama

  ollama-gpu:
    profiles: ["gpu-nvidia"]
    <<: *service-ollama
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

  ollama-gpu-amd:
    profiles: ["gpu-amd"]
    <<: *service-ollama
    image: ollama/ollama:rocm
    devices:
      - "/dev/kfd"
      - "/dev/dri"

  ollama-pull-llama-cpu:
    profiles: ["cpu"]
    <<: *init-ollama
    depends_on:
      - ollama-cpu

  ollama-pull-llama-gpu:
    profiles: ["gpu-nvidia"]
    <<: *init-ollama
    depends_on:
      - ollama-gpu

  ollama-pull-llama-gpu-amd:
    profiles: [gpu-amd]
    <<: *init-ollama
    image: ollama/ollama:rocm
    depends_on:
     - ollama-gpu-amd

  ai_meeting_chatbot_frontend:
    image: jccatomind/ai_meeting_chatbot_frontend:latest
    container_name: ai_meeting_chatbot_frontend
    restart: unless-stopped
    ports:
      - "3000:3000"
    environment:
      - VITE_N8N_BASE_URL=${VITE_N8N_BASE_URL}
    networks:
      - ai_network

volumes:
  pgvector_data:
  minio_data:
  minio_config:
  n8n_storage:
  ollama_storage:
  qdrant_storage:
  postgres_n8n_data:

networks:
  ai_network:
    driver: bridge
EOF
}

# Main execution
main() {
    echo -e "${YELLOW}🚀 Starting offline packaging process...${NC}"
    
    # Pull and save all images
    pull_and_save_images
    
    # Pull Ollama LLM model
    MODEL_NAME="deepseek-r1:70b-llama-distill-q8_0"
    echo -e "${YELLOW}📥 Pulling Ollama LLM model: $MODEL_NAME${NC}"
    docker run --rm -v $(pwd)/ollama_storage:/root/.ollama ollama/ollama:latest ollama pull $MODEL_NAME

    echo -e "${YELLOW}📦 Packaging ollama_storage directory...${NC}"
    tar czf ollama_storage.tar.gz ollama_storage
    
    # Create load script
    create_load_script
    
    # Create installation guide
    create_installation_guide
    
    # Create offline docker-compose
    create_offline_compose
    
    # Create package summary
    echo -e "${GREEN}📊 Package Summary:${NC}"
    echo "Total images packaged: $(ls *.tar 2>/dev/null | wc -l)"
    echo "Total package size: $(du -sh . | cut -f1)"
    
    echo -e "${GREEN}✅ Offline package created successfully!${NC}"
    echo -e "${YELLOW}📁 Package location: $(pwd)${NC}"
    echo -e "${YELLOW}📋 Next steps:${NC}"
    echo "1. Transfer the entire directory to your offline system"
    echo "2. Run: ./load-images.sh"
    echo "3. Run: docker-compose -f docker-compose-offline.yaml up -d"
}

# Run main function
main "$@" 