from pickle import GET
from flask import Flask, request, jsonify, session
from flask_cors import CORS
import openai
import os
import os.path
from dotenv import load_dotenv
from firebase_admin import credentials, firestore, initialize_app   
import requests
import cv2
from dateutil import parser
import dateparser
import pdfplumber
from docx import Document
from tavily import TavilyClient
from datetime import datetime, timedelta
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from werkzeug.utils import secure_filename
import json

try:
    import holidays as holidays_lib
except ImportError:
    holidays_lib = None

# Load env variables
load_dotenv()
api_key = os.getenv("OPENWEATHER_API_KEY")
city = "horley"
tavilyclient = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
openai.api_key = os.getenv("OPENAI_API_KEY")
SCOPES = ["https://www.googleapis.com/auth/calendar"]
# Initialize Firebase properly
cred = credentials.Certificate("tw.json")  # 👈 your Firebase service account JSON
firebase_app = initialize_app(cred)
db = firestore.client()

# Flask app
app = Flask(__name__)
CORS(app, supports_credentials=True, origins=["http://localhost:5173"])

@app.route('/')
def home():
    return "Welcome to the Assistant API!"
def get_tavily_results(query, num_results=5):
    """Helper to fetch Tavily search results."""
    try:
        results = tavilyclient.search(query=query, max_results=num_results)
        return results.get("results", [])
    except Exception as e:
        return [{"title": "Error", "url": "", "content": str(e)}]
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
    if not os.path.exists("token.json"):
        raise FileNotFoundError("token.json not found. Run login_calendar.py first.")
    creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if creds and not creds.valid and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return creds

def get_request_json():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}

def safe_get_calendar_events(data):
    try:
        user_id = data.get("userId")
        max_results = data.get("maxResults", 5)
        return get_calendar_events(user_id=user_id, maxResults=max_results)
    except Exception as e:
        return {"error": str(e)}

def create_chat_completion(model, messages, functions=None, function_call=None, **kwargs):
    if hasattr(openai, "ChatCompletion"):
        payload = {"model": model, "messages": messages, **kwargs}
        if functions is not None:
            payload["functions"] = functions
        if function_call is not None:
            payload["function_call"] = function_call
        return openai.ChatCompletion.create(**payload)
    if hasattr(openai, "OpenAI"):
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        if functions is not None:
            tools = [{"type": "function", "function": fn} for fn in functions]
            tool_choice = "auto" if function_call in (None, "auto") else {"type": "function", "function": {"name": function_call}}
            return client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools,
                tool_choice=tool_choice,
                **kwargs
            )
        return client.chat.completions.create(model=model, messages=messages, **kwargs)
    raise RuntimeError("OpenAI client is not available.")

def extract_message_content(response):
    try:
        return response["choices"][0]["message"]["content"]
    except TypeError:
        return response.choices[0].message.content

