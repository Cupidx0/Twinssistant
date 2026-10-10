import base64
import json
import os
from datetime import datetime, timedelta

from dateutil import parser
from flask import Blueprint, request, jsonify
from google.auth.transport.requests import Request
from google.cloud.firestore_v1.base_query import FieldFilter
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from Routing import create_chat_completion, extract_function_call, extract_message_content, create_gemini_completion
from auth_utils import require_auth, init_firebase
from gmail_call import mail_box
from utils import get_request_json, parse_natural_datetime

calendar_bp = Blueprint('calendar', __name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCOPES = ["https://www.googleapis.com/auth/calendar"]

firebase_app, db = init_firebase()


def get_creds():
    """
    Load credentials from token.json and refresh if expired.
    Raises error if not found, instructing to run login_calendar.py first.
    """
    from google.oauth2.credentials import Credentials
    token_path = os.path.join(BASE_DIR, "token.json")
    if not os.path.exists(token_path):
        raise FileNotFoundError("token.json not found. Run login_calendar.py first.")
    creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if creds and not creds.valid and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(token_path, "w") as token:
            token.write(creds.to_json())
    return creds
def get_gmail_creds():
    """
    Load Gmail credentials from token_gmail.json and refresh if expired.
    Raises error if not found, instructing to run login_gmail.py first.
    """
    from google.oauth2.credentials import Credentials
    token_path = os.path.join(BASE_DIR, "token_gmail.json")
    if not os.path.exists(token_path):
        raise FileNotFoundError("token_gmail.json not found. Run login_gmail.py first.")
    creds = Credentials.from_authorized_user_file(token_path, ["https://www.googleapis.com/auth/gmail.modify"])
    if creds and not creds.valid and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(token_path, "w") as token:
            token.write(creds.to_json())
    return creds

def safe_get_calendar_events(data, user_id):
    try:
        summary = data.get("summary")
        start_time = data.get("start")
        end_time = data.get("end")
        if summary and start_time and end_time:
            return add_event_to_calendar(summary, start_time, end_time)
        max_results = data.get("maxResults", 5)
        return get_calendar_events(user_id=user_id, maxResults=max_results)
    except Exception as e:
        return {"error": str(e), "debug": str(e.__traceback__)}

@calendar_bp.route('/calendar', methods=['GET'])
@require_auth
def calendar():
    try:
        creds = get_creds()
        service = build("calendar", "v3", credentials=creds)
        today = datetime.utcnow().date()
        now = str(today) + "T00:00:00Z"
        events_result = service.events().list(
            calendarId="primary",
            timeMin=now,
            maxResults=10,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        events = events_result.get("items", [])
        total_duration = timedelta(
            seconds=0,
            minutes=0,
            hours=0,
        )

        formatted = []
        id = 0
        for event in events:
            start = event["start"].get("dateTime", event["start"].get("date"))
            end = event["end"].get("dateTime", event["end"].get("date"))
            try:
                start_dt = parser.isoparse(start)
                end_dt = parser.isoparse(end)
                duration = end_dt - start_dt
                total_duration += duration
            except Exception as e:
                duration = "N/A"
            id += 1
            event["id"] = id
            event["duration"] = str(duration)
            formatted.append({event['summary']: {'start': start, 'end': end, 'duration': str(duration)}})

        return jsonify({"events": formatted})

    except HttpError as error:
        return jsonify({"error": str(error)}), 500


# ✅ single clean version
def add_event_to_calendar(summary, start_time, end_time):
    creds = get_creds()
    service = build("calendar", "v3", credentials=creds)
    event = {
        "summary": summary,
        "start": {"dateTime": start_time, "timeZone": "Europe/London"},
        "end": {"dateTime": end_time, "timeZone": "Europe/London"},
    }
    created_event = service.events().insert(calendarId="primary", body=event).execute()
    #return f"Event created: {created_event.get('htmlLink')}"
    return created_event

def get_email_body(payload):
    # Simple case: body directly on payload
    if payload.get("body", {}).get("data"):
        data = payload["body"]["data"]
        return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")

    # Multipart case: look through parts for text/plain
    if "parts" in payload:
        for part in payload["parts"]:
            if part.get("mimeType") == "text/plain":
                data = part.get("body", {}).get("data")
                if data:
                    return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
            # Some emails nest parts inside parts (multipart/alternative inside multipart/mixed)
            if "parts" in part:
                nested = get_email_body(part)
                if nested:
                    return nested

    return "(no readable body found)"
def summarize_email_body(body):
    # Simple summarization: take the first 200 characters
    summary = body.strip().replace("\n", " ")
    #prompt = f"Summarize the following email content in a concise manner take out any unnecessary details and return the summarries as list:\n\n{summary}\n\nSummary:"
    response = create_gemini_completion(
        model="gemini-3.1-flash-lite",
        messages=[
            {"role": "system", "content": f"provide a concise summary of the email content, focusing on key points and actionable items,make the answer just text ,short and clear,using minimum words focusing more on just the subjects and return the summarries as list."},
            {"role": "user", "content": f"{summary}"},
        ],
        max_tokens=2048,
        temperature=0.7
    )
    response_text = extract_message_content(response).strip()
    return response_text


@calendar_bp.route('/mail/notice', methods=['POST'])
@require_auth
#send important mails to the user front end summary
def mail_notice():
    service = build("gmail", "v1", credentials=get_gmail_creds())
    user_choice = request.json.get("choice")
    user_status = request.json.get("stat")
    mail = mail_box(user_status,user_choice)
    important_mails = []
    if not mail:
        return jsonify({"reply": "No important messages found."})
    for message in mail[:5]:
        msg = service.users().messages().get(userId="me", id=message["id"], format="full").execute()
        body = get_email_body(msg["payload"])
        summary = summarize_email_body(body)
        print(f'  Subject: {summary}')
        important_mails.append(summary.replace("**", " "))
    return jsonify({"mail_reply": important_mails})
@calendar_bp.route('/calendar/add', methods=['POST'])
@require_auth
def calendar_add():
    try:
        data = request.get_json()
        summary = data.get("summary")
        end_time = data.get("end")  # ISO 8601 string
        user_id = request.user["uid"]
        if not all([summary, end_time]):
            return jsonify({"error": "summary and end are required"}), 400

        end_time_obj = datetime.fromisoformat(end_time)
        start_time = end_time_obj - timedelta(hours=1)

        # Add to Google Calendar
        result = add_event_to_calendar(
            summary,
            start_time.isoformat(),
            end_time_obj.isoformat()
        )

        # Firestore upsert
        event_doc = {
            "summary": summary,
            "start": start_time.isoformat(),
            "end": end_time_obj.isoformat(),
            "duration": str(end_time_obj - start_time),
            "googleEventId": result.get("id"),  # returned from Google Calendar
            "htmlLink":result.get("htmlLink"),
            "userId": user_id,
        }
        db.collection("events").document(result["id"]).set(event_doc, merge=True)

        return jsonify({"reply":f"Event Created:{result.get('htmlLink')}"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


calendar_functions = [
    {
        "name": "get_calendar_events",
        "description": "Retrieve upcoming events from the user's Google Calendar",
        "parameters": {
            "type": "object",
            "properties": {
                "maxResults": {"type": "integer", "description": "Number of events to fetch (default 5)"}
            }
        }
    },
    {
        "name": "add_calendar_event",
        "description": "Add a new event to the user's Google Calendar",
        "parameters": {
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "Event title"},
                "end": {"type": "string", "description": "End time in ISO 8601 format"}
            },
            "required": ["summary", "end"]
        }
    }
]


def get_calendar_events(user_id, maxResults=5):
    creds = get_creds()
    service = build("calendar", "v3", credentials=creds)

    today = datetime.utcnow().date()
    now = str(today) + "T00:00:00Z"

    events_result = service.events().list(
        calendarId="primary",
        timeMin=now,
        maxResults=maxResults,
        singleEvents=True,
        orderBy="startTime",
        timeZone="Europe/London",
    ).execute()

    events = events_result.get("items", [])
    total_duration = timedelta()
    formatted = []
    id_counter = 0

    for event in events:
        start = event["start"].get("dateTime", event["start"].get("date"))
        end = event["end"].get("dateTime", event["end"].get("date"))
        try:
            start_dt = parser.isoparse(start)
            end_dt = parser.isoparse(end)
            duration = end_dt - start_dt
            total_duration += duration
        except Exception:
            duration = "N/A"

        google_id = event.get("id")
        id_counter += 1

        event_doc = {
            "id": id_counter,
            "summary": event.get("summary", "No Title"),
            "start": start or "N/A",
            "end": end or "N/A",
            "duration": str(duration),
            "googleEventId": google_id,
            "userId": user_id,
        }

        # Firestore upsert
        snapshot = db.collection("events").where(filter=FieldFilter("googleEventId", "==", google_id)).limit(1).get()
        if not snapshot:
            db.collection("events").document(google_id).set(event_doc, merge=True)
        else:
            for doc in snapshot:
                db.collection("events").document(doc.id).set(event_doc, merge=True)

        formatted.append(event_doc)

    return {
        "events": formatted,
        "total_duration": str(total_duration)
    }
@calendar_bp.route("/calendar/get", methods=["POST"])
@require_auth
def fetch_calendar_events():
    try:
        data = get_request_json()
        events = safe_get_calendar_events(data, request.user["uid"])
        return jsonify({"events":events})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@calendar_bp.route('/calendar/delete', methods=['DELETE'])
@require_auth
def calendar_delete():
    try:
        data = request.get_json()
        event_id = data.get("eventId")
        user_id = request.user["uid"]

        if not event_id:
            return jsonify({"error": "eventId is required"}), 400

        # 🔹 Delete from Google Calendar
        creds = get_creds()
        service = build("calendar", "v3", credentials=creds)
        service.events().delete(
            calendarId="primary",
            eventId=event_id
        ).execute()

        # 🔹 Delete from Firestore
        docs = db.collection("events") \
                 .where(filter=FieldFilter("googleEventId", "==", event_id)) \
                 .where(filter=FieldFilter("userId", "==", user_id)) \
                 .stream()
        for doc in docs:
            doc.reference.delete()

        return jsonify({"success": True, "reply": f"Event {event_id} deleted successfully."})

    except HttpError as error:
        return jsonify({"success": False, "error": f"Google Calendar error: {str(error)}"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@calendar_bp.route('/calendar/manage', methods=['POST'])
@require_auth
def calendar_manage():
    try:
        data = get_request_json()
        message = data.get("question", "").strip()
        calevent = safe_get_calendar_events(data, request.user["uid"])
        if not message:
            return jsonify({"error": "Please provide a question."}), 400
        prompt =( f"User request: {message}\nManage Google Calendar accordingly.\n"
                   "add events with start and end times, or fetch upcoming events.\n"
                     "Always provide start and end times in natural language or ISO format.\n"
                     f"use {calevent} to fetch events and add events with add_calendar_event.\n"
                     "start with a friendly greeting and confirm actions."
                   )
        response = create_chat_completion(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a smart assistant that manages Google Calendar. Always try to provide start and end times in natural language or ISO format."},
                {"role": "user", "content":prompt}
            ],
            functions=calendar_functions,
            function_call="auto"
        )

        msg = response["choices"][0]["message"] if isinstance(response, dict) else response.choices[0].message
        fn = extract_function_call(msg)

        if fn:
            fn_name = fn["name"]
            args = json.loads(fn.get("arguments") or "{}")

            if fn_name == "get_calendar_events":
                events = safe_get_calendar_events(args, request.user["uid"])
                return jsonify({"reply": events})

            elif fn_name == "add_calendar_event":
                summary = args["summary"]
                end_time = parse_natural_datetime(args["end"])

                if not end_time:
                    return jsonify({"error": "Could not parse date/time"}), 400

                end_time_obj = datetime.fromisoformat(end_time)
                start_time = end_time_obj - timedelta(hours=1)

                result = add_event_to_calendar(summary, start_time.isoformat(), end_time_obj.isoformat())
                return jsonify({"reply": result})

        content = msg.get("content") if isinstance(msg, dict) else getattr(msg, "content", None)
        return jsonify({"reply": content or "Sorry, I could not process that."})

    except Exception as e:
        return jsonify({"error": str(e)}), 500
