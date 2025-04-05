import os
from dotenv import load_dotenv
import requests
from pydub import AudioSegment
from flask import Flask, request, jsonify, send_from_directory
from utilities import mp4_to_wav_file, mp4_to_base64
from azure_service import upload_file_and_get_sas_url, delete_blob
import time

# Load environment variables
load_dotenv()

#Fano Lab API
# @app.route('/transcription_fanolab', methods=['POST'])
# def fanolab_transcription_b64(url: str):
#     # data = request.get_json()
#     # url = data.get('url')
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
#     return response.json()

AZURE_BLOB_NAME = 'temp_audio.wav'

def fanolab_transcription(url: str):
    """
    Receives a JSON request with an MP4 URL, converts it to WAV, and sends the file URL to FanoLab API.
    """
    # data = request.get_json()
    # url = data.get('url')

    if not url:
        return jsonify({"error": "URL is required"}), 400

    # Convert MP4 to WAV
    wav_path = mp4_to_wav_file(url)
    if not wav_path:
        return jsonify({"error": "Failed to process audio"}), 500

    # Upload audio file to Azure Blob Storage
    wav_url = upload_file_and_get_sas_url(file_path=wav_path, blob_name=AZURE_BLOB_NAME)
    if not wav_url:
        return jsonify({"error": "Failed to upload audio"}), 500

    # Prepare API request
    FANOLAB_API_KEY = os.getenv("FANOLAB_API_KEY")
    headers = {"Authorization": f"Bearer {FANOLAB_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "config": {
            "languageCode": "yue-x-auto",
            "maxAlternatives": 2,
            "enableSeparateRecognitionPerChannel": False,
            "enableAutomaticPunctuation": True
        },
        "enableWordTimeOffsets": True,
        "diarizationConfig": {
            "disableSpeakerDiarization": False
        },
        "audio": {
            "uri": wav_url
        }
    }

    # Send request to FanoLab API
    response = requests.post("https://portal-demo.fano.ai/speech/long-running-recognize", json=payload, headers=headers)

    if response:
        # Wait for 5 seconds before deleting the blob
        time.sleep(5)
        delete_blob(blob_name=AZURE_BLOB_NAME)

    return response.json()

if __name__ == '__main__':
    soruce_url = "https://catomindst.blob.core.windows.net/meeting/Call%20with%20Bin%20Dong/Call%20with%20Bin%20Dong-20250206_095433-Meeting%20Recording.mp4?sv=2023-01-03&st=2025-03-27T03%3A29%3A02Z&se=2026-03-28T03%3A29%3A00Z&sr=b&sp=r&sig=RrEeHA%2BCDXSeXLMmeYmnUpUAB%2Fl2516fIJosEDwkr4s%3D"
    response = fanolab_transcription(url=soruce_url)
    print(response)