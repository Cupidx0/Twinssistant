import os
from datetime import datetime

import requests
from dotenv import load_dotenv
from flask import Blueprint, request, jsonify

from Routing import create_chat_completion, extract_message_content
from auth_utils import require_auth
from holidays_util import get_current_label
from utils import get_request_json

weather_bp = Blueprint('weather', __name__)

load_dotenv()
api_key = os.getenv("OPENWEATHER_API_KEY")
city = "horley"


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

@weather_bp.route('/weather', methods=['POST'])
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
@weather_bp.route('/outfit',methods=['POST'])
@require_auth
def outfit():
    try:
        data = request.get_json()
        message = data.get("fit", "").strip()
        user_time = datetime.now()
        user_info ={
            "city": "horley",
            "height": 5.11 or "",
            "weight": 70 or "",
            "skin_tone": "black" or "",
            "sex": "male" or "",
            "body_type": "lean_athletic" or "",
            "age": 21 or "",
        }
        weather = fetch_weather(user_info["city"])
        if not message:
            return jsonify({"error": "Please provide a question."}), 400
        prompt =(
                  f"User request: {message}\n Suggest outfit for user based on the weather and the {user_time} time."
                  "based on if its morning ,afternoon and night.\n"
                  f"use the {weather} to decide which outfit to recommend to the user and also for the {user_info['city']}location.\n"
                  f"personalize the outfit based on the user info: {user_info}."
                  "think creatively and provide a unique outfit idea for the user based on the weather and the time of day and current fashion trends.\n"
                  "output the weather info to the user before the outfit idea. \n"
                  "start with a friendly greeting and confirm actions."
                   )
        System_prompt = "You are a smart assistant that manages Fashion closet. Always try to provide relevant outfit to the user based on the weather whilst keeping your word length at a minimum."
        response = create_chat_completion(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": System_prompt},
                {"role": "user", "content":prompt}
            ],
            max_tokens=180,
            temperature=0.7
        )
        outgen = extract_message_content(response).strip()
        return jsonify({'outgen':outgen})
    except Exception as e:
        return jsonify({"error":str(e)}),500
@weather_bp.route('/holiday_season', methods=['POST'])
def holiday_season():
    try:
        current_date = datetime.now().date()
        dreply = get_current_label(current_date)
        return jsonify({"dreply": dreply})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
