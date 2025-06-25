import os
from dotenv import load_dotenv
from typing import Optional
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime

from src.enums import OnPremiseMode
from src.models import AppOwnerControl
from src.db_config import get_database_url


# Load environment variables
load_dotenv()

DATABASE_URL = get_database_url()

# Create database engine
engine = create_engine(DATABASE_URL, connect_args={'client_encoding': 'utf8'})
Session = sessionmaker(bind=engine)
session = Session()

def check_quota(application_owner: str, duration_hours: float, is_update_hours: bool = True) -> tuple[bool, str]:
    """
    Check if the application owner has enough quota for the transcription.
    
    Args:
        application_owner: The name of the application owner
        duration_hours: The duration of the transcription in hours
        is_update_hours: Whether the durations hours should be added to the existing usage hours
        
    Returns:
        tuple: (is_allowed: bool, message: str)
    """
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
        if is_update_hours:
            app_owner.usage_hours = round(app_owner.usage_hours + duration_hours, 2)
            session.commit()
        
        return True, "Quota check passed"
        
    except Exception as e:
        session.rollback()
        return False, f"Error checking quota: {str(e)}"
    finally:
        session.close()

if __name__ == '__main__':
    is_allowed, message = check_quota(application_owner="catomind", duration_hours=1, is_update_hours=True)
    print(is_allowed)
    print(message)