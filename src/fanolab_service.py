import os
from dotenv import load_dotenv
import requests
import time
from collections import defaultdict
from pydub import AudioSegment
from flask import Flask, request, jsonify, send_from_directory
from src.azure_service import azure_upload_file_and_get_sas_url, azure_delete_blob
from src.utilities import format_time, mp4_to_wav_file, extract_audio_segment
from src.voiceprint_library_service import search_voiceprint
from src.app_owner_control_service import check_quota

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
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

FANOLAB_API_KEY = os.getenv("FANOLAB_API_KEY")
headers = {"Authorization": f"Bearer {FANOLAB_API_KEY}", "Content-Type": "application/json"}


def fanolab_submit_transcription(request):
    """
    Receives a JSON request with an MP4 URL, converts it to WAV, and sends the file URL to FanoLab API.
    """
    data = request.get_json()
    source_url = data.get('source_url')
    language_code = data.get('language_code', 'yue-x-auto')
    sample_rate_hertz = data.get('sample_rate_hertz', 16000)
    enable_automatic_punctuation = data.get('enable_auto_punctuation', False)
    application_owner = data.get('application_owner')

    if not source_url:
        return {"error": "URL is required"}

    if not application_owner:
        return {"error": "application_owner is required"}

    # Convert MP4 to WAV
    meeting_wav_path = mp4_to_wav_file(source_url)
    if not meeting_wav_path:
        return {"error": "Failed to process audio"}

    try:
        # Get duration from WAV file
        audio = AudioSegment.from_wav(meeting_wav_path)
        duration_seconds = len(audio) / 1000  # Convert milliseconds to seconds
        duration_hours = duration_seconds / 3600  # Convert to hours

        # # Check quota before proceeding
        is_allowed, message = check_quota(application_owner, duration_hours)

        if not is_allowed:
            return {"error": message}, 403

        # Upload audio file to Azure Blob Storage
        wav_url = azure_upload_file_and_get_sas_url(file_path=meeting_wav_path, blob_name=AZURE_BLOB_NAME)
        if not wav_url:
            return {"error": "Failed to upload audio"}, 500

        # Prepare API request
        payload = {
            "config": {
                "languageCode": language_code,
                "sampleRateHertz": sample_rate_hertz,
                "maxAlternatives": 1,
                "enableSeparateRecognitionPerChannel": False,
                "enableAutomaticPunctuation": enable_automatic_punctuation
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
            azure_delete_blob(blob_name=AZURE_BLOB_NAME)
            # Clean up the temporary WAV file
            if os.path.exists(meeting_wav_path):
                os.remove(meeting_wav_path)

        return response.json()
    except Exception as e:
        return {"error": str(e)}, 500
    finally:
        # Clean up the WAV file
        if os.path.exists(meeting_wav_path):
            os.remove(meeting_wav_path)


def fanolab_transcription(request):
    data = request.get_json()
    sys_id = data.get('sys_id')
    source_url = data.get('source_url')
    fanolab_id = data.get('fanolab_id')
    application_owner = data.get('application_owner')

    if not application_owner:
        return {"error": "application_owner is required"}, 400

    try:
        url = f"https://portal-demo.fano.ai/speech/operations/{fanolab_id}"
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raises an error for bad responses
        json_data = response.json()

        current_status = json_data.get('done')

        if current_status is True:
            speaker_text_pairs, speaker_stats, total_duration, source_url = fanolab_fetch_completed_transcription(source_url=source_url, fanolab_id=fanolab_id, application_owner=application_owner)
                
            result_dict = {
                "status": "success",
                "message": "Transcription completed successfully",
                "sys_id": sys_id,
                "source_url": source_url,
                "speaker_stats": speaker_stats,
                "total_duration": total_duration,
                "transcriptions": speaker_text_pairs
            }
            return result_dict
        else:
            # Check if there's an error in the response
            if "error" in json_data:
                return {
                    "status": "failed",
                    "message": json_data["error"].get("message", "Unknown error occurred"),
                }, 400
            else:
                return {
                    "status": "in_progress",
                    "message": "Transcription is still in progress"
                }, 200
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
        }, 500


def fanolab_fetch_completed_transcription(source_url: str, fanolab_id: str, application_owner: str = None):
    url = f"https://portal-demo.fano.ai/speech/operations/{fanolab_id}"
    response = requests.get(url, headers=headers)
    response.raise_for_status()  # Raises an error for bad responses
    json_data = response.json()

    speaker_text_pairs = []

    speaker_stats = defaultdict(lambda: {"total_duration": 0, "total_words": 0, "segments": []})
    total_duration = 0

    # If a source URL exists, perform the audio conversion as in the Azure version
    meeting_wav_path = mp4_to_wav_file(mp4_url=source_url)

    # Process each result from Fanolab's response
    results = json_data.get("response", {}).get("results", [])
    
    # Sort results by startTime
    def get_start_time(result):
        alternatives = result.get("alternatives", [])
        if alternatives:
            start_time_str = alternatives[0].get("startTime", "0s")
            try:
                return float(start_time_str.rstrip("s"))
            except ValueError:
                return 0
        return 0
    
    sorted_results = sorted(results, key=get_start_time)
    
    for result in sorted_results:
        alternatives = result.get("alternatives", [])
        if not alternatives:
            continue

        # Always take the first alternative
        alternative = alternatives[0]
        transcript = alternative.get("transcript", "")
        # Fanolab returns times as strings with a trailing "s" (e.g., "10.420s")
        start_time_str = alternative.get("startTime", "0s")
        end_time_str = alternative.get("endTime", "0s")

        try:
            start_time_sec = float(start_time_str.rstrip("s"))
        except ValueError:
            start_time_sec = 0
        try:
            end_time_sec = float(end_time_str.rstrip("s"))
        except ValueError:
            end_time_sec = 0

        duration = end_time_sec - start_time_sec
        formatted_start_time = format_time(start_time_sec)
        formatted_end_time = format_time(end_time_sec)
        speaker = alternative.get("speakerTag")

        if speaker is not None and transcript:
            try:
                speaker_int = int(speaker)
            except ValueError:
                continue  # Skip if speakerTag is not a valid integer string
            speaker_text_pairs.append(
                f"Speaker-{speaker_int} ({formatted_start_time} - {formatted_end_time}): {transcript}"
            )

            # Update speaker statistics
            speaker_stats[speaker_int]["total_duration"] += duration
            speaker_stats[speaker_int]["total_words"] += len(transcript.split())
            speaker_stats[speaker_int]["segments"].append({
                "start": start_time_sec,
                "end": end_time_sec,
                "duration": duration
            })
            total_duration += duration

    # Calculate percentages and words per minute; also perform voiceprint matching
    for speaker, stats in speaker_stats.items():
        stats["percentage"] = (stats["total_duration"] / total_duration) * 100 if total_duration > 0 else 0
        stats["words_per_minute"] = (stats["total_words"] / stats["total_duration"]) * 60 if stats["total_duration"] > 0 else 0

        # Sort segments by duration (longest first) and get top 3 segments
        stats["segments"].sort(key=lambda x: x["duration"], reverse=True)
        top_segments = stats["segments"][:3]

        if top_segments and application_owner:
            for i, segment in enumerate(top_segments):
                output_name = f"speaker_{speaker}_segment_{i}"
                extract_audio_segment(output_name=output_name, start_time=segment["start"], end_time=segment["end"], input_file=meeting_wav_path, clean_up_after=False)
                wav_path = os.path.join(UPLOAD_FOLDER, f"{output_name}.wav")
                matches = search_voiceprint(wav_path, application_owner)

                if matches:
                    matches_data = matches.get_json()
                    if matches_data and len(matches_data) > 0:
                        best_match = matches_data[0]
                        if best_match.get("similarity", 0) >= 0.8:  # Confidence threshold
                            stats["identified_name"] = best_match.get("name", "unknown")
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

    # Clean up the temporary WAV file
    if os.path.exists(meeting_wav_path):
        os.remove(meeting_wav_path)

    return speaker_text_pairs, speaker_stats, total_duration, source_url

