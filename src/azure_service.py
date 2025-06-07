from dotenv import load_dotenv
import requests
import os
import shutil
import zipfile
from collections import defaultdict
from src.utilities import format_time, mp4_to_wav_file, extract_audio_segment
from src.voiceprint_library_service import search_voiceprint
from datetime import datetime, timedelta
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
from src.app_owner_control_service import check_quota
import uuid

# Load environment variables
load_dotenv()

headers = {
    "Ocp-Apim-Subscription-Key": os.getenv("AZURE_STT_API_KEY"),
    "Content-Type": "application/json"
}

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def azure_transcription(request):
    data = request.get_json()
    url = data.get('url')
    application_owner = data.get('application_owner')
    confidence_threshold = data.get('confidence_threshold')

    try:
        content_url_list, sys_ids = azure_check_status(url)
        if content_url_list == "In Progress":
            return {"transcriptions": "Transcription in progress"}, 200
            
        output_list = []
        total_duration_hours = 0
        for i, content_url in enumerate(content_url_list[:-1]):
            speaker_text_pairs, speaker_stats, total_duration, source_url = azure_fetch_completed_transcription(url=content_url, match_voiceprint=True, application_owner=application_owner, confidence_threshold=confidence_threshold)
            result_dict = {
                "sys_id": sys_ids[i] if i < len(sys_ids) else None,
                "source_url": source_url,
                "speaker_stats": speaker_stats,
                "total_duration": total_duration,
                "transcriptions": speaker_text_pairs}
            output_list.append(result_dict)
            total_duration_hours += total_duration / 3600  # Convert seconds to hours

        # Check quota after getting total duration
        is_allowed, message = check_quota(application_owner, total_duration_hours)
        if not is_allowed:
            return {"error": message}, 403
            
        return output_list
    except Exception as e:
        return {"error": str(e)}



def azure_check_status(url: str):
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



def azure_fetch_completed_transcription(url: str, match_voiceprint: bool = True, application_owner: str = None, confidence_threshold: float = 0.8):
    response = requests.get(url)
    response.raise_for_status()  # Raises an error for bad responses
    json_data = response.json()

    speaker_text_pairs = []
    source_url = json_data.get("source")
    speaker_stats = defaultdict(lambda: {"total_duration": 0, "total_words": 0, "segments": []})
    
    # Get total duration from JSON data (convert milliseconds to seconds)
    total_duration = json_data.get("durationMilliseconds", 0) / 1000

    # Get the mp4 source and save the wav as src/uploads/temp_audio.wav
    meeting_wav_path = mp4_to_wav_file(mp4_url=json_data.get("source"))

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

    # Match voiceprint, Calculate percentages and words per minute
    if match_voiceprint and application_owner:
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
                    extract_audio_segment(output_name=output_name, start_time=segment["start"], end_time=segment["end"], input_file=meeting_wav_path, clean_up_after=False)

                    # Perform voiceprint matching
                    wav_path = os.path.join(UPLOAD_FOLDER, f"{output_name}.wav")
                    matches = search_voiceprint(wav_path, application_owner)

                    # Get the best match
                    if matches:
                        # Convert response to JSON data
                        matches_data = matches.get_json()
                        if matches_data and len(matches_data) > 0:
                            best_match = matches_data[0]
                            if best_match["similarity"] >= confidence_threshold:  # Confidence threshold
                                stats["identified_name"] = best_match["name"]
                                stats["confidence"] = best_match["similarity"]
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



def azure_upload_file_and_get_sas_url(file_path, blob_name, expiry_date: timedelta = timedelta(hours=1)):
    """
    Uploads a file to Azure Blob Storage and generates a temporary SAS URL.

    :param expiry_date: Expiry date for the SAS url
    :param file_path: Path to the local file to be uploaded.
    :param blob_name: Name for the blob in Azure Storage.

    :return: SAS URL string for the uploaded blob.
    """
    try:
        container_name = os.getenv('AZURE_CONTAINER_NAME')
        account_name = os.getenv('AZURE_ACCOUNT_NAME')
        account_key = os.getenv('AZURE_ACCOUNT_KEY')

        # Construct the BlobServiceClient using the account URL and account key
        account_url = f"https://{account_name}.blob.core.windows.net"
        blob_service_client = BlobServiceClient(account_url=account_url, credential=account_key)

        # Get the container client
        container_client = blob_service_client.get_container_client(container_name)

        # Upload the file
        with open(file_path, "rb") as data:
            blob_client = container_client.upload_blob(name=blob_name, data=data, overwrite=True)

        # Set the SAS token expiration time (e.g., 1 hour from now)
        sas_expiry = datetime.now() + expiry_date

        # Generate the SAS token with read permissions
        sas_token = generate_blob_sas(
            account_name=account_name,
            container_name=container_name,
            blob_name=blob_name,
            account_key=account_key,
            permission=BlobSasPermissions(read=True),
            expiry=sas_expiry
        )

        # Construct the full URL with the SAS token
        sas_url = f"{account_url}/{container_name}/{blob_name}?{sas_token}"
        return sas_url

    except Exception as e:
        print(f"An error occurred: {e}")
        return None


