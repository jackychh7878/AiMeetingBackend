import os
from dotenv import load_dotenv
import requests
import json
from collections import defaultdict
from enum import Enum
import urllib.parse
from src.enums import Dashboard, OnPremiseMode

# Load environment variables
load_dotenv()

# Predefined color palette for better visibility
COLOR_PALETTE = [
    "rgba(255, 99, 132, 0.8)",    # Pink
    "rgba(54, 162, 235, 0.8)",    # Blue
    "rgba(255, 206, 86, 0.8)",    # Yellow
    "rgba(75, 192, 192, 0.8)",    # Teal
    "rgba(153, 102, 255, 0.8)",   # Purple
    "rgba(255, 159, 64, 0.8)",    # Orange
    "rgba(199, 199, 199, 0.8)",   # Gray
    "rgba(83, 102, 255, 0.8)",    # Indigo
    "rgba(40, 159, 64, 0.8)",     # Green
    "rgba(210, 199, 199, 0.8)",   # Light Gray
]

TFLOW_HOST = os.getenv("TFLOW_HOST")
ON_PREMISES_MODE = os.getenv("ON_PREMISES_MODE")

def get_project_list(request):
    """
    Join the project list with glossary from t-flow

    Parameters:
    - app_key (str): T-flow app_key
    - sign (str): T-flow sign
    - page_size (int): Number of return item

    Returns:
    - project list data in json format
    """
    data = request.get_json()
    app_key = data.get('app_key')
    sign = data.get('sign')
    page_size = data.get('page_size', 50)


    # Prepare API request
    payload = {
        "appKey": app_key,
        "sign": sign,
        "worksheetId": "project_overview",
        "pageSize": page_size,
        "pageIndex": 1,
        "listType": 0,
        "controls": ["project", "start_date", "overview", "glossary_list"],
        "filters": []
    }
    # Send request to Get Meeting Minutes List API
    response = requests.post(f"{TFLOW_HOST}/api/v2/open/worksheet/getFilterRows", json=payload)

    output_list = []
    if response and response.status_code == 200:
        project_data_list = response.json().get("data", {}).get("rows", [])
        for project_data in project_data_list:
            glossary_rowid_string = project_data.get('glossary_list', '[]')
            try:
                glossary_rowid_list = json.loads(glossary_rowid_string)
            except json.JSONDecodeError:
                glossary_rowid_list = []

            glossary_payload = {
                "appKey": app_key,
                "sign": sign,
                "worksheetId": "project_glossary_list",
                "pageSize": 100,
                "pageIndex": 1,
                "sortId": "autoid",
                "isAsc": True,
                "listType": 0,
                "controls": ["term", "meaning"],
                "filters": [
                    {
                        "controlId": "rowid",
                        "spliceType": 1,
                        "filterType": 2,
                        "values": glossary_rowid_list
                    }
                ]
            }
            response_glossary = requests.post(f"{TFLOW_HOST}/api/v2/open/worksheet/getFilterRows", json=glossary_payload)

            glossary_data = response_glossary.json().get("data", {}).get("rows", [])

            glossary_filtered = [
                {
                    "term": item.get("term"),
                    "meaning": item.get("meaning")
                }
                for item in glossary_data
            ]

            output_json = {
                'project': project_data['project'],
                'overview': project_data['overview'],
                'start_date': project_data['start_date'],
                'glossary_list': glossary_filtered
            }
            output_list.append(output_json)
    
    return {"data": output_list}

