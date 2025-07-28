# AI Meeting Minutes Backend API Documentation

## Overview

This document provides comprehensive documentation for the AI Meeting Minutes backend API. The application supports both cloud (Azure) and on-premises deployments, providing transcription services, speaker identification, voiceprint management, and integration with TFlow.

**Base URL**: `http://localhost:5000` (development)

**Environment Mode**: Controlled by `ON_PREMISES_MODE` environment variable
- `on_cloud`: Uses Azure services
- `on_premises`: Uses MinIO and local services

---

## Table of Contents

1. [Frontend Pages](#frontend-pages)
2. [File Upload & Management](#file-upload--management)
3. [Azure Transcription Services](#azure-transcription-services)
4. [Fanolab Transcription Services](#fanolab-transcription-services)
5. [Voiceprint Management](#voiceprint-management)
6. [TFlow Integration Services](#tflow-integration-services)
7. [Error Handling](#error-handling)
8. [Data Models](#data-models)

---

## Frontend Pages

### Get Upload Page
- **URL**: `/`
- **Method**: `GET`
- **Description**: Returns the main file upload HTML page
- **Response**: HTML page for uploading MP4/WAV files

### Get Fano Extract Page
- **URL**: `/fano-extract`
- **Method**: `GET`
- **Description**: Returns the Fanolab speaker extraction HTML page
- **Response**: HTML page for Fanolab speaker clip extraction

---

## File Upload & Management

### Upload File
- **URL**: `/upload/file`
- **Method**: `POST`
- **Content-Type**: `multipart/form-data`
- **Description**: Uploads MP4 or WAV files to cloud storage and returns a shareable URL

**Request Parameters:**
```
Form Data:
- file: (file) MP4 or WAV file (required)
```

**Response:**
```json
{
  "sas_url": "https://storage.url/path/to/file?sas_token"
}
```

**Error Responses:**
```json
{
  "error": "No file provided"
}
```
```json
{
  "error": "Unsupported file type. Only MP4 and WAV files are supported."
}
```
```json
{
  "error": "Failed to upload file to Azure/MinIO Storage"
}
```

---

## Azure Transcription Services

### Azure Transcription
- **URL**: `/azure_transcription`
- **Method**: `POST`
- **Content-Type**: `application/json`
- **Description**: Gets transcription results from Azure Speech Services with speaker diarization and voiceprint matching

**Request Body:**
```json
{
  "url": "https://azure.transcription.url",
  "application_owner": "company_name",
  "confidence_threshold": 0.8
}
```

**Response:**
```json
[
  {
    "sys_id": 12345,
    "source_url": "https://storage.url/media.mp4",
    "speaker_stats": {
      "1": {
        "total_duration": 120.5,
        "total_words": 250,
        "percentage": 45.2,
        "words_per_minute": 124.6,
        "identified_name": "John Doe",
        "confidence": 0.92,
        "segments": []
      }
    },
    "total_duration": 267.3,
    "transcriptions": [
      "Speaker-1 (00:00:10 - 00:00:15): Hello everyone, welcome to the meeting."
    ]
  }
]
```

### Azure Extract Speaker Clips
- **URL**: `/azure_extract_speaker_clip`
- **Method**: `POST`
- **Content-Type**: `application/json`
- **Description**: Extracts audio segments for each speaker and returns a downloadable zip file

**Request Body:**
```json
{
  "source_url": "https://storage.url/media.mp4",
  "azure_url": "https://azure.transcription.url"
}
```

**Response:**
```json
{
  "download_url": "https://storage.url/speaker_clips.zip"
}
```

### Azure Match Speaker Voiceprint
- **URL**: `/azure_match_speaker_voiceprint`
- **Method**: `POST`
- **Content-Type**: `application/json`
- **Description**: Matches speakers from transcription against voiceprint library

**Request Body:**
```json
{
  "source_url": "https://storage.url/media.mp4",
  "azure_url": "https://azure.transcription.url",
  "application_owner": "company_name",
  "confidence_threshold": 0.8
}
```

**Response:**
```json
{
  "speaker": "Speaker-1: John Doe (92.50%)\nSpeaker-2: Jane Smith (87.30%)"
}
```

### Azure Upload Media
- **URL**: `/azure_upload_media`
- **Method**: `POST`
- **Content-Type**: `application/json`
- **Description**: Downloads media from URL and uploads to Azure storage

**Request Body:**
```json
{
  "data": ["https://external.url/media.mp4"]
}
```

**Response:**
```json
{
  "sas_url": "https://storage.url/media.mp4?sas_token"
}
```

---

## Fanolab Transcription Services

### Submit Fanolab Transcription
- **URL**: `/fanolab_submit_transcription`
- **Method**: `POST`
- **Content-Type**: `application/json`
- **Description**: Submits audio file to Fanolab API for transcription processing

**Request Body:**
```json
{
  "source_url": "https://storage.url/media.mp4",
  "language_code": "yue-x-auto",
  "enable_auto_punctuation": false,
  "application_owner": "company_name"
}
```

**Response:**
```json
{
  "name": "projects/xxx/operations/operation_id"
}
```

### Get Fanolab Transcription
- **URL**: `/fanolab_transcription`
- **Method**: `POST`
- **Content-Type**: `application/json`
- **Description**: Retrieves transcription results from Fanolab API

**Request Body:**
```json
{
  "sys_id": 12345,
  "source_url": "https://storage.url/media.mp4",
  "fanolab_id": "operation_id",
  "application_owner": "company_name",
  "confidence_threshold": 0.8
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Transcription completed successfully",
  "sys_id": 12345,
  "source_url": "https://storage.url/media.mp4",
  "speaker_stats": {
    "1": {
      "total_duration": 120.5,
      "total_words": 250,
      "percentage": 45.2,
      "words_per_minute": 124.6,
      "identified_name": "John Doe",
      "confidence": 0.92
    }
  },
  "total_duration": 267.3,
  "transcriptions": [
    "Speaker-1 (00:00:10 - 00:00:15): Hello everyone, welcome to the meeting."
  ]
}
```

### Fanolab Extract Speaker Clips
- **URL**: `/fanolab_extract_speaker_clip`
- **Method**: `POST`
- **Content-Type**: `application/json`
- **Description**: Extracts speaker audio segments using Fanolab transcription results

**Request Body:**
```json
{
  "source_url": "https://storage.url/media.mp4",
  "fanolab_id": "operation_id"
}
```

**Response:**
```json
{
  "download_url": "https://storage.url/speaker_clips.zip"
}
```

### Upload Fano Extract Speaker Clip
- **URL**: `/upload/fano_extract_speaker_clip`
- **Method**: `POST`
- **Content-Type**: `application/json`
- **Description**: Web interface endpoint for Fanolab speaker extraction

**Request Body:**
```json
{
  "source_url": "https://storage.url/media.mp4",
  "fanolab_id": "operation_id"
}
```

### Fanolab Match Speaker Voiceprint
- **URL**: `/fanolab_match_speaker_voiceprint`
- **Method**: `POST`
- **Content-Type**: `application/json`
- **Description**: Matches speakers against voiceprint library using Fanolab results

**Request Body:**
```json
{
  "source_url": "https://storage.url/media.mp4",
  "fanolab_id": "operation_id",
  "application_owner": "company_name",
  "confidence_threshold": 0.8
}
```

**Response:**
```json
{
  "speaker": "Speaker-1: John Doe (92.50%)\nSpeaker-2: unknown (0.00%)"
}
```

---

## Voiceprint Management

### Insert Voiceprint
- **URL**: `/insert_voiceprint`
- **Method**: `POST`
- **Content-Type**: `multipart/form-data`
- **Description**: Adds new voiceprint entries to the library

**Request Parameters:**
```
Form Data:
- name: (string) Person's name (required)
- email: (string) Email address
- department: (string) Department
- position: (string) Job position
- application_owner: (string) Application owner (required)
- audio_files: (file[]) Array of WAV files (required)
```

**Response:**
```json
{
  "message": "All voiceprints inserted successfully!"
}
```

**Error Response:**
```json
{
  "error": "Missing required fields: name, audio_files, and application_owner are required."
}
```

### Search Voiceprint
- **URL**: `/search_voiceprint`
- **Method**: `POST`
- **Content-Type**: `application/json`
- **Description**: Searches for matching voiceprints in the library

**Request Body:**
```json
{
  "path": "/path/to/audio.wav",
  "application_owner": "company_name"
}
```

**Response:**
```json
[
  {
    "sys_id": 1,
    "name": "John Doe",
    "email": "john.doe@company.com",
    "department": "Engineering",
    "position": "Senior Developer",
    "metadata": {"application_owner": "company_name"},
    "similarity": 0.92
  }
]
```

---

## TFlow Integration Services

### Get Project List
- **URL**: `/tflow_get_project_list`
- **Method**: `POST`
- **Content-Type**: `application/json`
- **Description**: Retrieves project list with glossary from TFlow

**Request Body:**
```json
{
  "app_key": "tflow_app_key",
  "sign": "tflow_signature",
  "page_size": 50
}
```

**Response:**
```json
{
  "data": [
    {
      "project": "Project Alpha",
      "overview": "Project description",
      "start_date": "2024-01-01",
      "glossary_list": [
        {
          "term": "API",
          "meaning": "Application Programming Interface"
        }
      ]
    }
  ]
}
```

### Get Project Memory
- **URL**: `/tflow_get_project_memory`
- **Method**: `POST`
- **Content-Type**: `application/json`
- **Description**: Retrieves project memory records from TFlow

**Request Body:**
```json
{
  "app_key": "tflow_app_key",
  "sign": "tflow_signature",
  "page_size": 50,
  "project_name": "Project Alpha"
}
```

**Response:**
```json
{
  "data": [
    {
      "project": "Project Alpha",
      "datetime": "2024-01-15 10:00:00",
      "memory": "Meeting summary text",
      "meeting_minutes_rowid": "12345"
    }
  ]
}
```

### Get Meeting Minutes
- **URL**: `/tflow_get_meeting_minutes`
- **Method**: `POST`
- **Content-Type**: `application/json`
- **Description**: Retrieves detailed meeting minutes with speaker data

**Request Body:**
```json
{
  "app_key": "tflow_app_key",
  "sign": "tflow_signature",
  "meeting_rowid": "12345"
}
```

**Response:**
```json
{
  "rowid": "12345",
  "datetime": "2024-01-15 10:00:00",
  "video_name": "meeting_recording.mp4",
  "description": "Weekly team meeting",
  "duration_minutes": 45,
  "speaker_data": [
    {
      "speaker": "1",
      "name": "John Doe",
      "talk_time_percentage": "45%",
      "total_talk_time_minutes": 20,
      "words_per_minutes": 120
    }
  ],
  "transcript": "Full meeting transcript text"
}
```

### Get Dashboard
- **URL**: `/tflow_get_dashboard`
- **Method**: `POST`
- **Content-Type**: `application/json`
- **Description**: Retrieves dashboard analytics data from TFlow

**Request Body:**
```json
{
  "app_key": "tflow_app_key",
  "sign": "tflow_signature",
  "dashboard_name": "time_spent_on_project",
  "start_dt": "2024-01-01",
  "end_dt": "2024-01-31"
}
```

**Dashboard Types:**
- `time_spent_on_project`: Time spent by project (with pie chart)
- `no_of_meeting_by_project`: Number of meetings by project (with bar chart)
- `time_spent_on_project_by_staff`: Time spent by staff per project (with stacked bar chart)
- `contribution_leaderboard`: Staff contribution leaderboard

**Response:**
```json
{
  "data": [
    {
      "project": "Project Alpha",
      "total_duration_minutes": 1200
    }
  ],
  "chart_url": "https://quickchart.io/chart?c=..."
}
```

---

## Error Handling

### Standard Error Response Format
```json
{
  "error": "Error description message"
}
```

### Common HTTP Status Codes
- `200`: Success
- `400`: Bad Request (missing parameters, invalid data)
- `403`: Forbidden (quota exceeded)
- `500`: Internal Server Error

### Quota Errors
When quota limits are exceeded:
```json
{
  "error": "Quota exceeded. Contact administrator."
}
```

---

## Data Models

### Speaker Statistics
```typescript
interface SpeakerStats {
  total_duration: number;        // Duration in seconds
  total_words: number;          // Word count
  percentage: number;           // Percentage of total talk time
  words_per_minute: number;     // Speaking rate
  identified_name?: string;     // Matched name from voiceprint
  confidence?: number;          // Confidence score (0-1)
  segments: Array<{
    start: number;              // Start time in seconds
    end: number;                // End time in seconds
    duration: number;           // Segment duration
  }>;
}
```

### Voiceprint Entry
```typescript
interface VoiceprintEntry {
  sys_id: number;
  name: string;
  email?: string;
  department?: string;
  position?: string;
  metadata: {
    application_owner: string;
  };
  similarity: number;           // Similarity score (0-1)
}
```

---

## Environment Variables

Required environment variables:

```bash
# Deployment Mode
ON_PREMISES_MODE=on_cloud|on_premises

# Azure Configuration (for on_cloud mode)
AZURE_STT_API_KEY=your_azure_key
AZURE_CONTAINER_NAME=your_container
AZURE_ACCOUNT_NAME=your_account
AZURE_ACCOUNT_KEY=your_key

# Fanolab Configuration
FANOLAB_HOST=fano_host
FANOLAB_API_KEY=your_fanolab_key

# TFlow Configuration
TFLOW_HOST=https://your-tflow-instance.com

# Database Configuration
DATABASE_URL=postgresql://user:pass@host:port/db
```

---

## Notes

1. **File Size Limits**: No explicit file size limits are enforced in the API, but storage providers may have limits.

2. **Audio Formats**: Only MP4 and WAV files are supported for upload and processing.

3. **Voiceprint Matching**: Requires a confidence threshold (default 0.8) for speaker identification.

4. **Quota Management**: The system tracks usage hours per application owner and enforces quotas.

5. **Temporary Files**: All temporary files are automatically cleaned up after processing.

6. **Chart Generation**: Charts are generated using quickchart.io for cloud deployments; not available for on-premises deployments.

7. **Concurrent Processing**: The system handles multiple file uploads and processing requests concurrently. 