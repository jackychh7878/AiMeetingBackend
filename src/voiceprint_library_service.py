from resemblyzer import VoiceEncoder, preprocess_wav
from pathlib import Path
import numpy as np
import os
from dotenv import load_dotenv
from typing import List, Dict, Any
from sqlalchemy import create_engine, Column, Integer, String, Text, TIMESTAMP, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import sessionmaker
from sqlalchemy import update
from flask import Flask, request, jsonify
import requests
from werkzeug.utils import secure_filename
import librosa
from typing import Optional, Union


load_dotenv()

# Set a directory for temporary file storage
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {'wav'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)

Base = declarative_base()

class VoiceprintLibrary(Base):
    __tablename__ = 'voiceprint_library'

    sys_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255))
    department = Column(String(255))
    position = Column(String(255))
    embedding = Column(Vector(256))  # Adjust dimensions as needed
    # metadata = Column(JSONB, nullable=False, default=dict)
    created_dt = Column(TIMESTAMP, server_default='CURRENT_TIMESTAMP')


# Replace the environment variable with the properly formatted connection string
DATABASE_URL = os.getenv("AZURE_POSTGRES_CONNECTION")
engine = create_engine(DATABASE_URL, connect_args={'client_encoding': 'utf8'})

Session = sessionmaker(bind=engine)
session = Session()



def get_embedding(file_wav: Union[str, Path, np.ndarray]) -> List[float]:
    """Get voiceprint embedding vector."""
    try:
        wav = preprocess_wav(file_wav)

        encoder = VoiceEncoder()
        embed = encoder.embed_utterance(wav)
        np.set_printoptions(precision=3, suppress=True)
        return embed.tolist()
    except Exception as e:
        print(f"Error getting embedding: {e}")
        return [0] * 256  # Return zero vector on error

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def insert_voiceprint(request):
    name = request.form.get("name")
    email = request.form.get("email")
    department = request.form.get("department")
    position = request.form.get("position")
    audio_files = request.files.getlist("audio_files")  # Get list of uploaded files

    if not name or not audio_files or any(file.filename == '' for file in audio_files):
        return jsonify({"error": "Missing required fields: name and audio_files are required."}), 400

    for audio_file in audio_files:
        if audio_file and allowed_file(audio_file.filename):
            filename = secure_filename(audio_file.filename)
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            audio_file.save(file_path)

            # Process the audio file
            try:
                wav_np, sr = librosa.load(file_path, sr=None)  # Load audio
                embedding = get_embedding(wav_np)
                voiceprint = VoiceprintLibrary(
                    name=name,
                    email=email,
                    department=department,
                    position=position,
                    embedding=embedding
                )
                session.add(voiceprint)
                session.commit()
            except Exception as e:
                session.rollback()
                return jsonify({"error": str(e)}), 500
            finally:
                os.remove(file_path)  # Delete the temporary file after processing
        else:
            return jsonify({"error": f"Invalid file format for file {audio_file.filename}. Only .wav files are allowed."}), 400

    return jsonify({"message": "All voiceprints inserted successfully!"})

def search_voiceprint(file_wav: Union[str, Path, np.ndarray]):
    """Search for the closest matching voiceprint in the database by sending a path with .wav file."""

    temp_path = file_wav
    limit = 3
    confidence_level = 0.8

    # Validate confidence_level is between 0 and 1
    if confidence_level < 0 or confidence_level > 1:
        return jsonify({"error": "confidence_level must be between 0 and 1"}), 400

    try:
        query_embedding = get_embedding(temp_path)

        similarity_score = (1 - VoiceprintLibrary.embedding.cosine_distance(query_embedding)).label("similarity")

        results = (
            session.query(VoiceprintLibrary, similarity_score)
            .filter(VoiceprintLibrary.embedding.is_not(None))
            # Apply confidence level filter directly in the query
            .filter(similarity_score >= confidence_level)
            .order_by(VoiceprintLibrary.embedding.cosine_distance(query_embedding),similarity_score.desc())
            .limit(limit)
            .all()
        )

        # Format the results
        response = []
        for person, similarity in results:
            response_obj = {
                "sys_id": person.sys_id,
                "name": person.name,
                "email": person.email,
                "department": person.department,
                "position": person.position,
                "similarity": float(similarity)
            }
            response.append(response_obj)

        return jsonify(response)

    except Exception as e:
        return jsonify({"error": f"Search error: {str(e)}"})

if __name__ == '__main__':
    app.run(debug=True)
