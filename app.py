from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

def fetch_completed_transcription(url: str):
    response = requests.get(url)
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
    if not url:
        return jsonify({"error": "URL is required"}), 400
    try:
        result = fetch_completed_transcription(url)
        return jsonify({"transcriptions": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
