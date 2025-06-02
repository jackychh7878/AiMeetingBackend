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

# Load environment variables
load_dotenv()

headers = {
    "Ocp-Apim-Subscription-Key": os.getenv("AZURE_API_KEY"),
    "Content-Type": "application/json"
}

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def azure_transcription(request):
    data = request.get_json()
    url = data.get('url')
    application_owner = data.get('application_owner')
    try:
        content_url_list, sys_ids = azure_check_status(url)
        if content_url_list != "In Progress":
            output_list = []
            for i, content_url in enumerate(content_url_list[:-1]):
                speaker_text_pairs, speaker_stats, total_duration, source_url = azure_fetch_completed_transcription(url=content_url, application_owner=application_owner)
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



def azure_fetch_completed_transcription(url: str, match_voiceprint: bool = True, application_owner: str = None):
    response = requests.get(url)
    response.raise_for_status()  # Raises an error for bad responses
    json_data = response.json()

    speaker_text_pairs = []
    source_url = json_data.get("source")
    speaker_stats = defaultdict(lambda: {"total_duration": 0, "total_words": 0, "segments": []})
    
    # Get total duration from JSON data (convert milliseconds to seconds)
    total_duration = json_data.get("durationMilliseconds", 0) / 1000

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
                    extract_audio_segment(output_name, segment["start"], segment["end"])

                    # Perform voiceprint matching
                    wav_path = os.path.join(UPLOAD_FOLDER, f"{output_name}.wav")
                    matches = search_voiceprint(wav_path, application_owner)

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



def azure_upload_file_and_get_sas_url(file_path, blob_name):
    """
    Uploads a file to Azure Blob Storage and generates a temporary SAS URL.

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
        sas_expiry = datetime.now() + timedelta(hours=1)

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
    application_owner = data.get('application_owner')

    if not mp4_url or not transcription_url:
        return {"error": "Both source_url and azure_url are required"}, 400
        
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
        speaker_text_pairs, speaker_stats, total_duration, source_url = azure_fetch_completed_transcription(url=content_url, match_voiceprint=False, application_owner=application_owner)
        
        # Download and convert the MP4 to WAV
        mp4_to_wav_file(mp4_url=mp4_url)
        
        # Create a directory to store the speaker clips
        clips_dir = os.path.join(UPLOAD_FOLDER, "speaker_clips")
        os.makedirs(clips_dir, exist_ok=True)
        
        # Extract segments for each speaker
        for speaker, stats in speaker_stats.items():
            # Sort segments by duration and get top 3
            stats["segments"].sort(key=lambda x: x["duration"], reverse=True)
            top_segments = stats["segments"][:3]  # Get up to 3 longest segments
            
            # Extract each segment
            for i, segment in enumerate(top_segments):
                output_name = f"speaker_{speaker}_segment_{i}"
                extract_audio_segment(output_name, segment["start"], segment["end"])
                
                # Move the file to the clips directory
                src_path = os.path.join(UPLOAD_FOLDER, f"{output_name}.wav")
                dst_path = os.path.join(clips_dir, f"{output_name}.wav")
                os.rename(src_path, dst_path)
        
        # Create a zip file of all clips
        zip_path = os.path.join(UPLOAD_FOLDER, "speaker_clips.zip")
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for root, dirs, files in os.walk(clips_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, clips_dir)
                    zipf.write(file_path, arcname)
        
        # Clean up the clips directory
        shutil.rmtree(clips_dir)
        
        # Upload the zip file to Azure Blob Storage and get a SAS URL
        blob_name = "speaker_clips.zip"  # Use a consistent name to overwrite existing files
        download_url = azure_upload_file_and_get_sas_url(zip_path, blob_name)
        
        # Clean up the local zip file
        os.remove(zip_path)
        
        # Return the download URL
        return {"download_url": download_url}
        
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
            url=content_url, match_voiceprint=True, application_owner=application_owner)

        # Download and convert the MP4 to WAV
        mp4_to_wav_file(mp4_url=mp4_url)

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
                    extract_audio_segment(output_name, segment["start"], segment["end"])

                    # Perform voiceprint matching
                    wav_path = os.path.join(UPLOAD_FOLDER, f"{output_name}.wav")
                    matches = search_voiceprint(wav_path, application_owner)

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

        output_list = []
        for speaker, stats in speaker_stats.items():
            output_list.append(f'Speaker-{speaker}: {stats["identified_name"]}')

        # Return the speaker voiceprint match
        return {"speaker": '\n'.join(output_list)}

    except Exception as e:
        return {"error": str(e)}, 500

# if __name__ == '__main__':
#     response = upload_file_and_get_sas_url(file_path='./uploads/temp_audio.wav', blob_name='temp_audio.wav')
#     print(response)
#     response = delete_blob('temp_audio')
#     print(response)
