# config.py

import os
from typing import List, Dict, Any, Tuple

# ==============================================================================
# --- PROJECT & UI CONFIGURATION ---
# ==============================================================================
PROJECT_NAME: str = "Krishinetra"
LOG_LEVEL: str = "INFO"

# ==============================================================================
# --- FILE SYSTEM & DATABASE PATHS ---
# ==============================================================================
PROJECT_ROOT: str = os.path.dirname(os.path.abspath(__file__))
DATA_PATH: str = os.path.join(PROJECT_ROOT, "data")
LOG_PATH: str = os.path.join(DATA_PATH, "logs")
CAPTURED_IMAGES_DATA_PATH: str = os.path.join(PROJECT_ROOT, "web_interface", "static", "captured_images")
DATABASE_PATH: str = os.path.join(DATA_PATH, "mission_log.db")

LOG_FILE_PATH: str = os.path.join(LOG_PATH, "robot.log")
ERROR_LOG_FILE_PATH: str = os.path.join(LOG_PATH, "error.log")

# ==============================================================================
# --- SERIAL COMMUNICATION WITH ARDUINOS ---
# ==============================================================================
UNO_SERIAL_PORT: str = '/dev/arduinoUNO'
NANO_SERIAL_PORT: str = '/dev/arduinoNANO'
SERIAL_BAUD_RATE: int = 115200
SERIAL_CONNECT_TIMEOUT_S: float = 3.0

# ==============================================================================
# --- INFERENCE & AI MODELS ---
# ==============================================================================
MODEL_WEIGHTS_PATH: str = os.path.join(PROJECT_ROOT, "inference", "weights")
STRESS_DETECTOR_MODEL_PATH: str = os.path.join(MODEL_WEIGHTS_PATH, "stress_detector.onnx")
INFERENCE_CONFIDENCE_THRESHOLD: float = 0.55
STRESS_MODEL_INPUT_SIZE: Tuple[int, int] = (448, 448)

STRESS_CLASS_NAMES: List[str] = [
    "Fungal_Blight", "Rust_Mildew", "Bacterial_Blight_Spot", "Viral_Curl_Mosaic",
    "Pest_Damage", "Wilt_Rot", "Nutrient_Deficiency", "Discoloration_Stress",
    "Leaf_Spot", "Physiological_Stress", "Rust_Scab_Rot", "Healthy"
]

# ==============================================================================
# --- NAVIGATION & MOVEMENT ---
# ==============================================================================
AUTONOMOUS_MOVE_SPEED: int = 210
MANUAL_DEFAULT_SPEED: int = 200
MANUAL_TURN_SPEED: int = 180
WHEEL_CIRCUMFERENCE_CM: float = 22.0
ENCODER_PULSES_PER_ROTATION: int = 20
SIDE_US_END_OF_ROW_THRESHOLD_CM: float = 30.0
NO_DETECTION_END_OF_ROW_CONSECUTIVE: int = 3

# ==============================================================================
# --- TREATMENT, SPRAYING & PUMPS ---
# ==============================================================================
ML_PER_SECOND: float = 5.0
HIGH_HUMIDITY_THRESHOLD: int = 85
HIGH_TEMP_THRESHOLD: float = 35.0

TANK_MAP: Dict[int, str] = {
    1: "Pesticide 1",
    2: "Pesticide 2",
    3: "Water",
}

PESTICIDE_GROUP_1: Dict[str, Any] = {"name": "Fungal Disease Control", "tank": 1, "targets": ["Fungal_Blight", "Rust_Mildew", "Leaf_Spot", "Rust_Scab_Rot"]}
PESTICIDE_GROUP_2: Dict[str, Any] = {"name": "Bacterial & Pest Control", "tank": 2, "targets": ["Bacterial_Blight_Spot", "Viral_Curl_Mosaic", "Pest_Damage", "Wilt_Rot"]}
FERTILIZER_GROUP: Dict[str, Any] = {"name": "Nutrient & Growth Support", "tank": 3, "targets": ["Nutrient_Deficiency", "Discoloration_Stress", "Physiological_Stress"]}
TREATMENT_GROUPS: List[Dict] = [PESTICIDE_GROUP_1, PESTICIDE_GROUP_2, FERTILIZER_GROUP]
HEALTHY_CLASSES: List[str] = ["Healthy"]

DISEASE_COLOR_MAP: Dict[str, str] = {
    "Healthy": "#4CAF50", "Fungal_Blight": "#E53935", "Rust_Mildew": "#EF5350",
    "Leaf_Spot": "#F44336", "Rust_Scab_Rot": "#D32F2F", "Pest_Damage": "#FDD835",
    "Bacterial_Blight_Spot": "#FFC107", "Viral_Curl_Mosaic": "#8E24AA", "Wilt_Rot": "#9C27B0",
    "Nutrient_Deficiency": "#1E88E5", "Discoloration_Stress": "#2196F3", "Physiological_Stress": "#42A5F5",
    "Default": "#9E9E9E",
}

# ==============================================================================
# --- WEB INTERFACE & SECURITY ---
# ==============================================================================
WEB_SERVER_HOST: str = "0.0.0.0"
WEB_SERVER_PORT: int = 5000
WEB_INTERFACE_PASSWORD: str = os.environ.get("ROBOT_PASSWORD", "krishinetra123")
WEB_ALLOWED_COMMANDS: List[str] = [
    "save_mission", "start_mission", "stop_mission", "pause", "resume",
    "emergency_stop", "set_manual_mode", "go_to_wizard",
]

# ==============================================================================
# --- ROBOT BEHAVIOR & STATE MACHINE ---
# ==============================================================================
CAMERA_ANGLES: Dict[str, int] = {
    "pan_straight": 90,
    "pan_left": 150,
    "tilt_top": 75,
    "tilt_middle": 90,
    "tilt_bottom": 120,
}
CAMERA_SETTLE_TIME_S: float = 0.5
YOLO_PRE_PROCESSING_DELAY_S: float = 1.0
YOLO_POST_PROCESSING_DELAY_S: float = 1.5

def validate_paths() -> None:
    for path in [LOG_PATH, CAPTURED_IMAGES_DATA_PATH]:
        os.makedirs(path, exist_ok=True)

validate_paths()
