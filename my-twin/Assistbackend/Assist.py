import os

from flask import Flask
from flask_cors import CORS

from extensions import socketio
from cv_route import cv_bp
from calendar_route import calendar_bp
from weather_route import weather_bp
from chat_core import chat_bp, CHAT_DIR
from costs import costs_bp
from uploads import uploads_bp, MAX_BYTES
from artifacts import artifacts_bp
from memory_route import memory_bp
from studio_route import studio_bp

# Flask app
app = Flask(__name__)
app.register_blueprint(cv_bp)
app.register_blueprint(calendar_bp)
app.register_blueprint(weather_bp)
app.register_blueprint(chat_bp)
for bp in (costs_bp, uploads_bp, artifacts_bp, memory_bp, studio_bp):
    app.register_blueprint(bp)
app.config["MAX_CONTENT_LENGTH"] = MAX_BYTES + 1024 * 1024  # uploads are capped at 20 MB
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