def extract_function_call(message):
    if isinstance(message, dict):
        return message.get("function_call")
    tool_calls = getattr(message, "tool_calls", None)
    if tool_calls:
        tool = tool_calls[0]
        return {"name": tool.function.name, "arguments": tool.function.arguments}
    return None

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
def calendar():
    try:
        creds = get_creds()
        service = build("calendar", "v3", credentials=creds)
        today = datetime.utcnow().date()
        now = str(today) + "T00:00:00Z"
        events_result = service.events().list(
            calendarId="alamugodwin@gmail.com",
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
    created_event = service.events().insert(calendarId="alamugodwin@gmail.com", body=event).execute()
    #return f"Event created: {created_event.get('htmlLink')}"
    return created_event


@app.route('/calendar/add', methods=['POST'])
def calendar_add():
    try:
        data = request.get_json()
        summary = data.get("summary")
        end_time = data.get("end")  # ISO 8601 string
        user_id = data.get("userId","default_user")
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
        calendarId="alamugodwin@gmail.com",  # or dynamic if needed
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
print(get_calendar_events)
@app.route("/calendar/get", methods=["POST"])
def fetch_calendar_events():
    try:
        data = get_request_json()
        events = safe_get_calendar_events(data)
        return jsonify({"events":events})  
    except Exception as e:
        return jsonify({"error": str(e)}), 500  


@app.route('/calendar/delete', methods=['DELETE'])
def calendar_delete():
    try:
        data = request.get_json()
        event_id = data.get("eventId")
        user_id = data.get("userId")

        if not event_id:
            return jsonify({"error": "eventId is required"}), 400

        # 🔹 Delete from Google Calendar
        creds = get_creds()
        service = build("calendar", "v3", credentials=creds)
        service.events().delete(
            calendarId="alamugodwin@gmail.com",
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
def calendar_manage():
    try:
        data = get_request_json()
        message = data.get("question", "").strip()
        calevent = safe_get_calendar_events(data)
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
                events = fetch_calendar_events()
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
def extract_text_from_pdf(file_path):
    try:
        with pdfplumber.open(file_path) as pdf:
            text = "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())
        return text
    except Exception as e:
        return f"Error extracting PDF: {str(e)}"
def extract_text_from_docx(file_path):
    try:
        doc = Document(file_path)
        text = "\n".join(paragraph.text for paragraph in doc.paragraphs)
        return text
    except Exception as e:
        return f"Error extracting DOCX: {str(e)}"
@app.route('/convertText', methods=['POST'])
def convert_file_to_text():
    path = os.path.join(os.getcwd(), "Cv_docs")
    os.makedirs(path, exist_ok=True)
    try:
       # data = get_request_json()
        file = request.files.get("file")
        filename = secure_filename(file.filename)
        file.save(filename)

        if filename.endswith('.pdf'):
            text = extract_text_from_pdf(filename)
        elif filename.endswith(('.docx', '.doc')):
            text = extract_text_from_docx(filename)
        else:
            return jsonify({"error": "Unsupported file type"}), 400

        os.remove(filename)
        new_filename = filename.rsplit('.', 1)[0]
        with open(f"{path}/{new_filename}.txt", "w", encoding="utf-8") as f:
            f.write(text)
        return jsonify({"text":'successfully extracted text from file',
                        "cv":f"{path}/{new_filename}.txt"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
def review_cv():
    cv = os.path.join(os.getcwd(), "Cv_docs")
    compare =["name","experience","skills","education","projects","contact"]
    try:
        with open(cv, "r", encoding="utf-8") as f:
            text = f.read()
        feedback = []
        for item in compare:
            if item in text.lower():
                items = item +1
                feedback.append(items)
        if feedback < 3:
            gpt_get = "Your CV is missing key sections. Consider adding: " + ", ".join(set(compare) - set(feedback))
            return jsonify({"feedback": gpt_get})
        return jsonify({"feedback": "Your CV looks good! It contains the essential sections."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
@app.route('/weather', methods=['POST'])
def getWeather():
    try:
        data = request.get_json()
        city = data.get("location", "London")  # ✅ get city from frontend, fallback to London

        url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric"
        weather_data = requests.get(url).json()

        if weather_data.get("main"):
            temp = weather_data["main"]["temp"]
            desc = weather_data["weather"][0]["description"]

            # ✅ return structured JSON instead of a single string
            return jsonify({
                "weather": {
                    "city": city,
                    "temperature": temp,
                    "description": desc
                }
            })

        return jsonify({"error": "Sorry, I could not fetch the weather right now."}), 404

    except Exception as e:
        return jsonify({"error": str(e)}), 500
@app.route('/outfit',methods=['POST'])
def outfit():
    try:
        data = request.get_json()
        message = data.get("fit", "").strip()
        user_time = datetime.now()
        city = "Horley"
        weather = getWeather()
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
@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = get_request_json()
        message = data.get("question", "").strip()
        if not message:
            return jsonify({"error": "Please provide a question."}), 400
        cv_check = review_cv()
        if cv_check:
            review = cv_check.get("feedback")
        # Weather check
        if "weather" in message.lower():
            url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric"
            weather_data = requests.get(url).json()
            if weather_data.get("main"):
                temp = weather_data["main"]["temp"]
                desc = weather_data["weather"][0]["description"]
                return jsonify({"reply": f"The current weather in {city} is {temp}°C with {desc}."})
            return jsonify({"reply": "Sorry, I could not fetch the weather right now."})
        #prompt
        creatorname = "Godwin Alamu"
        if not creatorname:
            return jsonify({"reply":"hello designated user"})
        history = load_chat_history()
        if history.count("User:") > 20:  # 20 exchanges
            return jsonify({"reply": "Your chat history is too long. Do you want to clear it (Y/N)?"})
        #tavily response
        calevent = safe_get_calendar_events(data)
        # Tavily search trigger
        today = datetime.now().strftime("%Y-%m-%d")
        time = datetime.now().strftime("%H:%M:%S")
        web_context = ""
        if any(word in message.lower() for word in ["latest", "news", "search", "youtube", "today","current","year",
                                                    "music","song","songs","weather","sports","football","cricket","president",
                                                    "prime minister","capital of","country","countries","who is","what is",
                                                    "when is","where is","how to","define"]):
            try:
                results = tavilyclient.search(query=message, max_results=5)
                items = results.get("results", []) if isinstance(results, dict) else results
                if items:
                    # Build web context string
                    web_context = "\n".join(
                        [f"{r.get('title', 'No title')}: {r.get('url','')}" for r in items]
                    )
            except Exception as e:
                web_context = f"(Tavily search failed: {e})"
        prompt = (
            f"Web context: {web_context}\n"
            f"User request: {message}\n"
            "use web context if provided - it overrides your pre-trained knowledge.\n"
            "Do not mention your training data or knowledge cut-off,instead use search results for fresh info.\n"
            f"verify your information with web context before answering.\n"
            f"use {calevent} to fetch events from calendar and add events with add_calendar_event.\n"
            f"use past chat history from {history} for context if it relates to user request.\n"
            "You are the user's personal AI Digital Twin assistant. "
            "Be concise, practical, and supportive. "
            "You handle:\n"
            "- Weather → suggest outfits from closet (if available) or general weather-appropriate ideas.\n"
            "- Career → help with CV/cover letters, interview prep, coding guidance.\n"
            "- Learning → explain coding/DSA step by step, generate study plans.\n"
            "- Productivity → plan tasks, manage time, suggest routines.\n"
            "- Personal → be empathetic, motivational, and supportive.\n"
            "- Fun → share jokes, trivia, light-hearted content.\n"
            "- Calendar → manage Google Calendar events (add, fetch, delete).\n"
            "- Scrape the internet for and provide links for the user if needed.\n"
            "- Sing → provide lyrics or sing a few lines and also suggest a song.\n"
            f"I am still a prototype created by {creatorname}, and i am still in development, so I may not be able to answer all questions perfectly,"
            " but I will do my best to assist you.\n"
            "\n"
            "Rules:\n"
            "- When giving code, format it cleanly and explain briefly.\n"
            "- Use simple language, avoid jargon.\n"
            "- Be friendly and approachable.\n"
            "- Verify your information with web context before answering.\n"
            "- Do not just use your pre-trained knowledge cut-off of 2023 to answer, always check the web context.\n"
            f"- Use {web_context} for real-time info.\n"
            "- Suggest helpful links or resources if relevant (but keep it simple).\n"
            "- Remember: the user is a developer learning Python, React, and DSA for apprenticeships.\n"
            "- Always end with a follow-up question to keep the conversation going.\n"
            f"if user ask you to review their CV, use this {review} to provide feedback on their CV and suggest improvements."
        )
        # assistant name
        assistantname = data.get("assistantname", "").strip()
        namer = f"{assistantname}" or "Ashen"
        # Otherwise ask OpenAI
        response = create_chat_completion(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": f"You are a helpful assistant,and your name is {namer},Current date is {today}, Current time is {time}."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=180,
            temperature=0.7
        )
        reply = extract_message_content(response).strip()
        if "*" in reply:
            reply = reply.replace("*", "")
         # Save chat to local file
        with open("chat/chat_history.txt", "a") as f:
            f.write(f"User: {message}\nAssistant: {reply}\nTimestamp: {datetime.now().isoformat()}\n\n")
        return jsonify({"reply": reply})

    except Exception as e:
        return jsonify({"error": str(e)}), 500
@app.route("/load_history", methods=["GET"])
def load_chat_history(n=10):
    if os.path.exists("chat/chat_history.txt"):
        with open("chat/chat_history.txt", "r", encoding="utf-8") as f:
            lines = f.readlines()
        convo = "".join(lines[-(n*2):])
        return convo 
    return ""
@app.route("/clear", methods=["POST"])
def clear_chat():
    try:
        data = request.get_json()
        confirmation = data.get("confirmation", "").strip().lower()
        if confirmation == "yes":
            with open("chat/chat_history.txt", "w", encoding="utf-8") as f:
                f.write("")
            return jsonify({"reply": "Chat history cleared."})
        return jsonify({"reply": "Chat history not cleared."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500  
if __name__ == '__main__':
    if not os.path.exists("chat"):
        os.makedirs("chat")
    app.run(debug=True)
