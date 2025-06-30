# Offline Docker Image Packaging Script for AI Meeting Minutes (Windows PowerShell)
# This script packages all required Docker images for offline installation

param(
    [string]$PackageDir = "docker-images-offline"
)

# Error handling
$ErrorActionPreference = "Stop"

# Colors for output
$Red = "Red"
$Green = "Green"
$Yellow = "Yellow"

Write-Host "=== AI Meeting Minutes - Offline Image Packaging ===" -ForegroundColor $Green

# Create package directory
New-Item -ItemType Directory -Force -Path $PackageDir | Out-Null
Set-Location $PackageDir

# Create list of required images
$ImagesFile = "required-images.txt"
@"
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
"@ | Out-File -FilePath $ImagesFile -Encoding UTF8

Write-Host "📋 Required images list created: $ImagesFile" -ForegroundColor $Yellow

# Function to pull and save images
function Pull-AndSave-Images {
    Write-Host "🔍 Pulling and saving Docker images..." -ForegroundColor $Yellow
    
    $images = Get-Content $ImagesFile | Where-Object { $_ -notmatch '^\s*#' -and $_.Trim() -ne '' }
    
    foreach ($image in $images) {
        $image = $image.Trim()
        Write-Host "📥 Pulling: $image" -ForegroundColor $Green
        docker pull $image
        
        # Create safe filename
        $safeName = $image -replace '[^a-zA-Z0-9._-]', '-'
        $tarFile = "$safeName.tar"
        Write-Host "💾 Saving: $image -> $tarFile" -ForegroundColor $Green
        docker save $image -o $tarFile
    }
}

# Function to create load script
function Create-LoadScript {
    $loadScript = @"
# Docker Image Loading Script for Offline Installation (Windows PowerShell)
# Run this script on the target system to load all images

`$ErrorActionPreference = "Stop"

Write-Host "=== Loading Docker Images ===" -ForegroundColor Green

# Load all .tar files
`$tarFiles = Get-ChildItem -Filter "*.tar"
foreach (`$tarFile in `$tarFiles) {
    Write-Host "📦 Loading: `$(`$tarFile.Name)" -ForegroundColor Yellow
    docker load -i `$tarFile.FullName
}

Write-Host "✅ All images loaded successfully!" -ForegroundColor Green
Write-Host "💡 You can now run: docker-compose up -d" -ForegroundColor Yellow
"@

    $loadScript | Out-File -FilePath "load-images.ps1" -Encoding UTF8
}

# Function to create installation guide
function Create-InstallationGuide {
    $guide = @"
# AI Meeting Minutes - Offline Installation Guide

## Prerequisites

- Docker Desktop for Windows
- Docker Compose 2.0+
- At least 8GB RAM
- 50GB+ free disk space
- NVIDIA GPU (optional, for GPU acceleration)

## Installation Steps

### 1. Transfer Files
Copy the entire package directory to your offline system.

### 2. Load Docker Images
```powershell
cd docker-images-offline
.\load-images.ps1
```

### 3. Configure Environment
Copy the `.env` file to the same directory as your `docker-compose.yaml`:
```powershell
Copy-Item .env.example .env
# Edit .env with your configuration
```

### 4. Start Services
```powershell
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
```powershell
docker-compose ps
```

### View Logs
```powershell
docker-compose logs -f [service-name]
```

### Reset Everything
```powershell
docker-compose down -v
docker-compose up -d
```

## Security Notes

- Change default passwords in `.env` file
- Configure Windows Firewall rules
- Use HTTPS in production
- Regularly update images when possible
"@

    $guide | Out-File -FilePath "INSTALLATION_GUIDE.md" -Encoding UTF8
}

# Function to create offline docker-compose
function Create-OfflineCompose {
    $composeContent = Get-Content "../docker-compose.yaml" -Raw
    $composeContent | Out-File -FilePath "docker-compose-offline.yaml" -Encoding UTF8
}

# Main execution
Write-Host "🚀 Starting offline packaging process..." -ForegroundColor $Yellow

# Pull and save all images
Pull-AndSave-Images

# Pull Ollama LLM model
$ModelName = "deepseek-r1:70b-llama-distill-q8_0"
Write-Host "Pulling Ollama LLM model: $ModelName" -ForegroundColor $Yellow
docker run --rm -v "$PWD\ollama_storage:/root/.ollama" ollama/ollama:latest ollama pull $ModelName

Write-Host "Packaging ollama_storage directory..." -ForegroundColor $Yellow
Compress-Archive -Path ollama_storage -DestinationPath ollama_storage.zip

# Create load script
Create-LoadScript

# Create installation guide
Create-InstallationGuide

# Create offline docker-compose
Create-OfflineCompose

# Create package summary
Write-Host "📊 Package Summary:" -ForegroundColor $Green
$tarCount = (Get-ChildItem -Filter "*.tar" | Measure-Object).Count
Write-Host "Total images packaged: $tarCount"
$packageSize = (Get-ChildItem | Measure-Object -Property Length -Sum).Sum / 1GB
Write-Host "Total package size: $([math]::Round($packageSize, 2)) GB"

Write-Host "✅ Offline package created successfully!" -ForegroundColor $Green
Write-Host "📁 Package location: $(Get-Location)" -ForegroundColor $Yellow
Write-Host "📋 Next steps:" -ForegroundColor $Yellow
Write-Host "1. Transfer the entire directory to your offline system"
Write-Host "2. Run: .\load-images.ps1"
Write-Host "3. Run: docker-compose -f docker-compose-offline.yaml up -d" 