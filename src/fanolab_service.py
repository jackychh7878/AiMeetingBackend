import os
from dotenv import load_dotenv
import requests
import time
from collections import defaultdict
from pydub import AudioSegment
from flask import Flask, request, jsonify, send_from_directory
from typing import Optional
from src.azure_service import azure_upload_file_and_get_sas_url, azure_delete_blob
from src.blob_storage_service import minio_upload_and_share, minio_delete_blob
from src.enums import OnPremiseMode
from src.utilities import format_time, mp4_to_wav_file, extract_audio_segment
from src.voiceprint_library_service import search_voiceprint
from src.app_owner_control_service import check_quota
import uuid
import zipfile
import shutil

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

FANOLAB_HOST = os.getenv("FANOLAB_HOST")
FANOLAB_API_KEY = os.getenv("FANOLAB_API_KEY")
headers = {"Authorization": f"Bearer {FANOLAB_API_KEY}", "Content-Type": "application/json"}

ON_PREMISES_MODE = os.getenv("ON_PREMISES_MODE")


def fanolab_submit_transcription(request):
    """
    Receives a JSON request with an MP4 URL, converts it to WAV, and sends the file URL to FanoLab API.
    """
    data = request.get_json()
    source_url = data.get('source_url')
    language_code = data.get('language_code', 'yue-x-auto')
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
        # Get duration and sample rate from WAV file
        audio = AudioSegment.from_wav(meeting_wav_path)
        duration_seconds = len(audio) / 1000  # Convert milliseconds to seconds
        duration_hours = duration_seconds / 3600  # Convert to hours
        sample_rate_hertz = audio.frame_rate

        # Validate sample rate
        if not (8000 <= sample_rate_hertz <= 48000):
            raise ValueError(f"Invalid sample rate: {sample_rate_hertz} Hz. Sample rate must be between 8000 and 48000 Hz.")

        # Check quota before proceeding
        is_allowed, message = check_quota(application_owner, duration_hours)

        if not is_allowed:
            return {"error": message}, 403

        wav_url: Optional[str] = None

        if ON_PREMISES_MODE == OnPremiseMode.ON_CLOUD.value:
            # Upload audio file to Azure Blob Storage
            wav_url = azure_upload_file_and_get_sas_url(file_path=meeting_wav_path, blob_name=AZURE_BLOB_NAME)
            if not wav_url:
                return {"error": "Failed to upload audio"}, 500

        elif ON_PREMISES_MODE == OnPremiseMode.ON_PREMISES.value:
            wav_url = minio_upload_and_share(
                    file_path=meeting_wav_path,
                    bucket="meeting-minutes-temp-audio",
                    blob_name=AZURE_BLOB_NAME)
            if not wav_url:
                return {"error": "Failed to upload audio"}, 500

        # Validate that wav_url was successfully set
        if not wav_url:
            return {"error": "Failed to upload audio file"}, 500

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
        response = requests.post(f"{FANOLAB_HOST}/speech/long-running-recognize", json=payload, headers=headers)

        if response:
            # Wait for 5 seconds before deleting the blob
            time.sleep(5)
            if ON_PREMISES_MODE == OnPremiseMode.ON_CLOUD.value:
                azure_delete_blob(blob_name=AZURE_BLOB_NAME)
            elif ON_PREMISES_MODE == OnPremiseMode.ON_PREMISES.value:
                minio_delete_blob(bucket="meeting-minutes-temp-audio", blob_name=AZURE_BLOB_NAME)
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
    confidence_threshold = float(data.get('confidence_threshold', 0.8))  # Convert to float with default value

    if not application_owner:
        return {"error": "application_owner is required"}, 400

    try:
        url = f"{FANOLAB_HOST}/speech/operations/{fanolab_id}"
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raises an error for bad responses
        json_data = response.json()

        current_status = json_data.get('done')

        if current_status is True:
            speaker_text_pairs, speaker_stats, total_duration, source_url = fanolab_fetch_completed_transcription(source_url=source_url, fanolab_id=fanolab_id, application_owner=application_owner, confidence_threshold=confidence_threshold)
                
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


def fanolab_fetch_completed_transcription(source_url: str, fanolab_id: str, match_voiceprint: bool = True, application_owner: str = None, confidence_threshold: float = 0.8):
    url = f"{FANOLAB_HOST}/speech/operations/{fanolab_id}"
    response = requests.get(url, headers=headers)
    response.raise_for_status()  # Raises an error for bad responses
    json_data = response.json()

    speaker_text_pairs = []

    speaker_stats = defaultdict(lambda: {"total_duration": 0, "total_words": 0, "segments": []})
    total_duration = 0

    # If a source URL exists, perform the audio conversion
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

    # Match voiceprint, Calculate percentages and words per minute
    if match_voiceprint and application_owner:
        for speaker, stats in speaker_stats.items():
            stats["percentage"] = (stats["total_duration"] / total_duration) * 100 if total_duration > 0 else 0
            stats["words_per_minute"] = (stats["total_words"] / stats["total_duration"]) * 60 if stats["total_duration"] > 0 else 0

            # Sort segments by duration (longest first) and get top 3 segments
            stats["segments"].sort(key=lambda x: x["duration"], reverse=True)
            top_segments = stats["segments"][:3]

            if top_segments:
                for i, segment in enumerate(top_segments):
                    output_name = f"speaker_{speaker}_segment_{i}"
                    extract_audio_segment(output_name=output_name, start_time=segment["start"], end_time=segment["end"], input_file=meeting_wav_path, clean_up_after=False)
                    wav_path = os.path.join(UPLOAD_FOLDER, f"{output_name}.wav")
                    matches = search_voiceprint(wav_path, application_owner)

                    if matches:
                        matches_data = matches.get_json()
                        if matches_data and len(matches_data) > 0:
                            best_match = matches_data[0]
                            if best_match.get("similarity", 0) >= confidence_threshold:  # Confidence threshold
                                stats["identified_name"] = best_match.get("name", "unknown")
                                stats["confidence"] = best_match.get("similarity")
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