def azure_delete_blob(blob_name):
    """
    Deletes a blob from Azure Blob Storage.

    :param blob_name: Name of the blob to be deleted.
    :return: Boolean indicating whether the deletion was successful.
    """
    try:
        # Retrieve Azure Storage account details from environment variables
        container_name = os.getenv('AZURE_CONTAINER_NAME')
        account_name = os.getenv('AZURE_ACCOUNT_NAME')
        account_key = os.getenv('AZURE_ACCOUNT_KEY')

        # Construct the BlobServiceClient using the account URL and account key
        account_url = f"https://{account_name}.blob.core.windows.net"
        blob_service_client = BlobServiceClient(account_url=account_url, credential=account_key)

        # Get the container client
        container_client = blob_service_client.get_container_client(container_name)

        # Delete the blob
        container_client.delete_blob(blob_name, delete_snapshots='include')
        print(f"Blob '{blob_name}' deleted successfully.")
        return True

    except Exception as e:
        print(f"An error occurred while deleting the blob: {e}")
        return False


def azure_extract_speaker_clip(request):
    """
    Extracts audio segments for each speaker from a meeting recording.
    
    Args:
        request: Flask request object containing:
            - source_url: URL of the meeting recording MP4 file
            - azure_url: URL of the Azure transcription results
            
    Returns:
        A zip file containing audio segments for each speaker
    """
    data = request.get_json()
    mp4_url = data.get('source_url')
    transcription_url = data.get('azure_url')

    if not mp4_url or not transcription_url:
        return {"error": "Both source_url and azure_url are required"}, 400
        
    try:
        # Generate unique identifier for this request
        unique_id = str(uuid.uuid4())
        
        # Create unique directory for this request's files
        request_dir = os.path.join(UPLOAD_FOLDER, f"request_{unique_id}")
        os.makedirs(request_dir, exist_ok=True)
        
        try:
            # First get the transcription results
            content_url_list, sys_ids = azure_check_status(transcription_url)
            if content_url_list == "In Progress":
                return {"error": "Transcription is still in progress"}, 400
                
            # Find the index of the matching sys_id
            try:
                target_content_url = ''
                mp4_sig = mp4_url.split("sig=")[1]
                for content_url in content_url_list:
                    response = requests.get(content_url)
                    response.raise_for_status()  # Raises an error for bad responses
                    json_data = response.json()
                    url = json_data.get('source')
                    content_url_sig = url.split("sig=")[1]
                    if mp4_sig == content_url_sig:
                        target_content_url = content_url
                        break

                if target_content_url == '':
                    return {"error": "target content url not found"}, 400

                content_url_index = content_url_list.index(target_content_url)
            except ValueError:
                return {"error": "target content url not found"}, 400
                
            # Get the content URL for the matching sys_id
            content_url = content_url_list[content_url_index]
            speaker_text_pairs, speaker_stats, total_duration, source_url = azure_fetch_completed_transcription(url=content_url, match_voiceprint=False)
            
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
            download_url = azure_upload_file_and_get_sas_url(zip_path, blob_name)

            # Clean up all temporary files and directories
            if os.path.exists(meeting_wav_path):
                os.remove(meeting_wav_path)
            if os.path.exists(request_dir):
                shutil.rmtree(request_dir)

            return {"download_url": download_url}

        except Exception as e:
            return {"error": str(e)}, 500

    except Exception as e:
        return {"error": str(e)}, 500


