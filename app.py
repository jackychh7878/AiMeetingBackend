import os
from dotenv import load_dotenv
from flask import Flask, request, jsonify, send_from_directory, render_template_string
import requests
from pydub import AudioSegment
from openai import AsyncAzureOpenAI

from src.enums import OnPremiseMode
from src.voiceprint_library_service import search_voiceprint, insert_voiceprint
from src.azure_service import azure_transcription, azure_extract_speaker_clip, azure_match_speaker_voiceprint, azure_upload_media_and_get_sas_url, azure_upload_file_and_get_sas_url
from src.fanolab_service import fanolab_submit_transcription, fanolab_transcription, fanolab_extract_speaker_clip, fanolab_match_speaker_voiceprint
from src.tflow_service import get_meeting_minutes, get_project_list, get_project_memory, get_dashboard
from src.blob_storage_service import minio_upload_and_share, minio_delete_blob
import uuid
from datetime import timedelta

# Load environment variables
load_dotenv()
app = Flask(__name__)

# On cloud or on premises
ON_PREMISES_MODE = os.getenv("ON_PREMISES_MODE")

# HTML template for the frontend
UPLOAD_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Meeting Minutes Upload</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .upload-section {
            margin-bottom: 20px;
            padding: 20px;
            border: 2px dashed #ccc;
            border-radius: 4px;
            text-align: center;
        }
        input[type="file"] {
            width: 100%;
            padding: 8px;
            margin: 8px 0;
            border: 1px solid #ddd;
            border-radius: 4px;
        }
        button {
            background-color: #007bff;
            color: white;
            padding: 10px 20px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
        }
        button:hover {
            background-color: #0056b3;
        }
        button:disabled {
            background-color: #ccc;
            cursor: not-allowed;
        }
        #result {
            margin-top: 20px;
            padding: 10px;
            border-radius: 4px;
            display: none;
            white-space: pre-line;
        }
        .success {
            background-color: #d4edda;
            color: #155724;
        }
        .error {
            background-color: #f8d7da;
            color: #721c24;
        }
        .copy-button {
            background-color: #28a745;
            margin-top: 10px;
        }
        .copy-button:hover {
            background-color: #218838;
        }
        .url-container {
            margin-top: 10px;
            padding: 10px;
            background-color: #f8f9fa;
            border-radius: 4px;
            word-break: break-all;
        }
        .spinner {
            display: none;
            width: 40px;
            height: 40px;
            margin: 20px auto;
            border: 4px solid #f3f3f3;
            border-top: 4px solid #007bff;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .upload-status {
            text-align: center;
            margin-top: 10px;
            color: #666;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Meeting Minutes Upload (wav or mp4 only)</h1>
        
        <div class="upload-section">
            <form id="uploadForm" enctype="multipart/form-data">
                <input type="file" id="fileInput" accept=".mp4,.wav" required>
                <button type="submit" id="uploadButton">Upload File</button>
            </form>
            <div class="spinner" id="spinner"></div>
            <div class="upload-status" id="uploadStatus"></div>
        </div>

        <div id="result"></div>
    </div>

    <script>
        function showResult(message, isError = false, sasUrl = null) {
            const resultDiv = document.getElementById('result');
            
            if (isError) {
                resultDiv.innerHTML = message;
            } else {
                resultDiv.innerHTML = `
                    <div>Paste the following url to "Meeting Url (only support wav or mp4)" field:</div>
                    <div class="url-container">${sasUrl}</div>
                `;
            }
            
            resultDiv.style.display = 'block';
            resultDiv.className = isError ? 'error' : 'success';
        }

        async function copyToClipboard(text) {
            try {
                await navigator.clipboard.writeText(text);
                const button = document.querySelector('.copy-button');
                const originalText = button.textContent;
                button.textContent = 'Copied!';
                setTimeout(() => {
                    button.textContent = originalText;
                }, 2000);
            } catch (err) {
                console.error('Failed to copy text: ', err);
            }
        }

        function setLoading(isLoading) {
            const spinner = document.getElementById('spinner');
            const uploadButton = document.getElementById('uploadButton');
            const uploadStatus = document.getElementById('uploadStatus');
            const fileInput = document.getElementById('fileInput');
            
            if (isLoading) {
                spinner.style.display = 'block';
                uploadButton.disabled = true;
                fileInput.disabled = true;
                uploadStatus.textContent = 'Uploading...';
            } else {
                spinner.style.display = 'none';
                uploadButton.disabled = false;
                fileInput.disabled = false;
                uploadStatus.textContent = '';
            }
        }

        document.getElementById('uploadForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const fileInput = document.getElementById('fileInput');
            const file = fileInput.files[0];
            
            if (!file) {
                showResult('Please select a file', true);
                return;
            }

            // Check file type
            const fileType = file.name.split('.').pop().toLowerCase();
            if (!['mp4', 'wav'].includes(fileType)) {
                showResult('Only MP4 and WAV files are supported', true);
                return;
            }

            setLoading(true);
            const formData = new FormData();
            formData.append('file', file);

            try {
                const response = await fetch('/upload/file', {
                    method: 'POST',
                    body: formData
                });
                const data = await response.json();
                
                if (response.ok) {
                    showResult('', false, data.sas_url);
                } else {
                    showResult(data.error || 'Upload failed', true);
                }
            } catch (error) {
                showResult('Error uploading file', true);
            } finally {
                setLoading(false);
            }
        });
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(UPLOAD_TEMPLATE)