def fanolab_extract_speaker_clip(request):
    """
    Extracts audio segments for each speaker from a meeting recording using Fanolab transcription.
    
    Args:
        request: Flask request object containing:
            - source_url: URL of the meeting recording MP4 file
            - fanolab_id: ID of the Fanolab transcription operation
            
    Returns:
        A zip file containing audio segments for each speaker
    """
    data = request.get_json()
    mp4_url = data.get('source_url')
    fanolab_id = data.get('fanolab_id')

    if not mp4_url or not fanolab_id:
        return {"error": "Both source_url and fanolab_id are required"}, 400
        
    try:
        # Generate unique identifier for this request
        unique_id = str(uuid.uuid4())
        
        # Create unique directory for this request's files
        request_dir = os.path.join(UPLOAD_FOLDER, f"request_{unique_id}")
        os.makedirs(request_dir, exist_ok=True)
        
        try:
            # Get the transcription results
            speaker_text_pairs, speaker_stats, total_duration, source_url = fanolab_fetch_completed_transcription(
                source_url=mp4_url,
                fanolab_id=fanolab_id,
                match_voiceprint = False,
                application_owner=None  # We don't need voiceprint matching for this operation
            )
            
            # Download and convert the MP4 to WAV
            meeting_wav_path = mp4_to_wav_file(mp4_url=mp4_url)
            
            # Create a directory to store the speaker clips
            clips_dir = os.path.join(request_dir, "speaker_clips")
            os.makedirs(clips_dir, exist_ok=True)
            
            # Extract segments for each speaker
            for speaker, stats in speaker_stats.items():
                # Sort segments by duration and get top 3
                stats["segments"].sort(key=lambda x: x["duration"], reverse=True)
                top_segments = stats["segments"][:3]  # Get up to 3 longest segments
                
                # Extract each segment
                for i, segment in enumerate(top_segments):
                    output_name = f"speaker_{speaker}_segment_{i}"
                    extract_audio_segment(output_name=output_name, start_time=segment["start"], end_time=segment["end"], input_file=meeting_wav_path, clean_up_after=False)
                    
                    # Move the file to the clips directory
                    src_path = os.path.join(UPLOAD_FOLDER, f"{output_name}.wav")
                    dst_path = os.path.join(clips_dir, f"{output_name}.wav")
                    os.rename(src_path, dst_path)
            
            # Create a zip file of all clips with unique name
            zip_filename = f"speaker_clips_{unique_id}.zip"
            zip_path = os.path.join(request_dir, zip_filename)
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                for root, dirs, files in os.walk(clips_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, clips_dir)
                        zipf.write(file_path, arcname)

            # Clean up the clips directory
            shutil.rmtree(clips_dir)

            # Upload the zip file to Azure Blob Storage and get a SAS URL
            blob_name = f"speaker_clips_{unique_id}.zip"  # Use unique name for blob

            download_url: Optional[str] = None

            if ON_PREMISES_MODE == OnPremiseMode.ON_CLOUD.value:
                download_url = azure_upload_file_and_get_sas_url(file_path=zip_path, blob_name=blob_name)

            elif ON_PREMISES_MODE == OnPremiseMode.ON_PREMISES.value:
                download_url = minio_upload_and_share(file_path=zip_path, bucket="meeting-minutes-speaker-clip", blob_name=blob_name)

            # Clean up all temporary files and directories
            if os.path.exists(meeting_wav_path):
                os.remove(meeting_wav_path)
            if os.path.exists(request_dir):
                shutil.rmtree(request_dir)

            if not download_url:
                return {"error": "Failed to export speaker clip"}, 500

            return {"download_url": download_url}

        except Exception as e:
            return {"error": str(e)}, 500

    except Exception as e:
        return {"error": str(e)}, 500


def fanolab_match_speaker_voiceprint(request):
    """
    Match each speaker from existing voiceprint library using Fanolab transcription.

    Args:
        request: Flask request object containing:
            - source_url: URL of the meeting recording MP4 file
            - fanolab_id: ID of the Fanolab transcription operation
            - application_owner: Owner of the application for voiceprint matching

    Returns:
        JSON of each speaker's name
    """
    data = request.get_json()
    mp4_url = data.get('source_url')
    fanolab_id = data.get('fanolab_id')
    application_owner = data.get('application_owner')
    confidence_threshold = data.get('confidence_threshold')

    if not mp4_url or not fanolab_id or not application_owner:
        return {"error": "source_url, fanolab_id, and application_owner are required"}, 400

    try:
        # Clean up upload folder first
        for filename in os.listdir(UPLOAD_FOLDER):
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print(f'Failed to delete {file_path}. Reason: {e}')

        # Get the transcription results with voiceprint matching enabled
        speaker_text_pairs, speaker_stats, total_duration, source_url = fanolab_fetch_completed_transcription(
            source_url=mp4_url,
            fanolab_id=fanolab_id,
            match_voiceprint=True,
            application_owner=application_owner,
            confidence_threshold=confidence_threshold
        )

        # Create output list of speaker matches
        output_list = []
        for speaker, stats in speaker_stats.items():
            confidence_pct = f"{stats.get('confidence', 0) * 100:.2f}%"
            output_list.append(f'Speaker-{speaker}: {stats["identified_name"]} ({confidence_pct})')

        # Return the speaker voiceprint match
        return {"speaker": '\n'.join(output_list)}

    except Exception as e:
        return {"error": str(e)}, 500

