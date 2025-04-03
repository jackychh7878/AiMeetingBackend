from dotenv import load_dotenv
import requests
import os
from collections import defaultdict
from src.utilities import format_time

# Load environment variables
load_dotenv()

headers = {
    "Ocp-Apim-Subscription-Key": os.getenv("AZURE_API_KEY"),
    "Content-Type": "application/json"
}


def azure_transcription(data):
    url = data.get('url')
    try:
        content_url_list = check_status(url)
        if content_url_list != "In Progress":
            output_list = []
            for content_url in content_url_list[:-1]:
                speaker_text_pairs, speaker_stats, total_duration = fetch_completed_transcription(content_url)
                result_dict = { "speaker_stats": speaker_stats,
                                "total_duration": total_duration,
                                "transcriptions": speaker_text_pairs}
                output_list.append(result_dict)
            return output_list
        else:
            return {"transcriptions": "Transcription in progress"}
    except Exception as e:
        return {"error": str(e)}



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
                response_url_list = []
                for item in values:
                    content_url = item.get("links", {}).get("contentUrl")
                    response_url_list.append(content_url)
                return response_url_list
    else:
        return "In Progress"


def fetch_completed_transcription(url: str):
    response = requests.get(url)
    response.raise_for_status()  # Raises an error for bad responses
    json_data = response.json()

    speaker_text_pairs = []
    speaker_stats = defaultdict(lambda: {"total_duration": 0, "total_words": 0})
    total_duration = 0

    for phrase in json_data.get("recognizedPhrases", []):
        speaker = phrase.get("speaker")
        display_text = phrase.get("nBest", [{}])[0].get("display", "")
        offset = phrase.get("offsetInTicks", 0) / 10000000  # Convert ticks to seconds
        duration = phrase.get("durationInTicks", 0) / 10000000  # Convert ticks to seconds

        start_time = format_time(offset)
        end_time = format_time(offset + duration)

        if speaker is not None and display_text:
            speaker_text_pairs.append(f"Speaker-{speaker} ({start_time} - {end_time}): {display_text}")

            # Update speaker statistics
            speaker_stats[speaker]["total_duration"] += duration
            speaker_stats[speaker]["total_words"] += len(display_text.split())
            total_duration += duration

    # Calculate percentages and words per minute
    for speaker, stats in speaker_stats.items():
        stats["percentage"] = (stats["total_duration"] / total_duration) * 100
        stats["words_per_minute"] = (stats["total_words"] / stats["total_duration"]) * 60

    return speaker_text_pairs, speaker_stats, total_duration

