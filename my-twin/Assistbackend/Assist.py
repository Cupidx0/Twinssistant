from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from dotenv import load_dotenv
from firebase_admin import credentials, firestore, initialize_app
import requests
from dateutil import parser
import dateparser
from eleven import text_to_speech_ws_streaming
import asyncio
import base64
from tavily import TavilyClient
from datetime import datetime, timedelta
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from gtts import gTTS
from Routing import create_chat_completion, extract_function_call, create_anthropic_completion, extract_message_content, create_gemini_completion
import io
import re
import json
from flask_socketio import SocketIO, emit
from cv_route import cv_bp
from Pinecone_vec import save_pattern, find_pattern
from auth_utils import require_auth
try:
    import holidays as holidays_lib
except ImportError:
    holidays_lib = None
# Load env variables
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CV_DIR = os.path.join(BASE_DIR, "Cv_docs")
CV_INFO_FILE = os.path.join(BASE_DIR, "refined")
CHAT_DIR = os.path.join(BASE_DIR, "chat")
CHAT_HISTORY_FILE = os.path.join(CHAT_DIR, "chat_history.txt")
load_dotenv()
api_key = os.getenv("OPENWEATHER_API_KEY")
city = "horley"
tavilyclient = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
SCOPES = ["https://www.googleapis.com/auth/calendar"]
# Initialize Firebase properly
cred = credentials.Certificate(os.path.join(BASE_DIR, "tw.json"))  # 👈 your Firebase service account JSON
firebase_app = initialize_app(cred)
db = firestore.client()
# Flask app
app = Flask(__name__)
app.register_blueprint(cv_bp)
CORS(app, supports_credentials=True, origins=["http://localhost:5173"])
socketio = SocketIO(app, cors_allowed_origins="http://localhost:5173", async_mode='threading')
@app.route('/')
def home():
    return "Welcome to the Assistant API!"
def parse_natural_datetime(text, base_time=None):
    """
    Convert natural language datetime (e.g. 'tomorrow 7pm') into ISO 8601.
    If parsing fails, returns None.
    """
    settings = {"RELATIVE_BASE": base_time or datetime.now()}
    dt = dateparser.parse(text, settings=settings)
    return dt.isoformat() if dt else None
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

def get_request_json():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}

def safe_get_calendar_events(data, user_id):
    try:
        max_results = data.get("maxResults", 5)
        return get_calendar_events(user_id=user_id, maxResults=max_results)
    except Exception as e:
        return {"error": str(e)}

def get_easter_date(year):
    """Return Easter Sunday for the given year using the Gregorian algorithm."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return datetime(year, month, day).date()

def get_nth_weekday(year, month, weekday, occurrence):
    """Return the nth weekday in a month, where Monday is 0."""
    current = datetime(year, month, 1).date()
    while current.weekday() != weekday:
        current += timedelta(days=1)
    return current + timedelta(weeks=occurrence - 1)

def get_last_weekday(year, month, weekday):
    """Return the last weekday in a month, where Monday is 0."""
    if month == 12:
        current = datetime(year + 1, 1, 1).date() - timedelta(days=1)
    else:
        current = datetime(year, month + 1, 1).date() - timedelta(days=1)
    while current.weekday() != weekday:
        current -= timedelta(days=1)
    return current

def get_substitute_holiday(actual_date):
    """Shift weekend public holidays to the next working day."""
    if actual_date.weekday() == 5:
        return actual_date + timedelta(days=2)
    if actual_date.weekday() == 6:
        return actual_date + timedelta(days=1)
    return actual_date

def get_uk_holidays(year):
    """Return a mapping of UK holiday dates to holiday names."""
    if holidays_lib is not None:
        try:
            return {
                holiday_date: holiday_name
                for holiday_date, holiday_name in holidays_lib.country_holidays("GB", years=year).items()
            }
        except Exception:
            pass

    easter_sunday = get_easter_date(year)
    easter_monday = easter_sunday + timedelta(days=1)
    good_friday = easter_sunday - timedelta(days=2)

    new_year = datetime(year, 1, 1).date()
    christmas = datetime(year, 12, 25).date()
    boxing_day = datetime(year, 12, 26).date()

    holiday_map = {
        get_substitute_holiday(new_year): "New Year's Day",
        datetime(year, 2, 14).date(): "Valentine's Day",
        datetime(year, 3, 17).date(): "St Patrick's Day",
        datetime(year, 10, 31).date(): "Halloween",
        datetime(year, 11, 5).date(): "Bonfire Night",
        datetime(year, 12, 24).date(): "Christmas Eve",
        get_substitute_holiday(christmas): "Christmas Day",
        get_substitute_holiday(boxing_day): "Boxing Day",
        good_friday: "Good Friday",
        easter_sunday: "Easter",
        easter_monday: "Easter Monday",
        get_nth_weekday(year, 5, 0, 1): "Early May Bank Holiday",
        get_last_weekday(year, 5, 0): "Spring Bank Holiday",
        get_last_weekday(year, 8, 0): "Summer Bank Holiday",
    }

    if get_substitute_holiday(christmas) == get_substitute_holiday(boxing_day):
        holiday_map[christmas + timedelta(days=2)] = "Boxing Day"

    return holiday_map

def get_current_label(current_date):
    """Return today's holiday if it is exact, otherwise return the meteorological season."""
    holiday = get_uk_holidays(current_date.year).get(current_date)
    if holiday:
        return holiday

    month = current_date.month
    if month in (3, 4, 5):
        return "Spring"
    if month in (6, 7, 8):
        return "Summer"
    if month in (9, 10, 11):
        return "Autumn"
    return "Winter"

