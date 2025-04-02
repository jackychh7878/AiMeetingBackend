import requests
import os
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from pydantic import BaseModel
import base64
from pydub import AudioSegment
from collections import defaultdict


# Load environment variables
load_dotenv()

headers = {
    "Ocp-Apim-Subscription-Key": os.getenv("AZURE_API_KEY"),  # Replace with your actual key
    "Content-Type": "application/json"
}

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

# def fetch_completed_transcription(url: str):
#     response = requests.get(url)
#     response.raise_for_status()  # Raises an error for bad responses
#     json_data = response.json()
#
#     speaker_text_pairs = []
#     for phrase in json_data.get("recognizedPhrases", []):
#         speaker = phrase.get("speaker")
#         display_text = phrase.get("nBest", [{}])[0].get("display", "")
#         offset = phrase.get("offsetInTicks", 0) / 10000000  # Convert ticks to seconds
#         duration = phrase.get("durationInTicks", 0) / 10000000  # Convert ticks to seconds
#
#         start_time = format_time(offset)
#         end_time = format_time(offset + duration)
#
#         if speaker is not None and display_text:
#             speaker_text_pairs.append(f"Speaker-{speaker} ({start_time} - {end_time}): {display_text}")
#     return speaker_text_pairs

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


def format_time(seconds):
    minutes, seconds = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def mp4_to_base64(mp4_url):
    """
    Downloads an MP4 file from a URL, extracts the audio, converts it to WAV, and returns a base64-encoded string.
    """
    try:
        # Define temporary file paths
        mp4_path = "temp_audio.mp4"
        wav_path = "temp_audio.wav"

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

        # Step 3: Encode WAV to base64
        # with open(wav_path, "rb") as audio_file:
        #     encoded_audio = base64.b64encode(audio_file.read()).decode("utf-8")
        #
        # # Cleanup temporary files
        # os.remove(mp4_path)
        # os.remove(wav_path)

        # return encoded_audio  # Return the base64-encoded string

    except Exception as e:
        print(f"Error: {e}")
        return None



def extract_audio_segment(input_file: str, output_file: str, start_time: float, end_time: float) -> None:
    """
    Extracts a segment from an audio file and saves it as a new file.

    Parameters:
    - input_file (str): Path to the input audio file.
    - output_file (str): Path where the extracted segment will be saved.
    - start_time (float): Start time in seconds for the segment to extract.
    - end_time (float): End time in seconds for the segment to extract.

    Returns:
    - None
    """
    # Load the audio file
    audio = AudioSegment.from_file(input_file)

    # Convert start and end times to milliseconds
    start_ms = start_time * 1000
    end_ms = end_time * 1000

    # Extract the desired segment
    extracted_segment = audio[start_ms:end_ms]

    # Export the extracted segment to a new file
    extracted_segment.export(output_file, format="wav")

if __name__ == '__main__':
    mp4_to_base64()