def get_project_memory(request):
    """
    Get the project memory and massage the return field

    Parameters:
    - app_key (str): T-flow app_key
    - sign (str): T-flow sign
    - page_size (int): Number of return item
    - project_name (str): Project Name

    Returns:
    - project list data in json format
    """
    data = request.get_json()
    app_key = data.get('app_key')
    sign = data.get('sign')
    page_size = data.get('page_size', 50)
    project_name = data.get('project_name')

    # Prepare API request
    payload = {
        "appKey": app_key,
        "sign": sign,
        "worksheetId": "project_memory",
        "pageSize": page_size,
        "pageIndex": 1,
        "sortId": "datetime",
        "isAsc": False,
        "listType": 0,
        "controls": ["project", "datetime", "meeting_minutes", "memory"],
        "filters": [
            {
                "controlId": "project",
                "spliceType": 1,
                "filterType": 2,
                "value": project_name
            }
        ]
    }
    # Send request to Get Project Memory List API
    response = requests.post(f"{TFLOW_HOST}/api/v2/open/worksheet/getFilterRows", json=payload)

    output_list = []
    if response and response.status_code == 200:
        project_memory_list = response.json().get("data", {}).get("rows", [])

        # Get the Meeting Minutes Rowid for each project
        for project_memory in project_memory_list:
            meeting_minutes_string = project_memory['meeting_minutes']
            meeting_minutes_json = json.loads(meeting_minutes_string)
            sourcevalue = meeting_minutes_json[0]['sourcevalue']
            sourcevalue_dict = json.loads(sourcevalue)
            meeting_minutes_rowid = sourcevalue_dict['rowid']
            output_json = {
                'project': project_memory['project'],
                'datetime': project_memory['datetime'],
                'memory': project_memory['memory'],
                'meeting_minutes_rowid': meeting_minutes_rowid
            }
            output_list.append(output_json)
    return {"data": output_list}

def get_meeting_minutes(request):
    """
    Join the meeting minutes data with speaker data from t-flow

    Parameters:
    - app_key (str): T-flow app_key
    - sign (str): T-flow sign
    - meeting_rowid (str): Meeting row id

    Returns:
    - meeting minutes data in json format
    """
    data = request.get_json()
    app_key = data.get('app_key')
    sign = data.get('sign')
    meeting_rowid = data.get('meeting_rowid')

    # Prepare API request
    payload = {
        "appKey": app_key,
        "sign": sign,
        "worksheetId": "meeting_minutes",
        "sortId": "datetime",
        "isAsc": False,
        "listType": 0,
        "controls": ["project", "datetime", "video_name", "description", "transcript", "ai_summary", "duration", "process_status", "speaker_map", "rowid"],
        "filters": [
            {
                "controlId":"rowid",
                "spliceType": 1,
                "filterType":2,
                "value": meeting_rowid
            }
        ]
    }
    # Send request to Get Meeting Minutes List API
    response = requests.post(f"{TFLOW_HOST}/api/v2/open/worksheet/getFilterRows", json=payload)

    if response:
        meeting_minutes_data = response.json()
        speaker_rowid_string  = meeting_minutes_data['data']['rows'][0]['speaker_map']
        # Convert from string to list
        speaker_rowid_list = json.loads(speaker_rowid_string)
        speaker_payload = {
            "appKey": app_key,
            "sign": sign,
            "worksheetId": "speaker_map",
            "listType": 0,
            "sortId": "speaker",
            "isAsc": True,
            "controls": ["project", "name", "speaker", "talk_time", "total_talk_time", "wpm", "duration", "rowid"],
            "filters": [
                {
                    "controlId": "rowid",
                    "spliceType": 1,
                    "filterType": 2,
                    "values": speaker_rowid_list
                }
            ]
        }
        response_speaker_map = requests.post(f"{TFLOW_HOST}/api/v2/open/worksheet/getFilterRows", json=speaker_payload)

        speaker_map_data = response_speaker_map.json().get("data", {}).get("rows", [])
        output_speaker_data_list = []
        for speaker_map in speaker_map_data:
            try:
                # Safely get and convert talk_time
                talk_time_float = float(speaker_map.get('talk_time', 0))
                speaker_map['talk_time'] = f"{round(talk_time_float * 100)}%"

                output_speaker_data_obj = {
                    'speaker': speaker_map['speaker'],
                    'name': speaker_map['name'],
                    'talk_time_percentage': speaker_map['talk_time'],
                    'total_talk_time_minutes': speaker_map['total_talk_time'],
                    'words_per_minutes': speaker_map['wpm'],
                }
                output_speaker_data_list.append(output_speaker_data_obj)
            except (ValueError, TypeError):
                speaker_map['talk_time'] = "0%"

        output_json = {
            'rowid': meeting_minutes_data['data']['rows'][0]['rowid'],
            'datetime': meeting_minutes_data['data']['rows'][0]['datetime'],
            'video_name': meeting_minutes_data['data']['rows'][0]['video_name'],
            'description': meeting_minutes_data['data']['rows'][0]['description'],
            'duration_minutes': meeting_minutes_data['data']['rows'][0]['duration'],
            'speaker_data': output_speaker_data_list,
            'transcript': meeting_minutes_data['data']['rows'][0]['transcript']
        }
        return output_json

    return response.json()


