from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os
from dotenv import load_dotenv
from src.models import AppOwnerControl

# Load environment variables
load_dotenv()

# Create database engine
DATABASE_URL = os.getenv("AZURE_POSTGRES_CONNECTION")
engine = create_engine(DATABASE_URL, connect_args={'client_encoding': 'utf8'})
Session = sessionmaker(bind=engine)

def check_quota(application_owner: str, duration_hours: float) -> tuple[bool, str]:
    """
    Check if the application owner has enough quota for the transcription.
    
    Args:
        application_owner: The name of the application owner
        duration_hours: The duration of the transcription in hours
        
    Returns:
        tuple: (is_allowed: bool, message: str)
    """
    session = Session()
    try:
        # Get the app owner control record
        app_owner = session.query(AppOwnerControl).filter(
            AppOwnerControl.name == application_owner,
            AppOwnerControl.valid_to >= datetime.now().date()
        ).first()
        
        if not app_owner:
            return False, "Application owner not found or subscription expired"
            
        # Check if there's enough quota
        if app_owner.usage_hours + duration_hours > app_owner.quota_hours:
            return False, "Insufficient quota hours"
            
        # Update usage hours with 2 decimal places
        app_owner.usage_hours = round(app_owner.usage_hours + duration_hours, 2)
        session.commit()
        
        return True, "Quota check passed"
        
    except Exception as e:
        session.rollback()
        return False, f"Error checking quota: {str(e)}"
    finally:
        session.close() 