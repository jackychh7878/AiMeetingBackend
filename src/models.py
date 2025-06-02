from sqlalchemy import Column, Integer, String, Float, Date, TIMESTAMP, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime
from pgvector.sqlalchemy import Vector

Base = declarative_base()

class AppOwnerControl(Base):
    __tablename__ = 'ai_meeting_app_owner_control'

    sys_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    quota_hours = Column(Float, default=0)
    usage_hours = Column(Float, default=0)
    valid_to = Column(Date)
    metadata_json = Column(JSONB, nullable=False, default=dict)
    created_dt = Column(TIMESTAMP, default='CURRENT_TIMESTAMP')

class VoiceprintLibrary(Base):
    __tablename__ = 'voiceprint_library'

    sys_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255))
    department = Column(String(255))
    position = Column(String(255))
    embedding = Column(Vector(256))  # Adjust dimensions as needed
    metadata_json = Column(JSONB, nullable=False, default=dict)
    created_dt = Column(TIMESTAMP, server_default='CURRENT_TIMESTAMP')
