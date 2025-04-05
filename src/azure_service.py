from dotenv import load_dotenv
import requests
import os
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


def azure_transcription(request):
    data = request.get_json()
    url = data.get('url')
    try:
        content_url_list, sys_ids = azure_check_status(url)
        if content_url_list != "In Progress":
            output_list = []
            for i, content_url in enumerate(content_url_list[:-1]):
                speaker_text_pairs, speaker_stats, total_duration, source_url = azure_fetch_completed_transcription(content_url)
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


UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def azure_fetch_completed_transcription(url: str):
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


# if __name__ == '__main__':
#     response = upload_file_and_get_sas_url(file_path='./uploads/temp_audio.wav', blob_name='temp_audio.wav')
#     print(response)
#     response = delete_blob('temp_audio')
#     print(response)