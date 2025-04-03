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

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def format_time(seconds):
    minutes, seconds = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def mp4_to_base64(mp4_url: str):
    """
    Downloads an MP4 file from a URL, extracts the audio, converts it to WAV, and returns a base64-encoded string.
    """
    try:
        # Define temporary file paths
        mp4_path = "../uploads/temp_audio.mp4"
        wav_path = "../uploads/temp_audio.wav"

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
        with open(wav_path, "rb") as audio_file:
            encoded_audio = base64.b64encode(audio_file.read()).decode("utf-8")

        # Cleanup temporary files
        os.remove(mp4_path)
        os.remove(wav_path)

        return encoded_audio  # Return the base64-encoded string

    except Exception as e:
        print(f"Error: {e}")
        return None



def extract_audio_segment(output_name: str, start_time: float, end_time: float) -> None:
    """
    Extracts a segment from an audio file and saves it as a new file.

    Parameters:
    - output_name (str): The name of the output audio file
    - start_time (float): Start time in seconds for the segment to extract.
    - end_time (float): End time in seconds for the segment to extract.

    Returns:
    - None
    """

    input_file = os.path.join(UPLOAD_FOLDER, "temp_audio.wav")
    output_file = os.path.join(UPLOAD_FOLDER, f"{output_name}.wav")


    # Load the audio file
    audio = AudioSegment.from_file(input_file)

    # Convert start and end times to milliseconds
    start_ms = start_time * 1000
    end_ms = end_time * 1000

    # Extract the desired segment
    extracted_segment = audio[start_ms:end_ms]

    # Export the extracted segment to a new file
    extracted_segment.export(output_file, format="wav")



def mp4_to_wav_file(mp4_url, save_dir=UPLOAD_FOLDER):
    """
    Downloads an MP4 file, extracts audio as WAV, and saves it.
    Returns the local file path.
    """
    try:
        mp4_path = os.path.join(save_dir, "temp_audio.mp4")
        wav_path = os.path.join(save_dir, "temp_audio.wav")

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

        # Cleanup MP4 to save space
        os.remove(mp4_path)

        return wav_path  # Return local WAV file path

    except Exception as e:
        print(f"Error: {e}")
        return None


if __name__ == '__main__':
    # mp4_to_base64(mp4_url="")
    mp4_url = "https://catomindst.blob.core.windows.net/meeting/Call%20with%20Sunny%20Chan/Call%20with%20Sunny%20Chan-20250306_174429-Meeting%20Recording.mp4?sv=2023-01-03&st=2025-04-02T09%3A25%3A27Z&se=2026-04-03T09%3A25%3A00Z&sr=b&sp=r&sig=2a%2Fp0JrOTHPZFWwIpcEz4lRMLlUbrp%2FoNomidsdSJSk%3D"
    mp4_to_wav_file(mp4_url=mp4_url)
    extract_audio_segment(output_name="temp_clip", start_time=0.0, end_time=20.0)
