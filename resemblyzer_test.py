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

load_dotenv()

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



def get_embedding(fpath: Path) -> List[float]:
    """Get embedding vector from OpenAI."""
    try:
        wav = preprocess_wav(fpath)

        encoder = VoiceEncoder()
        embed = encoder.embed_utterance(wav)
        np.set_printoptions(precision=3, suppress=True)
        return embed.tolist()
    except Exception as e:
        print(f"Error getting embedding: {e}")
        return [0] * 256  # Return zero vector on error


fpath = Path("sample_audio/enrollment_voiceprint_jacky.wav")
# wav = preprocess_wav(fpath)
#
# encoder = VoiceEncoder()
# embed = encoder.embed_utterance(wav)
# np.set_printoptions(precision=3, suppress=True)
# print(embed)


@app.route('/insert_voiceprint', methods=['POST'])
def insert_voiceprint():
    data = request.json
    name = data.get("name")
    email = data.get("email")
    department = data.get("department")
    position = data.get("position")
    # audio_path = data.get("audio_path")  # Path to audio file
    audio_path = "sample_audio/enrollment_voiceprint_kelvin.wav"

    if not all([name, audio_path]):
        return jsonify({"error": "Missing required fields: name and audio_path are required."}), 400

    try:
        embedding = get_embedding(Path(audio_path))
        voiceprint = VoiceprintLibrary(
            name=name,
            email=email,
            department=department,
            position=position,
            embedding=embedding
        )
        session.add(voiceprint)
        session.commit()
        return jsonify({"message": "Voiceprint inserted successfully!"}), 201
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500


@app.route('/search_voiceprint', methods=['POST'])
def search_voiceprint():
    """Search for the closest matching voiceprint in the database by sending a .wav file."""
    # if 'file' not in request.files:
    #     return jsonify({"error": "No file uploaded"}), 400

    # file = request.files['file']
    # temp_path = Path("./temp_audio.wav")
    # file.save(temp_path)
    data = request.json
    temp_path = data.get("path")
    # temp_path = "sample_audio/test_jacky.wav"

    try:
        query_embedding = get_embedding(temp_path)
        # temp_path.unlink()  # Remove temp file

        similarity_score = (1 - VoiceprintLibrary.embedding.cosine_distance(query_embedding)).label("similarity")

        results = (
            session.query(VoiceprintLibrary, similarity_score)
            .filter(VoiceprintLibrary.embedding.is_not(None))
            .order_by(VoiceprintLibrary.embedding.cosine_distance(query_embedding),similarity_score.desc())
            .limit(1)
            .all()
        )

        if not results:
            return jsonify({"message": "No matching voiceprint found."}), 404

        person, similarity = results[0]
        response = {
            "sys_id": person.sys_id,
            "name": person.name,
            "email": person.email,
            "department": person.department,
            "position": person.position,
            "similarity": float(similarity)
        }
        return jsonify(response)

    except Exception as e:
        return jsonify({"error": f"Search error: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True)
