import os
from dotenv import load_dotenv
from typing import Optional
from src.enums import OnPremiseMode

# Load environment variables
load_dotenv()

def get_database_url() -> Optional[str]:
    on_premises_mode = os.getenv("ON_PREMISES_MODE")
    if on_premises_mode == OnPremiseMode.ON_CLOUD.value:
        return os.getenv("AZURE_POSTGRES_CONNECTION")
    elif on_premises_mode == OnPremiseMode.ON_PREMISES.value:
        return os.getenv("ON_PREMISES_POSTGRES_CONNECTION")
    return None 