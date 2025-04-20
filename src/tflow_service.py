import requests
import json

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
    response = requests.post("https://www.t-flow.tech/api/v2/open/worksheet/getFilterRows", json=payload)

    output_list = []
    if response and response.status_code == 200:
        project_data_list = response.json().get("data", {}).get("rows", [])
        for project_data in project_data_list:
            glossary_rowid_string = project_data.get('glossary_list', '[]')
            try:
                glossary_rowid_list = json.loads(glossary_rowid_string)
                if not glossary_rowid_list:
                    continue
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
            response_glossary = requests.post("https://www.t-flow.tech/api/v2/open/worksheet/getFilterRows", json=glossary_payload)

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
    response = requests.post("https://www.t-flow.tech/api/v2/open/worksheet/getFilterRows", json=payload)

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
    response = requests.post("https://www.t-flow.tech/api/v2/open/worksheet/getFilterRows", json=payload)

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
        response_speaker_map = requests.post("https://www.t-flow.tech/api/v2/open/worksheet/getFilterRows", json=speaker_payload)

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

# if __name__ == '__main__':
#     x = get_project_memory()
    # print(x)