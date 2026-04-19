import os
import json
import pickle
from datetime import datetime, timedelta
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar"]
TOKEN_PATH = os.path.join(os.path.dirname(__file__), "token.pickle")
CREDS_PATH = os.path.join(os.path.dirname(__file__), "credentials.json")


def get_calendar_service():
    creds = None
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, "rb") as f:
            creds = pickle.load(f)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDS_PATH):
                raise FileNotFoundError(
                    f"Missing {CREDS_PATH}. Download OAuth2 credentials from "
                    "Google Cloud Console and save as credentials.json in the client directory."
                )
            flow = InstalledAppFlow.from_client_secrets_file(CREDS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, "wb") as f:
            pickle.dump(creds, f)
    return build("calendar", "v3", credentials=creds)


def add_game_to_calendar(
    summary: str,
    start_date: str,
    start_time: str = None,
    venue: str = None,
    description: str = None,
    duration_hours: float = 2.5,
    calendar_id: str = "primary",
) -> dict:
    service = get_calendar_service()

    if start_time and start_time != "None" and start_time.strip():
        time_clean = start_time.replace(":", "")[:4]
        hour = int(time_clean[:2])
        minute = int(time_clean[2:4]) if len(time_clean) >= 4 else 0
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(hour=hour, minute=minute)
        end_dt = start_dt + timedelta(hours=duration_hours)
        event_body = {
            "summary": summary,
            "start": {"dateTime": start_dt.isoformat(), "timeZone": "America/New_York"},
            "end": {"dateTime": end_dt.isoformat(), "timeZone": "America/New_York"},
        }
    else:
        event_body = {
            "summary": summary,
            "start": {"date": start_date},
            "end": {"date": start_date},
        }

    if venue:
        event_body["location"] = venue
    if description:
        event_body["description"] = description

    event_body["reminders"] = {
        "useDefault": False,
        "overrides": [
            {"method": "popup", "minutes": 30},
        ],
    }

    created = service.events().insert(calendarId=calendar_id, body=event_body).execute()
    return {
        "status": "created",
        "event_id": created["id"],
        "link": created.get("htmlLink"),
        "summary": summary,
        "start": start_date,
    }


def list_sports_events_on_calendar(
    date_from: str = None,
    date_to: str = None,
    calendar_id: str = "primary",
) -> list[dict]:
    service = get_calendar_service()
    if not date_from:
        date_from = datetime.now().strftime("%Y-%m-%d")
    if not date_to:
        date_to = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")

    time_min = f"{date_from}T00:00:00Z"
    time_max = f"{date_to}T23:59:59Z"

    results = service.events().list(
        calendarId=calendar_id,
        timeMin=time_min,
        timeMax=time_max,
        maxResults=50,
        singleEvents=True,
        orderBy="startTime",
        q="vs",
    ).execute()

    events = results.get("items", [])
    return [
        {
            "id": e["id"],
            "summary": e.get("summary"),
            "start": e["start"].get("dateTime", e["start"].get("date")),
            "end": e["end"].get("dateTime", e["end"].get("date")),
            "location": e.get("location"),
        }
        for e in events
    ]
