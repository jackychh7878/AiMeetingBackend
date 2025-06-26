# AiMeetingMinutes

## Introduction

<!-- TODO: Add a detailed project introduction here -->

This project combines an AI-powered meeting backend with a self-hosted n8n automation and AI workflow stack, including vector database, MinIO, and Ollama for local LLMs.

## Prerequisites
- [Docker](https://www.docker.com/get-started)
- [Docker Compose](https://docs.docker.com/compose/)

## Getting Started

1. **Clone the repository:**
   ```sh
   git clone <your-repo-url>
   cd AiMeetingMinutes
   ```

2. **Configure environment variables:**
   - Copy or create a `.env` file in the project root and fill in the required values.

3. **Start all services (default: CPU profile):**
   ```sh
   docker compose --profile cpu up
   ```
   - For Nvidia GPU:
     ```sh
     docker compose --profile gpu-nvidia up
     ```
   - For AMD GPU:
     ```sh
     docker compose --profile gpu-amd up
     ```

4. **Access the services:**
   - Backend API: [http://localhost:8000](http://localhost:8000)
   - n8n Automation: [http://localhost:5678](http://localhost:5678)
   - MinIO Console: [http://localhost:9001](http://localhost:9001)
   - Qdrant: [http://localhost:6333](http://localhost:6333)

## Folder Structure
- `src/` - Backend source code
- `n8n/` - n8n demo-data and shared folders
- `docker-compose.yaml` - Main compose file for all services

## Notes
- n8n and the backend share the same Postgres database for simplicity.
- Ollama supports CPU, Nvidia GPU, and AMD GPU profiles. Select the appropriate profile for your hardware.
- Demo workflows and credentials for n8n are included in `n8n/demo-data`.

## TODO
- [ ] Add detailed project introduction
- [ ] Add API documentation
- [ ] Add workflow examples
- [ ] Add troubleshooting and FAQ