from enum import Enum

class NgrokMode(Enum):
    PUBLIC = "public"
    PRIVATE = "private"

class OnPremiseMode(Enum):
    ON_PREMISES = "on_premises"
    ON_CLOUD = "on_cloud"

class Dashboard(Enum):
    TIME_SPENT_BY_PROJECT = 'time_spent_on_project'
    NO_MEETING_BY_PROJECT = 'no_of_meeting_by_project'
    TIME_SPENT_BY_STAFF = 'time_spent_on_project_by_staff'
    LEADERBOARD = 'contribution_leaderboard'