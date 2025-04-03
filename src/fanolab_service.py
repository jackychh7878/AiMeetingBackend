import os
from dotenv import load_dotenv
import requests
from pydub import AudioSegment
from flask import Flask, request, jsonify, send_from_directory
from utilities import mp4_to_wav_file

# Load environment variables
load_dotenv()

#Fano Lab API
# @app.route('/transcription_fanolab', methods=['POST'])
# def call_speech_to_text_api():
#     data = request.get_json()
#     url = data.get('url')
#
#     audio_base64 = mp4_to_base64(mp4_url=url)
#
#     FANOLAB_API_KEY = os.getenv("FANOLAB_API_KEY")
#     headers = {"Authorization": f"Bearer {FANOLAB_API_KEY}", "Content-Type": "application/json"}
#     payload = {
#       "config": {
#         "languageCode": "yue",
#         "maxAlternatives": 2,
#         "enableSeparateRecognitionPerChannel": False,
#         "enableAutomaticPunctuation": True
#         },
#         "enableWordTimeOffsets": True,
#         "diarizationConfig": {
#             "disableSpeakerDiarization": False
#         },
#         "audio": {
#             "content": audio_base64
#         }
#     }
#     response = requests.post("https://portal-demo.fano.ai/speech/long-running-recognize", json=payload, headers=headers)

# @app.route('/transcription_fanolab', methods=['POST'])
def call_speech_to_text_api():
    """
    Receives a JSON request with an MP4 URL, converts it to WAV, and sends the file URL to FanoLab API.
    """
    data = request.get_json()
    url = data.get('url')

    if not url:
        return jsonify({"error": "URL is required"}), 400

    # Convert MP4 to WAV
    wav_path = mp4_to_wav_file(url)
    if not wav_path:
        return jsonify({"error": "Failed to process audio"}), 500

    # Generate the file URL
    AZURE_URL = "https://transcribe-video-api-bwbkcsh6c3daarg4.eastasia-01.azurewebsites.net/"
    file_url = f"{AZURE_URL}/uploads/audio.wav" # Replace with actual domain if hosted

    # Prepare API request
    FANOLAB_API_KEY = os.getenv("FANOLAB_API_KEY")
    headers = {"Authorization": f"Bearer {FANOLAB_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "config": {
            "languageCode": "yue",
            "maxAlternatives": 2,
            "enableSeparateRecognitionPerChannel": False,
            "enableAutomaticPunctuation": True
        },
        "enableWordTimeOffsets": True,
        "diarizationConfig": {
            "disableSpeakerDiarization": False
        },
        "audio": {
            "uri": file_url  # Using URL instead of base64 content
        }
    }

    # Send request to FanoLab API
    response = requests.post("https://portal-demo.fano.ai/speech/long-running-recognize", json=payload, headers=headers)

    return response.json()