def generate_chart_url(chart_type, data, labels, datasets):
    """
    Generate a chart URL using quickchart.io
    
    Parameters:
    - chart_type (str): Type of chart (bar, line, etc.)
    - data (dict): Chart data
    - labels (list): Chart labels
    - datasets (list): Chart datasets
    
    Returns:
    - str: URL of the generated chart
    """
    chart_config = {
        "type": chart_type,
        "data": {
            "labels": labels,
            "datasets": datasets
        },
        "options": {
            "responsive": True,
            "plugins": {
                "title": {
                    "display": True,
                    "text": data.get("title", "")
                }
            }
        }
    }
    
    # Encode the chart configuration
    encoded_config = urllib.parse.quote(json.dumps(chart_config))
    return f"https://quickchart.io/chart?c={encoded_config}"

def get_dashboard(request):
    """
    Get the project dashboard by the dashboard name

    Parameters:
    - app_key (str): T-flow app_key
    - sign (str): T-flow sign
    - dashboard_name (str): Dashboard Name (time_spent_on_project, no_of_meeting_by_project, time_spent_on_project_by_staff, contribution_leaderboard)
    - start_dt (date): Range start date from
    - end_dt (date): Range end date to

    Returns:
    - project list data in json format with chart_url
    """
    data = request.get_json()
    app_key = data.get('app_key')
    sign = data.get('sign')
    dashboard_name = data.get('dashboard_name')
    start_dt = data.get('start_dt', None)
    end_dt = data.get('end_dt', None)

    by_project_dashboard = [Dashboard.TIME_SPENT_ON_PROJECT.value, Dashboard.NO_MEETING_BY_PROJECT.value]
    by_staff_dashboard = [Dashboard.TIME_SPENT_BY_STAFF.value, Dashboard.LEADERBOARD.value]

    output_list = []

    # by project dashboard
    if dashboard_name in by_project_dashboard:
        # Prepare API request
        payload = {
            "appKey": app_key,
            "sign": sign,
            "worksheetId": "meeting_minutes",
            "pageSize": 100,
            "pageIndex": 1,
            "sortId": "project",
            "isAsc": False,
            "listType": 0,
            "controls": ["project", "datetime", "video_name", "duration", "rowid"],
            "filters": []
        }
        if start_dt is not None:
            payload['filters'].append({
                "controlId": "datetime",
                "spliceType": 1,
                "filterType": 34,
                "value": start_dt
            })
        if end_dt is not None:
            payload['filters'].append({
                "controlId": "datetime",
                "spliceType": 1,
                "filterType": 36,
                "value": end_dt
            })

        # Send request to Get Project Memory List API
        response = requests.post(f"{TFLOW_HOST}/api/v2/open/worksheet/getFilterRows", json=payload)
        # Dictionaries to hold summaries
        duration_by_project = defaultdict(int)
        meeting_count_by_project = defaultdict(int)

        meeting_minutes_list = response.json().get("data", {}).get("rows", [])

        # Process each meeting record
        for meeting in meeting_minutes_list:
            project = meeting.get("project")
            try:
                duration = int(meeting.get("duration", 0))
            except (ValueError, TypeError):
                duration = 0

            duration_by_project[project] += duration
            meeting_count_by_project[project] += 1


        if dashboard_name == Dashboard.TIME_SPENT_ON_PROJECT.value:
            for project, total_duration in duration_by_project.items():
                output_obj = {
                    "project": project,
                    "total_duration_minutes": total_duration
                }
                output_list.append(output_obj)
            
            # Generate pie chart for time spent by project
            labels = [item["project"] for item in output_list]
            data = [item["total_duration_minutes"] for item in output_list]
            
            datasets = [{
                "data": data,
                "backgroundColor": COLOR_PALETTE[:len(labels)]
            }]
            
            chart_data = {
                "type": "outlabeledPie",
                "data": {
                    "labels": labels,
                    "datasets": datasets
                },
                "options": {
                    "plugins": {
                        "legend": False,
                        "outlabels": {
                            "text": "%l %p",
                            "color": "white",
                            "stretch": 35,
                            "font": {
                                "resizable": True,
                                "minSize": 12,
                                "maxSize": 18
                            }
                        }
                    }
                }
            }
            
            # Encode the chart configuration
            if ON_PREMISES_MODE == OnPremiseMode.ON_CLOUD.value:
                encoded_config = urllib.parse.quote(json.dumps(chart_data))
                chart_url = f"https://quickchart.io/chart?c={encoded_config}"
                return {"data": output_list, "chart_url": chart_url}
            elif ON_PREMISES_MODE == OnPremiseMode.ON_PREMISES.value:
                return {"data": output_list, "chart_url": None}

        if dashboard_name == Dashboard.NO_MEETING_BY_PROJECT.value:
            for project, count in meeting_count_by_project.items():
                output_obj = {
                    "project": project,
                    "number_of_meetings": count
                }
                output_list.append(output_obj)
            
            # Generate chart for number of meetings by project
            labels = [item["project"] for item in output_list]
            datasets = [{
                "label": "Number of Meetings",
                "data": [item["number_of_meetings"] for item in output_list],
                "backgroundColor": "rgba(75, 192, 192, 0.5)"
            }]
            chart_data = {
                "title": "Number of Meetings by Project"
            }
            if ON_PREMISES_MODE == OnPremiseMode.ON_CLOUD.value:
                chart_url = generate_chart_url("bar", chart_data, labels, datasets)
                return {"data": output_list, "chart_url": chart_url}
            elif ON_PREMISES_MODE == OnPremiseMode.ON_PREMISES.value:
                return {"data": output_list, "chart_url": None}

    if dashboard_name in by_staff_dashboard:
        # Prepare API request
        payload = {
            "appKey": app_key,
            "sign": sign,
            "worksheetId": "speaker_map",
            "pageSize": 1000,
            "pageIndex": 1,
            "sortId": "speaker",
            "isAsc": False,
            "listType": 0,
            "controls": ["project", "name", "speaker", "talk_time", "total_talk_time", "wpm", "duration", "rowid"],
            "filters": []
        }
        # Send request to Get Project Memory List API
        response = requests.post(f"{TFLOW_HOST}/api/v2/open/worksheet/getFilterRows", json=payload)

        # Dictionaries to hold summaries
        project_time_by_staff = defaultdict(lambda: defaultdict(int))
        staff_summary = defaultdict(lambda: {
            "total_talk_time": 0,
            "total_meetings": 0,
            "total_duration": 0,
            "total_wpm": 0
        })

        speaker_map_list = response.json().get("data", {}).get("rows", [])

        # Helper functions to safely convert to int and float
        def safe_int(val, default=0):
            try:
                return int(val)
            except (ValueError, TypeError):
                return default

        def safe_float(val, default=0.0):
            try:
                return float(val)
            except (ValueError, TypeError):
                return default

        # Process each record
        for row in speaker_map_list:
            name = row.get("name", "Unknown").strip() or "Unknown"
            project = row.get("project")
            duration = safe_int(row.get("duration", 0))
            total_talk_time = safe_int(row.get("total_talk_time", 0))
            talk_time_ratio = safe_float(row.get("talk_time", 0))
            wpm = safe_int(row.get("wpm", 0))

            # 1. Project time by staff
            project_time_by_staff[name][project] += duration

            # 2. Talk time and other summaries
            staff_summary[name]["total_talk_time"] += total_talk_time
            staff_summary[name]["total_duration"] += duration
            staff_summary[name]["total_meetings"] += 1
            staff_summary[name]["total_wpm"] += wpm

        if dashboard_name == Dashboard.TIME_SPENT_BY_STAFF.value:
            for staff, projects in project_time_by_staff.items():
                if staff == 'Unknown':
                    continue

                output_obj = {"name": staff}
                total_time = 0
                for project, time in projects.items():
                    output_obj[project] = time
                    total_time += time
                output_obj["total_time"] = total_time
                output_list.append(output_obj)
            
            # Generate stacked bar chart for time spent by staff with total labels
            staff_names = [item["name"] for item in output_list]
            projects = list(set().union(*[item.keys() for item in output_list]) - {"name", "total_time"})
            
            datasets = []
            for i, project in enumerate(projects):
                dataset = {
                    "label": project,
                    "data": [item.get(project, 0) for item in output_list],
                    "backgroundColor": COLOR_PALETTE[i % len(COLOR_PALETTE)],
                    "borderColor": "white",
                    "borderWidth": 1
                }
                datasets.append(dataset)
            
            # Add total time dataset
            datasets.append({
                "label": "Total Time",
                "data": [item["total_time"] for item in output_list],
                "backgroundColor": "rgba(0, 0, 0, 0.1)",
                "borderColor": "black",
                "borderWidth": 2,
                "type": "line",
                "fill": False
            })
            
            chart_data = {
                "title": "Time Spent by Staff per Project",
                "options": {
                    "plugins": {
                        "datalabels": {
                            "display": True,
                            "formatter": "(val, ctx) => ctx.datasetIndex === datasets.length - 1 ? `${val} min` : ''",
                            "color": "black",
                            "font": {
                                "weight": "bold"
                            },
                            "align": "top",
                            "anchor": "end"
                        },
                        "legend": {
                            "position": "right",
                            "labels": {
                                "padding": 20,
                                "font": {
                                    "size": 12
                                }
                            }
                        }
                    },
                    "scales": {
                        "x": {
                            "stacked": True,
                            "grid": {
                                "display": False
                            }
                        },
                        "y": {
                            "stacked": True,
                            "beginAtZero": True,
                            "title": {
                                "display": True,
                                "text": "Minutes"
                            }
                        }
                    }
                }
            }
            if ON_PREMISES_MODE == OnPremiseMode.ON_CLOUD.value:
                chart_url = generate_chart_url("bar", chart_data, staff_names, datasets)
                return {"data": output_list, "chart_url": chart_url}
            elif ON_PREMISES_MODE == OnPremiseMode.ON_PREMISES.value:
                return {"data": output_list, "chart_url": None}

        if dashboard_name == Dashboard.LEADERBOARD.value:
            for staff, stats in staff_summary.items():
                if staff == 'Unknown':
                    continue

                number_of_meetings = stats["total_meetings"]
                total_talk_time = stats["total_talk_time"]
                avg_talk_time = stats["total_talk_time"] / number_of_meetings if number_of_meetings else 0
                avg_talk_time_percentage = (stats["total_talk_time"] / stats["total_duration"] * 100) if stats["total_duration"] else 0
                avg_wpm = stats["total_wpm"] / number_of_meetings if number_of_meetings else 0
                output_obj = {
                    "name": staff,
                    "total_number_of_meeting": number_of_meetings,
                    "total_talk_time_minutes": f"{total_talk_time}",
                    "avg_talk_time_minutes": f"{avg_talk_time:.2f}",
                    "avg_talk_time_percent": f"{avg_talk_time_percentage:.2f}",
                    "avg_wpm": f"{avg_wpm:.2f}"
                }
                output_list.append(output_obj)
            
            return {"data": output_list}

    return {"data": output_list}



# if __name__ == '__main__':
#     x = get_dashboard()
#     print(x)