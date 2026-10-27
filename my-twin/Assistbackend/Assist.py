import os

from flask import Flask
from flask_cors import CORS

from extensions import socketio
from cv_route import cv_bp
from calendar_route import calendar_bp
from weather_route import weather_bp
from chat_core import chat_bp, CHAT_DIR

# Flask app
app = Flask(__name__)
app.register_blueprint(cv_bp)
app.register_blueprint(calendar_bp)
app.register_blueprint(weather_bp)
app.register_blueprint(chat_bp)
CORS(app, supports_credentials=True, origins=["http://localhost:5174"])
socketio.init_app(app, cors_allowed_origins="http://localhost:5174", async_mode='threading',engineio_logger=True, logger=True)
import socket_handlers  # noqa: E402,F401 — registers the @socketio.on handlers

@app.route('/')
def home():
    return "Welcome to the Assistant API!"

if __name__ == '__main__':
    if not os.path.exists(CHAT_DIR):
        os.makedirs(CHAT_DIR)
    #app.run(debug=True)
    socketio.run(app, debug=True, port=5050, use_reloader=False)
