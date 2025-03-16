import os
from dotenv import load_dotenv
from flask import Flask, request, jsonify, send_from_directory
import requests
from utilities import check_status, fetch_completed_transcription, mp4_to_base64
from pydub import AudioSegment

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
#     return response.json()


UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/uploads/<filename>')
def serve_audio(filename):
    """ Serves the audio file over HTTP. """
    return send_from_directory(UPLOAD_FOLDER, filename)

def mp4_to_wav_file(mp4_url, save_dir=UPLOAD_FOLDER):
    """
    Downloads an MP4 file, extracts audio as WAV, and saves it.
    Returns the local file path.
    """
    try:
        mp4_path = os.path.join(save_dir, "audio.mp4")
        wav_path = os.path.join(save_dir, "audio.wav")

        # Step 1: Download MP4
        response = requests.get(mp4_url, stream=True)
        if response.status_code == 200:
            with open(mp4_path, "wb") as file:
                for chunk in response.iter_content(chunk_size=1024):
                    file.write(chunk)
            print("Downloaded MP4")
        else:
            raise Exception(f"Failed to download MP4. Status code: {response.status_code}")

        # Step 2: Convert MP4 to WAV
        audio = AudioSegment.from_file(mp4_path, format="mp4")
        audio.export(wav_path, format="wav")
        print("Converted to WAV")

        # Cleanup MP4 to save space
        os.remove(mp4_path)

        return wav_path  # Return local WAV file path

    except Exception as e:
        print(f"Error: {e}")
        return None

@app.route('/transcription_fanolab', methods=['POST'])
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
    file_url = f"http://localhost:5000/uploads/audio.wav"  # Replace with actual domain if hosted

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

if __name__ == '__main__':
    app.run(debug=True)