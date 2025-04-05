from dotenv import load_dotenv
import requests
import os
from collections import defaultdict
from src.utilities import format_time, mp4_to_wav_file, extract_audio_segment
from src.voiceprint_library_service import search_voiceprint

# Load environment variables
load_dotenv()

headers = {
    "Ocp-Apim-Subscription-Key": os.getenv("AZURE_API_KEY"),
    "Content-Type": "application/json"
}


def azure_transcription(request):
    data = request.get_json()
    url = data.get('url')
    try:
        content_url_list, sys_ids = check_status(url)
        if content_url_list != "In Progress":
            output_list = []
            for i, content_url in enumerate(content_url_list[:-1]):
                speaker_text_pairs, speaker_stats, total_duration, source_url = fetch_completed_transcription(content_url)
                result_dict = {
                    "sys_id": sys_ids[i] if i < len(sys_ids) else None,
                    "source_url": source_url,
                    "speaker_stats": speaker_stats,
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
    display_name = json_data.get("displayName")

    # Extract sys_id values
    sys_ids = []
    if "sys_id:" in display_name:
        sys_id_part = display_name.split("sys_id:")[-1].strip()
        sys_ids = []
        for id in sys_id_part.split(','):
            id = id.strip()
            if id.isdigit():
                sys_ids.append(int(id))
            elif id:  # Check if the id is not empty
                sys_ids.append(id)

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
                return response_url_list, sys_ids
    else:
        return "In Progress"


UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def fetch_completed_transcription(url: str):
    response = requests.get(url)
    response.raise_for_status()  # Raises an error for bad responses
    json_data = response.json()

    speaker_text_pairs = []
    source_url = json_data.get("source")
    speaker_stats = defaultdict(lambda: {"total_duration": 0, "total_words": 0, "segments": []})
    total_duration = 0

    # Get the mp4 source and save the wav as src/uploads/temp_audio.wav
    mp4_to_wav_file(mp4_url=json_data.get("source"))

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
            speaker_stats[speaker]["segments"].append({
                "start": offset,
                "end": offset + duration,
                "duration": duration
            })
            total_duration += duration

    # Calculate percentages and words per minute
    for speaker, stats in speaker_stats.items():
        stats["percentage"] = (stats["total_duration"] / total_duration) * 100
        stats["words_per_minute"] = (stats["total_words"] / stats["total_duration"]) * 60

        # Sort segments by duration and get top 3
        stats["segments"].sort(key=lambda x: x["duration"], reverse=True)
        top_segments = stats["segments"][:3]

        # Extract audio segments and perform voiceprint matching
        if len(top_segments) >= 1:
            # Extract audio segments
            for i, segment in enumerate(top_segments):
                output_name = f"speaker_{speaker}_segment_{i}"
                extract_audio_segment(output_name, segment["start"], segment["end"])
                
                # Perform voiceprint matching
                wav_path = os.path.join(UPLOAD_FOLDER, f"{output_name}.wav")
                matches = search_voiceprint(wav_path)
                
                # Get the best match
                if matches:
                    # Convert response to JSON data
                    matches_data = matches.get_json()
                    if matches_data and len(matches_data) > 0:
                        best_match = matches_data[0]
                        if best_match["similarity"] >= 0.8:  # Confidence threshold
                            stats["identified_name"] = best_match["name"]
                        else:
                            stats["identified_name"] = "unknown"
                    else:
                        stats["identified_name"] = "unknown"
                else:
                    stats["identified_name"] = "unknown"
                
                # Clean up the temporary WAV file
                os.remove(wav_path)
        else:
            stats["identified_name"] = "unknown"

    return speaker_text_pairs, speaker_stats, total_duration, source_url
