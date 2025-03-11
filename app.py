from flask import Flask, request, jsonify
from pydantic import BaseModel
import requests
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()
app = Flask(__name__)

class TranscriptionRequest(BaseModel):
    url: str

headers = {
    "Ocp-Apim-Subscription-Key": os.getenv("AZURE_API_KEY"),  # Replace with your actual key
    "Content-Type": "application/json"
}

def check_status(url: str):
    response = requests.get(url, headers=headers)
    response.raise_for_status()  # Raises an error for bad responses
    json_data = response.json()

    transcribing_status = json_data.get("status", "")

    if transcribing_status == "Succeeded":
        file_url = json_data.get("links", {}).get("files")  # Avoids unnecessary empty string

        if file_url:
            content_response = requests.get(file_url, headers=headers)
            content_json = content_response.json()

            values = content_json.get("values", [])
            if values:
                content_url = values[0].get("links", {}).get("contentUrl")
                return content_url
    else:
        return "In Progress"

def fetch_completed_transcription(url: str):
    response = requests.get(url)
    response.raise_for_status()  # Raises an error for bad responses
    json_data = response.json()

    speaker_text_pairs = []
    for phrase in json_data.get("recognizedPhrases", []):
        speaker = phrase.get("speaker")
        display_text = phrase.get("nBest", [{}])[0].get("display", "")
        if speaker is not None and display_text:
            speaker_text_pairs.append(f"Speaker-{speaker}: {display_text}")
    return speaker_text_pairs


@app.route('/transcription', methods=['POST'])
def transcription():
    data = request.get_json()
    url = data.get('url')
    try:
        content_response = check_status(url)
        if content_response != "In Progress":
            result = fetch_completed_transcription(content_response)
            return {"transcriptions": result}
        else:
            return {"transcriptions": "Transcription in progress"}
    except Exception as e:
        return {"error": str(e)}


if __name__ == '__main__':
    app.run(debug=True)