from enum import Enum

class NgrokMode(Enum):
    PUBLIC = "public"
    PRIVATE = "private"

class OnPremiseMode(Enum):
    ON_PREMISES = "on_premises"
    ON_CLOUD = "on_cloud"