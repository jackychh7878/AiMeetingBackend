import os
from dotenv import load_dotenv
from flask import Flask, request, jsonify, send_from_directory
import requests
from pydub import AudioSegment
from openai import AsyncAzureOpenAI
from src.voiceprint_library_service import search_voiceprint, insert_voiceprint
from src.azure_service import azure_transcription

# Load environment variables
load_dotenv()
app = Flask(__name__)


@app.route('/transcription', methods=['POST'])
def azure_transcription_api():
    try:
        data = request.json
        result = azure_transcription(data)

        return result, 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500



@app.route('/insert_voiceprint', methods=['POST'])
def insert_voiceprint_api():
    try:
        result = insert_voiceprint(request)
        return result, 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# @app.route('/search_voiceprint', methods=['POST'])
# def search_voiceprint_api():
#     try:
#         data = request.json
#         result = search_voiceprint(data)
#         return result, 200
#     except Exception as e:
#         return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)