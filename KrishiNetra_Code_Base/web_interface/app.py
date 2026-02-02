# web_interface/app.py

import logging
import cv2
import sys
import os
import numpy as np
import threading

from flask import Flask, Response, render_template, request, jsonify, send_from_directory
from flask_apscheduler import APScheduler

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import config
from web_interface.auth import requires_auth
from core.robot_context import RobotContext, RobotState
from services import database_manager as db
from core.robot_controller import RobotController

logger = logging.getLogger(__name__)

robot_controller_instance: RobotController = None


def create_app(robot_controller: RobotController):
    global robot_controller_instance
    robot_controller_instance = robot_controller

    app = Flask(__name__)
    app.config["robot_context"] = robot_controller.context

    # Scheduler
    scheduler = APScheduler()
    scheduler.init_app(app)
    scheduler.start()

    @scheduler.task("interval", id="poll_sensors_task", seconds=2, misfire_grace_time=900)
    def poll_sensors():
        """Non-blocking polling thread"""
        def _poll():
            try:
                if robot_controller_instance and robot_controller_instance.is_initialized:
                    uno = robot_controller_instance.uno_comm.get_sensors()
                    if uno:
                        robot_controller_instance.context.update_sensor_data("uno", uno)

                    nano = robot_controller_instance.nano_comm.get_sensors()
                    if nano:
                        robot_controller_instance.context.update_sensor_data("nano", nano)

            except Exception as e:
                logger.error(f"Sensor polling thread error: {e}")

        threading.Thread(target=_poll).start()

    # ROUTES
    @app.route("/")
    @requires_auth
    def index():
        return render_template("index.html")

    @app.route("/captured_images/<path:filename>")
    @requires_auth
    def get_captured_image(filename):
        return send_from_directory(config.CAPTURED_IMAGES_DATA_PATH, filename)

    @app.route("/api/status")
    @requires_auth
    def api_status():
        return jsonify(app.config["robot_context"].get_all_data_for_ui())

    @app.route("/api/scan_image/<string:angle>")
    @requires_auth
    def api_scan_image(angle: str):
        if angle not in ["top", "middle", "bottom"]:
            return "Invalid angle", 404

        frame = app.config["robot_context"].get_scan_image(angle)

        if frame is None:
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(frame, "Awaiting Scan",
                        (200, 240), cv2.FONT_HERSHEY_SIMPLEX, 1,
                        (255, 255, 255), 2)

        ok, encoded = cv2.imencode(".jpg", frame)
        if not ok:
            return "Encoding error", 500

        return Response(encoded.tobytes(), mimetype="image/jpeg")

    @app.route("/api/command", methods=["POST"])
    @requires_auth
    def api_command():
        data = request.get_json()
        cmd = data.get("command")
        payload = data.get("payload")

        if cmd in config.WEB_ALLOWED_COMMANDS:
            app.config["robot_context"].set_web_command(cmd, payload=payload)
            return jsonify({"status": "success"})

        return jsonify({"status": "error", "message": "Invalid command"}), 400

    @app.route("/api/manual_control", methods=["POST"])
    @requires_auth
    def api_manual_control():
        ctx: RobotContext = app.config["robot_context"]

        if ctx.get_state() == RobotState.MANUAL_CONTROL:
            ctx.set_manual_command(request.get_json())
            return jsonify({"status": "success"})

        return jsonify({"status": "error", "message": "Robot not in manual mode"}), 403

    @app.route("/api/previous_session_analytics")
    @requires_auth
    def api_prev():
        ctx: RobotContext = app.config["robot_context"]
        robot_state = ctx.get_state()
        current_mission_id = ctx.get_mission_id()
        
        exclude_id = current_mission_id if robot_state in [RobotState.EXECUTING_ROW, RobotState.PAUSED, RobotState.ANALYZING] else None

        prev_id = db.get_latest_mission_id(exclude_id=exclude_id)

        if not prev_id:
            return jsonify({"error": "No previous session data found"}), 404

        data = db.get_previous_session_analytics(prev_id)
        
        if not data or not data.get("header_stats"):
            return jsonify({"error": "Could not retrieve analytics for the session"}), 404

        data["mission_id"] = prev_id
        return jsonify(data)

    @app.route("/api/overall_analytics")
    @requires_auth
    def api_all():
        return jsonify(db.get_overall_analytics())

    return app


