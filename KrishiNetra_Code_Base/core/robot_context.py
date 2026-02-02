# core/robot_context.py

import threading
from enum import Enum, auto
import numpy as np
from typing import Optional, Dict, Any, List
import datetime
import config

class RobotState(Enum):
    """Enumeration for the Krishinetra robot's mission-based states."""
    OFF = auto()
    STARTUP = auto()
    IDLE = auto()
    MISSION_SETUP = auto()
    MISSION_AWAITING_START = auto()
    EXECUTING_ROW = auto()
    ANALYZING = auto()
    TREATING = auto()
    MANUAL_CONTROL = auto()
    PAUSED = auto()
    ERROR = auto()
    SHUTDOWN = auto()

class RobotContext:
    """A thread-safe class that holds the complete state of the Krishinetra robot."""

    def __init__(self):
        self._lock = threading.RLock()

        # --- Core State Machine ---
        self._current_state: RobotState = RobotState.OFF
        self._is_running: bool = False
        self._is_paused: bool = False
        self._previous_state_before_pause: RobotState = RobotState.IDLE

        # --- Mission Management ---
        self._mission_id: Optional[str] = None
        self._mission_plan: Dict[str, Any] = {}
        self._mission_progress: Dict[str, Any] = {}
        self._mission_message: str = "Welcome to KrishiNetra! Please start a new mission."

        # --- Live Session Data for Dashboard ---
        self._session_detection_tally: Dict[str, int] = {}
        self._session_plant_log: List[Dict[str, Any]] = []
        self._latest_scan_images: Dict[str, Optional[np.ndarray]] = {
            "top": None,
            "middle": None,
            "bottom": None,
        }

        # --- Hardware & Sensor Data ---
        self._last_sensor_data: Dict[str, Any] = {
            "F": 0, "S": 0, "E": 0, "T": 0.0, "H": 0.0,
        }

        # --- Manual Control & Web Commands ---
        self._manual_command: Dict[str, Any] = {}
        self._web_command: Optional[Dict] = None
        self._emergency_stop_activated: bool = False

    def _sanitize_for_json(self, data: Any) -> Any:
        if isinstance(data, dict):
            return {k: self._sanitize_for_json(v) for k, v in data.items()}
        if isinstance(data, list):
            return [self._sanitize_for_json(i) for i in data]
        if isinstance(data, np.integer):
            return int(data)
        if isinstance(data, np.floating):
            return float(data)
        return data

    def get_all_data_for_ui(self) -> Dict[str, Any]:
        with self._lock:
            ui_data = {
                "server_status": "connected",
                "robot_status": self._current_state.name,
                "is_paused": self._is_paused,
                "mission_id": self._mission_id,
                "mission_plan": self._mission_plan.copy(),
                "mission_progress": self._mission_progress.copy(),
                "last_sensor_data": self._last_sensor_data.copy(),
                "mission_message": self._mission_message,
                "session_tally": self._session_detection_tally.copy(),
                "plant_log": self._session_plant_log.copy(),
            }
            return self._sanitize_for_json(ui_data)

    def save_mission_plan(self, plan: Dict[str, Any]):
        """Saves a new mission plan, generates an ID, and resets session data."""
        now = datetime.datetime.now()
        with self._lock:
            self._mission_plan = plan
            mission_num_today = (now - now.replace(hour=0, minute=0, second=0, microsecond=0)).seconds
            self._mission_id = f"KR-MSN-{now.strftime('%Y-%m-%d')}-{mission_num_today:04d}"

            self._mission_progress = {
                "current_row_index": 0,
                "current_plant_index": 0,
                "total_distance_in_row_cm": 0.0,
                "start_time": now.isoformat(),
                "plants_treated": 0,
                "consecutive_empty_scans": 0,
            }

            self._session_detection_tally = {}
            self._session_plant_log = []
            self._latest_scan_images = {"top": None, "middle": None, "bottom": None}
            
            self._mission_message = "Mission plan saved. Ready to start."
            self._current_state = RobotState.MISSION_AWAITING_START

    def get_mission_id(self) -> Optional[str]:
        with self._lock:
            return self._mission_id

    def update_mission_progress(self, **kwargs):
        with self._lock:
            self._mission_progress.update(kwargs)

    def log_plant_analysis(self, plant_log_entry: Dict[str, Any]):
        with self._lock:
            self._session_plant_log.insert(0, plant_log_entry)
            for class_name in plant_log_entry.get("detected_diseases", []):
                self._session_detection_tally[class_name] = self._session_detection_tally.get(class_name, 0) + 1
            if plant_log_entry.get("treatment_applied") != "None":
                self._mission_progress["plants_treated"] = self._mission_progress.get("plants_treated", 0) + 1

    def clear_mission_plan(self):
        with self._lock:
            self._mission_id = None
            self._mission_plan = {}
            self._mission_progress = {}
            self._mission_message = "Start a new mission."
            self._session_detection_tally = {}
            self._session_plant_log = []

    def get_state(self) -> RobotState:
        with self._lock:
            return self._current_state

    def set_state(self, new_state: RobotState):
        with self._lock:
            if self._current_state != new_state:
                self._current_state = new_state

    def set_pause_state(self, pause: bool):
        with self._lock:
            if pause and not self._is_paused:
                self._is_paused = True
                self._previous_state_before_pause = self._current_state
                self._current_state = RobotState.PAUSED
            elif not pause and self._is_paused:
                self._is_paused = False
                self._current_state = self._previous_state_before_pause

    def is_running(self) -> bool:
        with self._lock:
            return self._is_running

    def set_running(self, running: bool):
        with self._lock:
            self._is_running = running

    def update_scan_image(self, angle: str, frame: np.ndarray):
        with self._lock:
            if angle in self._latest_scan_images:
                self._latest_scan_images[angle] = frame.copy()

    def get_scan_image(self, angle: str) -> Optional[np.ndarray]:
        with self._lock:
            return self._latest_scan_images.get(angle)

    def update_sensor_data(self, source: str, data: Dict[str, Any]):
        with self._lock:
            if data:
                self._last_sensor_data.update(data)

    def get_sensor_data(self) -> Dict[str, Any]:
        with self._lock:
            return self._last_sensor_data.copy()

    def set_mission_message(self, message: str):
        with self._lock:
            self._mission_message = message

    def set_manual_command(self, command: Dict):
        with self._lock:
            self._manual_command = command

    def get_manual_command(self) -> Dict:
        with self._lock:
            cmd = self._manual_command
            self._manual_command = {}
            return cmd

    def set_web_command(self, command: str, payload: Optional[Dict] = None):
        with self._lock:
            self._web_command = {"command": command, "payload": payload or {}}
            if command == "emergency_stop":
                self._emergency_stop_activated = True
                self._is_running = False

    def get_web_command(self) -> Optional[Dict]:
        with self._lock:
            command_obj = self._web_command
            self._web_command = None
            return command_obj
        