@app.route('/upload/file', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
            
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400
            
        # Get file extension
        file_type = file.filename.rsplit('.', 1)[1].lower()
        if file_type not in ['mp4', 'wav']:
            return jsonify({"error": "Unsupported file type. Only MP4 and WAV files are supported."}), 400
            
        # Generate unique filename
        unique_id = str(uuid.uuid4())
        temp_filepath = os.path.join('uploads', f"temp_{unique_id}.{file_type}")
        
        try:
            # Save the file temporarily
            file.save(temp_filepath)
            
            # Generate blob name
            blob_name = f"media/{unique_id}.{file_type}"

            # Upload with 1-year expiry
            # Upload to Azure
            if ON_PREMISES_MODE == OnPremiseMode.ON_CLOUD.value:
                sas_url = azure_upload_file_and_get_sas_url(
                    file_path=temp_filepath,
                    blob_name=blob_name,
                    expiry_date=timedelta(days=365)
                )

                if not sas_url:
                    return jsonify({"error": "Failed to upload file to Azure"}), 500

                return jsonify({"sas_url": sas_url})

            # Upload to MinIO
            elif ON_PREMISES_MODE == OnPremiseMode.ON_PREMISES.value:
                sas_url = minio_upload_and_share(
                    file_path=temp_filepath,
                    bucket="meeting-minutes",
                    blob_name=blob_name,
                    expiry_date=timedelta(days=7)
                )

                if not sas_url:
                    return jsonify({"error": "Failed to upload file to MinIO Storage"}), 500

                return jsonify({"sas_url": sas_url})
            # Incorrect env variable
            else:
                return jsonify({"error": "Failed to upload file to Blob Storage: Incorrect env variable"}), 500
        finally:
            # Clean up temporary file
            if os.path.exists(temp_filepath):
                os.remove(temp_filepath)
                
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# @app.route('/upload/url', methods=['POST'])
# def upload_url():
#     return azure_upload_media_and_get_sas_url(request)

@app.route('/azure_transcription', methods=['POST'])
def azure_transcription_api():
    try:
        result = azure_transcription(request)
        return result
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/fanolab_submit_transcription', methods=['POST'])
def fanolab_submit_transcription_api():
    try:
        result = fanolab_submit_transcription(request)
        return result
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/fanolab_transcription', methods=['POST'])
def fanolab_transcription_api():
    try:
        result = fanolab_transcription(request)
        return result
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/fanolab_extract_speaker_clip', methods=['POST'])
def fanolab_extract_speaker_clip_api():
    try:
        result = fanolab_extract_speaker_clip(request)
        return result
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/fanolab_match_speaker_voiceprint', methods=['POST'])
def fanolab_match_speaker_voiceprint_api():
    try:
        result = fanolab_match_speaker_voiceprint(request)
        return result
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/insert_voiceprint', methods=['POST'])
def insert_voiceprint_api():
    try:
        result = insert_voiceprint(request)
        return result
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/search_voiceprint', methods=['POST'])
def search_voiceprint_api():
    try:
        data = request.json
        if not data or 'path' not in data or 'application_owner' not in data:
            return jsonify({'error': 'Both path and application_owner are required'}), 400
        result = search_voiceprint(data.get('path'), data.get('application_owner'))
        return result
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/azure_extract_speaker_clip', methods=['POST'])
def azure_extract_speaker_clip_api():
    try:
        result = azure_extract_speaker_clip(request)
        return result
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/azure_match_speaker_voiceprint', methods=['POST'])
def azure_match_speaker_voiceprint_api():
    try:
        result = azure_match_speaker_voiceprint(request)
        return result
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/azure_upload_media', methods=['POST'])
def azure_upload_media_api():
    try:
        result = azure_upload_media_and_get_sas_url(request)
        return result
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/tflow_get_project_list', methods=['POST'])
def tflow_get_project_list_api():
    try:
        result = get_project_list(request)
        return result
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/tflow_get_project_memory', methods=['POST'])
def tflow_get_project_memory_api():
    try:
        result = get_project_memory(request)
        return result
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/tflow_get_meeting_minutes', methods=['POST'])
def tflow_get_meeting_minutes_api():
    try:
        result = get_meeting_minutes(request)
        return result
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/tflow_get_dashboard', methods=['POST'])
def tflow_get_dashboard_api():
    try:
        result = get_dashboard(request)
        return result
    except Exception as e:
        return jsonify({"error": str(e)})

# @app.route('/minio_upload_blob', methods=['POST'])
# def minio_upload_blob_api():
#     try:
#         data = request.get_json()
#
#         mp4_url = data.get('source_url')
#         fanolab_id = data.get('fanolab_id')
#
#         result = minio_upload_and_share(file_path)
#         return result
#     except Exception as e:
#         return jsonify({"error": str(e)})

if __name__ == '__main__':
    # app.run(debug=True)
    app.run(debug=True, use_debugger=False, use_reloader=False)