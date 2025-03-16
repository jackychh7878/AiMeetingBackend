import os
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from pydantic import BaseModel
import requests
from utilities import check_status, fetch_completed_transcription

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


if __name__ == '__main__':
    app.run(debug=True)