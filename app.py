import os
from dotenv import load_dotenv
from flask import Flask, request, jsonify, send_from_directory
import requests
from pydub import AudioSegment
from openai import AsyncAzureOpenAI
from src.voiceprint_library_service import search_voiceprint, insert_voiceprint
from src.azure_service import azure_transcription, azure_extract_speaker_clip, azure_match_speaker_voiceprint
from src.fanolab_service import fanolab_submit_transcription, fanolab_transcription

# Load environment variables
load_dotenv()
app = Flask(__name__)


@app.route('/azure_transcription', methods=['POST'])
def azure_transcription_api():
    try:
        result = azure_transcription(request)
        return result, 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/fanolab_submit_transcription', methods=['POST'])
def fanolab_submit_transcription_api():
    try:
        result = fanolab_submit_transcription(request)
        return result, 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/fanolab_transcription', methods=['POST'])
def fanolab_transcription_api():
    try:
        result = fanolab_transcription(request)
        return result, 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/insert_voiceprint', methods=['POST'])
def insert_voiceprint_api():
    try:
        result = insert_voiceprint(request)
        return result, 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/search_voiceprint', methods=['POST'])
def search_voiceprint_api():
    try:
        data = request.json
        result = search_voiceprint(data.get('path'))
        return result, 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/azure_extract_speaker_clip', methods=['POST'])
def azure_extract_speaker_clip_api():
    try:
        result = azure_extract_speaker_clip(request)

        return result, 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/azure_match_speaker_voiceprint', methods=['POST'])
def azure_match_speaker_voiceprint_api():
    try:
        result = azure_match_speaker_voiceprint(request)
        return result, 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)