@app.route('/calendar', methods=['GET'])
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


@app.route('/calendar/add', methods=['POST'])
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
        snapshot = db.collection("events").where("googleEventId", "==", google_id).limit(1).get()
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
@app.route("/calendar/get", methods=["POST"])
@require_auth
def fetch_calendar_events():
    try:
        data = get_request_json()
        events = safe_get_calendar_events(data, request.user["uid"])
        return jsonify({"events":events})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/calendar/delete', methods=['DELETE'])
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
                 .where("googleEventId", "==", event_id) \
                 .where("userId", "==", user_id) \
                 .stream()
        for doc in docs:
            doc.reference.delete()

        return jsonify({"success": True, "reply": f"Event {event_id} deleted successfully."})

    except HttpError as error:
        return jsonify({"success": False, "error": f"Google Calendar error: {str(error)}"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/calendar/manage', methods=['POST'])
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
def fetch_weather(city_name):
    """Fetch current weather for a city; returns a dict or None."""
    url = f"https://api.openweathermap.org/data/2.5/weather?q={city_name}&appid={api_key}&units=metric"
    weather_data = requests.get(url, timeout=10).json()
    if weather_data.get("main"):
        return {
            "city": city_name,
            "temperature": weather_data["main"]["temp"],
            "description": weather_data["weather"][0]["description"],
        }
    return None

@app.route('/weather', methods=['POST'])
def getWeather():
    try:
        data = get_request_json()
        city_name = data.get("location", "London")
        weather = fetch_weather(city_name)
        if weather:
            return jsonify({"weather": weather})
        return jsonify({"error": "Sorry, I could not fetch the weather right now."}), 404

    except Exception as e:
        return jsonify({"error": str(e)}), 500
@app.route('/outfit',methods=['POST'])
@require_auth
def outfit():
    try:
        data = request.get_json()
        message = data.get("fit", "").strip()
        user_time = datetime.now()
        city = "Horley"
        weather = fetch_weather(city)
        if not message:
            return jsonify({"error": "Please provide a question."}), 400
        prompt =( 
                  f"User request: {message}\n Suggest outfit for user based on the weather and the {user_time} time."
                  "based on if its morning ,afternoon and night.\n"
                  f"use the {weather} to decide which outfit to recommend to the user and also for the {city}location.\n"
                  "output the weather info to the user before the outfit idea. \n"
                  "start with a friendly greeting and confirm actions."
                   )
        response = create_chat_completion(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a smart assistant that manages Fashion closet. Always try to provide relevant outfit to the user based on the weather whilst keeping your word length at a minimum."},
                {"role": "user", "content":prompt}
            ],
            max_tokens=180,
            temperature=0.7
        )
        outgen = extract_message_content(response).strip()
        return jsonify({'outgen':outgen})
    except Exception as e:
        return jsonify({"error":str(e)}),500
@app.route('/holiday_season', methods=['POST'])
def holiday_season():
    try:
        current_date = datetime.now().date()
        dreply = get_current_label(current_date)
        return jsonify({"dreply": dreply})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
def has_word(text, words):
    """Match whole words/phrases, not substrings ('hi' should not match 'this')."""
    return any(re.search(rf"\b{re.escape(w)}\b", text) for w in words)

WEB_SEARCH_KEYWORDS = [
    "latest", "news", "search", "youtube", "today", "current", "year",
    "music", "song", "songs", "weather", "sports", "football", "cricket", "president",
    "prime minister", "capital of", "country", "countries", "who is", "what is",
    "when is", "where is", "how to", "define"
]

def keyword_classify(user_text):
    text = user_text.lower()

    if has_word(text, [
        "good morning", "good afternoon", "good evening", "hello", "hi", "hey", "how are you"
    ]):
        return "greeting"

    if has_word(text, [
        "what are you", "who made you", "your name"
    ]):
        return "identity"

    if has_word(text, [
        "calendar", "schedule", "remind", "meeting", "event", "appointment", "book"
    ]):
        return "calendar"

    if has_word(text, [
        "cv", "resume", "cover letter", "job application", "rewrite my cv"
    ]):
        return "cv"

    if has_word(text, [
        "open", "launch", "play", "spotify", "file", "folder", "close", "quit"
    ]):
        return "mac_control"

    if has_word(text, [
        "code", "debug", "error", "function", "python", "react", "flask", "bug", "fix"
    ]):
        return "code"

    if has_word(text, WEB_SEARCH_KEYWORDS):
        return "web_search"

    return "casual"

INTENT_NAMES = ["calendar", "cv", "mac_control", "code", "greeting", "web_search", "identity", "casual"]

def intent_classifier(user_text):
    try:
        cached_intent, cached_confidence = find_pattern(user_text)
        if cached_intent:
            print(f"Found cached intent: {cached_intent} with confidence {cached_confidence}")
            return cached_intent, cached_confidence
    except Exception as e:
        print(f"Intent cache lookup failed: {e}")

    intent = keyword_classify(user_text)
    confidence = 0.9 if intent != "casual" else 0.5
    if confidence < 0.7:
        try:
            response = create_gemini_completion(
                model="gemini-3.1-flash-lite",
                messages=[
                    {"role": "system", "content": (
                        "You classify user intents. Respond with JSON only: "
                        f'{{"intent": one of {INTENT_NAMES}, "confidence": 0-1}}'
                    )},
                    {"role": "user", "content": f"Classify the intent of this message: '{user_text}'"}
                ],
                max_tokens=50,
                temperature=0.5
            )
            response_text = extract_message_content(response).strip()
            match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if not match:
                raise ValueError(f"No JSON found in: {response_text}")
            response_json = json.loads(match.group())
            intent = response_json.get("intent", intent)
            confidence = float(response_json.get("confidence", confidence))
        except Exception as e:
            # Fall back to the keyword result on any classification failure
            print(f"Error during intent classification: {e}")

    try:
        save_pattern(user_text, intent=intent, confidence=confidence)
    except Exception as e:
        print(f"Intent cache save failed: {e}")
    return intent, confidence
def get_ai_response(user_text):
    try:
        namer = "Tavily"
        today = datetime.now().strftime("%Y-%m-%d")
        time = datetime.now().strftime("%H:%M:%S")
        response = create_gemini_completion(
                    model="gemini-3.1-flash-lite",
                    messages=[
                        {"role": "system", "content": f"You are a helpful assistant,and your name is {namer},Current date is {today}, Current time is {time}."},
                        {"role": "user", "content": user_text}
                    ],
                    max_tokens=2048,
                    temperature=0.7
                )
        response_text = extract_message_content(response).strip()
        return response_text
    except Exception as e:
        return f"Error generating response: {str(e)}"
@socketio.on('voice_message')
def handle_voice(data):
    user_text = data.get('text', '')
    ai_response = get_ai_response(user_text)
    emit('ai_response', {'text': ai_response})
def text_to_speech_sync(text: str) -> bytes:
    tts = gTTS(text=text, lang='en')
    buf = io.BytesIO()
    tts.write_to_fp(buf)
    return buf.getvalue()
def smart_chat_history(history_text, recent=6):
    """Keep the last `recent` exchanges verbatim and squash older ones into one line.

    History is stored as text blocks separated by blank lines (one per exchange).
    """
    turns = [t for t in history_text.split("\n\n") if t.strip()]
    if len(turns) <= recent:
        return history_text

    old = turns[:-recent]
    recent_turns = turns[-recent:]
    summary = f"Earlier in conversation: {' | '.join(t[:50] for t in old)}"
    return summary + "\n" + "\n\n".join(recent_turns)

@app.route('/api/chat', methods=['POST'])
@require_auth
def chat():
    try:
        data = get_request_json()
        message = data.get("question", "").strip()
        if not message:
            return jsonify({"error": "Please provide a question."}), 400
        intent, confidence = intent_classifier(message)
        if intent == "calendar":
            return calendar_manage()

        # Weather check
        if "weather" in message.lower():
            weather = fetch_weather(city)
            if weather:
                return jsonify({"reply": f"The current weather in {weather['city']} is {weather['temperature']}°C with {weather['description']}."})
            return jsonify({"reply": "Sorry, I could not fetch the weather right now."})
        #prompt
        creatorname = "Godwin Alamu"
        history = smart_chat_history(read_chat_history())
        if history.count("User:") > 20:  # 20 exchanges
            return jsonify({"reply": "Your chat history is too long. Do you want to clear it (Y/N)?"})
        #tavily response
        fit_check = "if the user asks for outfit suggestion or fashion advice,check if the users sex,age,height,weight,skin tone is in the history if not ask the user for the details ."
        calevent = safe_get_calendar_events(data, request.user["uid"])
        # Latest CV review feedback, if one exists
        cv_info = None
        cv_info_json = os.path.join(CV_INFO_FILE, "review_Software_Engineer.json")
        if intent == "cv" and os.path.exists(cv_info_json):
            with open(cv_info_json, "r") as f:
                cv_info = json.load(f)
        today = datetime.now().strftime("%Y-%m-%d")
        time = datetime.now().strftime("%H:%M:%S")
        web_context = ""
        sources = []
        if intent == "web_search" or has_word(message.lower(), WEB_SEARCH_KEYWORDS):
            try:
                results = tavilyclient.search(query=message, max_results=5)
                items = results.get("results", []) if isinstance(results, dict) else results
                # Structured list for the frontend source chips…
                sources = [
                    {"title": r.get("title", "Untitled"), "url": r.get("url", "")}
                    for r in items[:5]
                ]
                # …and a numbered string for the prompt, so the model can cite [1], [2]
                web_context = "\n".join(
                    f"[{i}] {s['title']}: {s['url']}" for i, s in enumerate(sources, start=1)
                )
            except Exception as e:
                web_context = f"(Tavily search failed: {e})"
        source = f"Web search results:\n{web_context}" if web_context else "no web search results available."
        prompt = (
            f"""
            You are Godwin's personal AI assistant. You are sharp, intelligent, and adaptive — not just a coding assistant. Most conversations will be personal, practical, or conversational.

            Today is {today}, current time is {time}.

            Context available to you:
            - Web search results: {web_context if web_context else 'None'}
            - Calendar events: {calevent if calevent else 'None'}
            - Conversation history: {history if history else 'None'}
            - Current message: {message}
            Respond to this directly and specifically. Do not get distracted by context unless it
            How to behave:
            - Prioritise web context over your training knowledge for anything current
            - When you use a web result, cite it inline as [1], [2] matching the numbered list above
            - Primary rule: Always respond directly to the current message first.
                Use context only if it strengthens the response.
            - If it's casual, respond like a smart friend — no unnecessary structure
            - If it's technical, be precise and concise
            - If it's emotional or personal, be empathetic and grounded
            - For code, format it cleanly with a brief explanation
            - For CV questions, use the uploaded CV and give concrete specific feedback. Latest CV review: {cv_info if cv_info else 'none available — ask him to upload a CV first'}
            - For calendar, use the events provided and confirm when adding or deleting
            - In voice mode, respond in natural spoken sentences — no bullet points, no markdown
            - Be direct. Don't over-explain. Don't pad responses
            - Always respond in plain conversational language unless code or structure is specifically needed

            What you can handle:
            - Weather: suggest outfits based on conditions, from closet if available
            - Outfit: using {fit_check} suggest outfits based on conditions, from closet if available
            - Career: CV feedback, cover letters, interview prep
            - Learning: explain Python, React, DSA step by step, build study plans
            - Productivity: plan tasks, manage time, suggest routines
            - Personal: be empathetic and motivational when needed
            - Fun: jokes, trivia, light content when the mood calls for it
            - Web: search and provide relevant links when useful
            - Music: suggest songs or provide lyrics if asked
            - Calendar: fetch, add, delete Google Calendar events
            - Mac: you have access to Godwin's calendar, files, and Mac

            About Godwin:
            - Developer learning Python, React, and DSA
            - Targeting apprenticeships and junior roles
            - Built you — so he knows how you work

            You are built by {creatorname} and still evolving.
            """
        )
        # assistant name
        assistantname = data.get("assistantname", "").strip()
        namer = assistantname or "Ashen"
        system_msg = f"You are a helpful assistant named {namer}. Current date is {today}, current time is {time}."
        #choose model based on intent
        if intent == "calendar":
            # Anthropic takes the system prompt as a separate parameter, not a message
            response = create_anthropic_completion(
                model="claude-sonnet-4-6",
                system=system_msg,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2048,
                temperature=0.7
            )
        elif intent in ("weather", "web_search") or any(k in message.lower() for k in ["weather", "outfit", "logic", "jokes"]):
            response = create_gemini_completion(
                model="gemini-3.1-flash-lite",
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2048,
                temperature=0.7
            )
        else:
            response = create_chat_completion(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2048,
                temperature=0.7
            )
        reply = extract_message_content(response).strip()
        # Plain-text version for TTS so markdown/citation markers aren't read aloud
        speech_text = re.sub(r"\[\d+\]", "", reply)
        speech_text = re.sub(r"[*_#`]", "", speech_text)
         # Save chat to local file
        os.makedirs(CHAT_DIR, exist_ok=True)
        with open(CHAT_HISTORY_FILE, "a", encoding="utf-8") as f:
            f.write(f"User: {message}\nAssistant: {reply}\n Source: {source}\n Timestamp: {datetime.now().isoformat()}\n\n")
        try:
            audio_bytes = asyncio.run(text_to_speech_ws_streaming(
                    voice_id="JBFqnCBsd6RMkjVDRZzb",
                    model_id="eleven_flash_v2_5",
                    text=speech_text,
            ))
        except Exception:
            audio_bytes = text_to_speech_sync(speech_text)
        audio_b64 = base64.b64encode(audio_bytes).decode()
        return jsonify({
            "reply": reply,
            "sources": sources,
            "audio": audio_b64
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
def read_chat_history(n=10):
    if os.path.exists(CHAT_HISTORY_FILE):
        with open(CHAT_HISTORY_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        return "".join(lines[-(n * 2):])
    return ""
@app.route("/load_history", methods=["GET"])
@require_auth
def load_chat_history():
    return jsonify({"history": read_chat_history()})
@app.route("/clear", methods=["POST"])
@require_auth
def clear_chat():
    try:
        data = request.get_json()
        confirmation = data.get("confirmation", "").strip().lower()
        if confirmation == "yes":
            os.makedirs(CHAT_DIR, exist_ok=True)
            with open(CHAT_HISTORY_FILE, "w", encoding="utf-8") as f:
                f.write("")
            return jsonify({"reply": "Chat history cleared."})
        return jsonify({"reply": "Chat history not cleared."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500  
if __name__ == '__main__':
    if not os.path.exists(CHAT_DIR):
        os.makedirs(CHAT_DIR)
    #app.run(debug=True)
    socketio.run(app, debug=True, port=5000, use_reloader=False)
