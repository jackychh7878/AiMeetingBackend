import os
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from pydantic import BaseModel
import requests
from utilities import check_status, fetch_completed_transcription, mp4_to_base64

# Load environment variables
load_dotenv()
app = Flask(__name__)


@app.route('/transcription', methods=['POST'])
def transcription():
    data = request.get_json()
    url = data.get('url')
    try:
        content_url_list = check_status(url)
        if content_url_list != "In Progress":
            output_list = []
            for content_url in content_url_list[:-1]:
                result = fetch_completed_transcription(content_url)
                result_dict = {"transcriptions": result}
                output_list.append(result_dict)
            return output_list
        else:
            return {"transcriptions": "Transcription in progress"}
    except Exception as e:
        return {"error": str(e)}


@app.route('/transcription_fanolab', methods=['POST'])
def call_speech_to_text_api():
    data = request.get_json()
    url = data.get('url')

    audio_base64 = mp4_to_base64(mp4_url=url)

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
            "content": audio_base64
        }
    }
    response = requests.post("https://portal-demo.fano.ai/speech/long-running-recognize", json=payload, headers=headers)
    return response.json()


if __name__ == '__main__':
    app.run(debug=True)