import requests
import json

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
#     x = get_meeting_minutes()
#     print(x)