import os
from dotenv import load_dotenv
from flask import Flask, request, jsonify, send_from_directory
import requests
from pydub import AudioSegment
from openai import AsyncAzureOpenAI
from src.voiceprint_library_service import search_voiceprint, insert_voiceprint
from src.azure_service import azure_transcription, azure_extract_speaker_clip, azure_match_speaker_voiceprint
from src.fanolab_service import fanolab_submit_transcription, fanolab_transcription
from src.tflow_service import get_meeting_minutes, get_project_list, get_project_memory, get_dashboard

# Load environment variables
load_dotenv()
app = Flask(__name__)


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


if __name__ == '__main__':
    app.run(debug=True)
    # app.run(debug=True, use_debugger=False, use_reloader=False)