def azure_match_speaker_voiceprint(request):
    """
    Match each speaker from existing voiceprint library

    Args:
        request: Flask request object containing:
            - source_url: URL of the meeting recording MP4 file
            - azure_url: URL of the Azure transcription results
            - application_owner: Owner of the application for voiceprint matching

    Returns:
        JSON of each speaker's name
    """
    data = request.get_json()
    mp4_url = data.get('source_url')
    transcription_url = data.get('azure_url')
    application_owner = data.get('application_owner')
    confidence_threshold = data.get('confidence_threshold')

    if not mp4_url or not transcription_url or not application_owner:
        return {"error": "source_url, azure_url, and application_owner are required"}, 400

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

        # First get the transcription results
        content_url_list, sys_ids = azure_check_status(transcription_url)
        if content_url_list == "In Progress":
            return {"error": "Transcription is still in progress"}, 400

        # Find the index of the matching sys_id
        try:
            target_content_url = ''
            mp4_sig = mp4_url.split("sig=")[1]
            for content_url in content_url_list:
                response = requests.get(content_url)
                response.raise_for_status()  # Raises an error for bad responses
                json_data = response.json()
                url = json_data.get('source')
                content_url_sig = url.split("sig=")[1]
                if mp4_sig == content_url_sig:
                    target_content_url = content_url
                    break

            if target_content_url == '':
                return {"error": "target content url not found"}, 400

            content_url_index = content_url_list.index(target_content_url)
        except ValueError:
            return {"error": "target content url not found"}, 400

        # Get the content URL for the matching sys_id
        content_url = content_url_list[content_url_index]
        speaker_text_pairs, speaker_stats, total_duration, source_url = azure_fetch_completed_transcription(
            url=content_url, match_voiceprint=True, application_owner=application_owner, confidence_threshold=confidence_threshold)

        # Download and convert the MP4 to WAV
        meeting_wav_path = mp4_to_wav_file(mp4_url=mp4_url)

        # Create a directory to store the speaker clips
        clips_dir = os.path.join(UPLOAD_FOLDER, "speaker_clips")
        os.makedirs(clips_dir, exist_ok=True)

        # Extract segments for each speaker
        for speaker, stats in speaker_stats.items():
            # Sort segments by duration and get top 3
            stats["segments"].sort(key=lambda x: x["duration"], reverse=True)
            top_segments = stats["segments"][:3]  # Get up to 3 longest segments

            # Extract audio segments and perform voiceprint matching
            if len(top_segments) >= 1:
                # Extract audio segments
                for i, segment in enumerate(top_segments):
                    output_name = f"speaker_{speaker}_segment_{i}"
                    extract_audio_segment(output_name=output_name, start_time=segment["start"], end_time=segment["end"], input_file=meeting_wav_path, clean_up_after=False)

                    # Perform voiceprint matching
                    wav_path = os.path.join(UPLOAD_FOLDER, f"{output_name}.wav")
                    matches = search_voiceprint(wav_path, application_owner)

                    # Get the best match
                    if matches:
                        # Convert response to JSON data
                        matches_data = matches.get_json()
                        if matches_data and len(matches_data) > 0:
                            best_match = matches_data[0]
                            if best_match["similarity"] >= confidence_threshold:  # Confidence threshold
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

        output_list = []
        for speaker, stats in speaker_stats.items():
            confidence_pct = f"{stats.get('confidence', 0) * 100:.2f}%"
            output_list.append(f'Speaker-{speaker}: {stats["identified_name"]} ({confidence_pct})')

        # Clean up the temporary WAV file
        if os.path.exists(meeting_wav_path):
            os.remove(meeting_wav_path)

        # Return the speaker voiceprint match
        return {"speaker": '\n'.join(output_list)}

    except Exception as e:
        return {"error": str(e)}, 500


def azure_upload_media_and_get_sas_url(request):
    """
    Uploads a media file (MP4 or WAV) to Azure Blob Storage and generates a SAS URL with 1-year expiry.
    Automatically detects file type from URL and content.
    
    Args:
        request: Flask request object containing:
            - data: List containing a single URL of the media file to be downloaded and uploaded
            
    Returns:
        Dictionary containing the SAS URL for the uploaded blob
    """
    try:
        data = request.get_json()
        url_list = data.get('data')
        
        if not url_list or not isinstance(url_list, list):
            return {"error": "data must be a list containing a single URL"}, 400
            
        if len(url_list) != 1:
            return {"error": "data must contain exactly one URL"}, 400
            
        file_url = url_list[0]
        if not file_url or not isinstance(file_url, str):
            return {"error": "URL must be a valid string"}, 400
            
        # Generate unique filename
        unique_id = str(uuid.uuid4())
        temp_filepath = os.path.join(UPLOAD_FOLDER, f"temp_{unique_id}")
        
        try:
            # Download the file
            response = requests.get(file_url, stream=True)
            response.raise_for_status()
            
            # Get content type from response headers
            content_type = response.headers.get('content-type', '').lower()
            
            # Determine file type from content type or URL
            file_type = None
            if 'video/mp4' in content_type or file_url.lower().endswith('.mp4'):
                file_type = 'mp4'
            elif 'audio/wav' in content_type or file_url.lower().endswith('.wav'):
                file_type = 'wav'
            
            if not file_type:
                return {"error": "Unsupported file type. Only MP4 and WAV files are supported."}, 400
            
            # Save the file temporarily with detected extension
            temp_filepath = f"{temp_filepath}.{file_type}"
            with open(temp_filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            # Generate blob name
            blob_name = f"media/{unique_id}.{file_type}"
            
            # Upload to Azure with 1-year expiry
            sas_url = azure_upload_file_and_get_sas_url(
                file_path=temp_filepath,
                blob_name=blob_name,
                expiry_date=timedelta(days=365)
            )
            
            if not sas_url:
                return {"error": "Failed to upload file to Azure"}, 500
                
            return {"sas_url": sas_url}
            
        finally:
            # Clean up temporary file
            if os.path.exists(temp_filepath):
                os.remove(temp_filepath)
                
    except Exception as e:
        return {"error": str(e)}, 500
