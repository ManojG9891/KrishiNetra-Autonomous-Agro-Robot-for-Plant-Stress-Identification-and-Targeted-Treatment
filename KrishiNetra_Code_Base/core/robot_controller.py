# core/robot_controller.py

import logging
import time
import sys
import os
import cv2
import datetime
from typing import Dict, Any, Optional, List
from collections import Counter
import numpy as np

# Add project root to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import config
from core.robot_context import RobotContext, RobotState
from services.arduino_communicator import ArduinoCommunicator
from hardware.camera_manager import CameraManager
from inference.stress_detector import StressDetector
from services.treatment_planner import TreatmentPlanner
from services import database_manager as db

logger = logging.getLogger(__name__)

class RobotController:
    """The main orchestrator of the Krishinetra robot, with snapshot-based analysis and detailed status feedback."""

    def __init__(self) -> None:
        logger.info(f"Initializing {config.PROJECT_NAME} Controller...")
        self.context = RobotContext()
        self.uno_comm = ArduinoCommunicator(
            config.UNO_SERIAL_PORT, config.SERIAL_BAUD_RATE, name="Uno"
        )
        self.nano_comm = ArduinoCommunicator(
            config.NANO_SERIAL_PORT, config.SERIAL_BAUD_RATE, name="Nano"
        )
        self.camera = CameraManager()
        self.stress_detector = StressDetector()
        self.treatment_planner = TreatmentPlanner()
        self.is_initialized = self._verify_initialization()

    def _verify_initialization(self) -> bool:
        db.init_db()
        critical_modules = {
            "Uno(Motion/Sensors)": self.uno_comm.connect(),
            "Nano(Tools/UI)": self.nano_comm.connect(),
            "Camera": self.camera.is_operational,
            "StressDetector": self.stress_detector.is_initialized,
        }
        all_ok = all(critical_modules.values())
        if not all_ok:
            logger.critical("CRITICAL: One or more modules failed to initialize.")
        return all_ok

    def startup(self) -> None:
        if not self.is_initialized:
            return
        self.context.set_state(RobotState.STARTUP)
        self.camera.start()
        self.context.set_running(True)
        time.sleep(1)
        self.context.set_state(RobotState.IDLE)
        logger.info("Krishinetra startup complete. Now in IDLE state.")

    def shutdown(self) -> None:
        logger.info("Shutdown sequence initiated...")
        self.context.set_running(False)
        self.context.set_state(RobotState.SHUTDOWN)

        if self.uno_comm.is_connected:
            self.uno_comm.send_command("STOP", expect_ack=False)

        if self.nano_comm.is_connected:
            self.nano_comm.send_command(
                f"PAN:{config.CAMERA_ANGLES['pan_straight']}", expect_ack=False
            )
            self.nano_comm.send_command(
                f"TILT:{config.CAMERA_ANGLES['tilt_middle']}", expect_ack=False
            )
            self.nano_comm.send_command("INDICATE:error", expect_ack=False)

        self.camera.shutdown()
        self.uno_comm.disconnect()
        self.nano_comm.disconnect()
        logger.info("Krishinetra shutdown complete.")

    def run(self) -> None:
        if not self.is_initialized:
            return
        self.startup()
        try:
            while self.context.is_running():
                try:
                    self._handle_web_commands()
                    current_state = self.context.get_state()
                    action = self.state_action_map.get(current_state)
                    if action:
                        action()
                except Exception as loop_err:
                    logger.critical(
                        f"Unhandled exception in control loop iteration: {loop_err}",
                        exc_info=True,
                    )
                    self._handle_error("Internal controller error occurred. Check logs.")
                time.sleep(0.1)
        except (KeyboardInterrupt, SystemExit):
            logger.info("Termination signal received. Shutting down.")
        finally:
            self.shutdown()

    @property
    def state_action_map(self):
        return {
            RobotState.IDLE: self._wait,
            RobotState.MISSION_SETUP: self._wait,
            RobotState.MISSION_AWAITING_START: self._wait,
            RobotState.MANUAL_CONTROL: self._execute_state_manual_control,
            RobotState.PAUSED: lambda: self.context.set_mission_message("Mission Paused."),
            RobotState.EXECUTING_ROW: self._execute_state_executing_row,
            RobotState.ERROR: lambda: self.nano_comm.send_command("INDICATE:error", expect_ack=False),
        }

    def _wait(self) -> None:
        time.sleep(0.5)

    def _execute_state_manual_control(self) -> None:
        self.context.set_mission_message("Manual Control Active")
        cmd = self.context.get_manual_command()
        if not cmd:
            return
        if cmd.get("type") == "move":
            speed = int(cmd.get("speed", config.MANUAL_DEFAULT_SPEED))
            direction = cmd.get("direction")
            move_cmds = {
                "forward": (speed, speed), "backward": (-speed, -speed),
                "left": (-config.MANUAL_TURN_SPEED, config.MANUAL_TURN_SPEED),
                "right": (config.MANUAL_TURN_SPEED, -config.MANUAL_TURN_SPEED),
                "stop": (0, 0),
            }
            left, right = move_cmds.get(direction, (0, 0))
            self.uno_comm.send_command(f"MOVE:{left}:{right}")
        elif cmd.get("type") == "pump":
            self.uno_comm.send_command(f"PUMP:{cmd.get('tank')}:{1 if cmd.get('state') else 0}")
        elif cmd.get("type") == "servo" and cmd.get("servo") and cmd.get("angle") is not None:
            self.nano_comm.send_command(f"{cmd['servo'].upper()}:{cmd['angle']}")

    def _execute_state_executing_row(self) -> None:
        ui_data = self.context.get_all_data_for_ui()
        plan: Dict[str, Any] = ui_data.get("mission_plan") or {}
        progress: Dict[str, Any] = ui_data.get("mission_progress") or {}
        layout = plan.get("layoutMode")
        op_mode = plan.get("operationMode")
        map_rows: List[Dict[str, Any]] = plan.get("map") or []

        if not layout or not op_mode or not map_rows:
            self._handle_error("Mission plan is empty or invalid.")
            return

        current_row_idx = int(progress.get("current_row_index", 0))
        current_plant_idx = int(progress.get("current_plant_index", 0))

        if current_row_idx >= len(map_rows):
            self._complete_mission()
            return
        
        if current_plant_idx == 0:
            logger.info(f"Start of Row #{current_row_idx + 1}. Panning camera left.")
            self.nano_comm.send_command(f"PAN:{config.CAMERA_ANGLES['pan_left']}", expect_ack=False)
            time.sleep(config.CAMERA_SETTLE_TIME_S)

        if current_plant_idx > 0:
            move_dist = float(plan.get("scan_step_cm", 0.0)) if op_mode == "continuous" else float(map_rows[current_row_idx].get("spacing_cm", 0.0))
            if move_dist <= 0:
                self._handle_error("Invalid mission: movement distance is 0.")
                return
            
            self.context.set_mission_message(f"Moving {move_dist:.1f} cm...")
            logger.info(f"Moving {move_dist:.1f} cm to next plant/scan position...")
            if not self._move_distance_cm(move_dist):
                self._handle_error("Movement failed. Mission aborted.")
                return
            prev_dist = float(progress.get("total_distance_in_row_cm", 0.0))
            self.context.update_mission_progress(total_distance_in_row_cm=prev_dist + move_dist)

        detection_found = self._analyze_plant_at_current_location()
        consec_empty = 0 if detection_found else int(progress.get("consecutive_empty_scans", 0)) + 1
        self.context.update_mission_progress(consecutive_empty_scans=consec_empty)

        if self._end_of_row_check():
            logger.info("End of row reached. Panning camera to front.")
            self.nano_comm.send_command(f"PAN:{config.CAMERA_ANGLES['pan_straight']}", expect_ack=False)
            time.sleep(config.CAMERA_SETTLE_TIME_S)

            if current_row_idx >= len(map_rows) - 1:
                self._complete_mission()
            else:
                next_row_idx = current_row_idx + 1
                logger.info(f"Row {current_row_idx + 1} complete. Moving to row {next_row_idx + 1}.")
                self.context.set_mission_message(f"Row {current_row_idx + 1} complete. Preparing for row {next_row_idx + 1}.")
                self.context.update_mission_progress(
                    current_row_index=next_row_idx, current_plant_index=0,
                    total_distance_in_row_cm=0.0, consecutive_empty_scans=0,
                )
            return

        self.context.update_mission_progress(current_plant_index=current_plant_idx + 1)
        self.context.set_state(RobotState.EXECUTING_ROW)

    def _complete_mission(self) -> None:
        logger.info("Mission Complete.")
        self.context.set_mission_message("Mission Complete! View summary below.")
        self.context.set_state(RobotState.IDLE)

    def _analyze_plant_at_current_location(self) -> bool:
        ui_data = self.context.get_all_data_for_ui()
        mission_id: Optional[str] = ui_data.get("mission_id")
        plant_num = int(ui_data.get("mission_progress", {}).get("current_plant_index", 0)) + 1
        self.context.set_mission_message(f"Starting analysis for Plant #{plant_num}...")
        logger.info(f"--- Plant #{plant_num} Analysis Started ---")
        self.nano_comm.send_command("INDICATE:working", expect_ack=False)

        all_detections_in_scan: List[Dict[str, Any]] = []
        plant_log_entry = {"plant_number": plant_num, "detected_diseases": set(), "images": {}, "treatment_applied": "None"}

        for angle_name in ["top", "middle", "bottom"]:
            if self.context.get_state() != RobotState.EXECUTING_ROW:
                logger.warning("State changed during analysis. Aborting scan for this plant.")
                return False

            self.context.set_mission_message(f"Capturing {angle_name}...")
            logger.info(f"Tilting to and capturing {angle_name}...")
            self.nano_comm.send_command(f"TILT:{config.CAMERA_ANGLES[f'tilt_{angle_name}']}", expect_ack=False)
            time.sleep(config.CAMERA_SETTLE_TIME_S + 0.5)

            frame = self.camera.capture_frame()
            if frame is None:
                logger.error(f"CAMERA FAILED at {angle_name} angle. Skipping.")
                continue
            self.context.update_scan_image(angle_name, frame)
            
            time.sleep(config.YOLO_PRE_PROCESSING_DELAY_S)

            self.context.set_mission_message(f"Processing {angle_name}...")
            logger.info(f"Running YOLO on {angle_name} view.")
            
            detections = self.stress_detector.detect(frame)

            if detections:
                detected_names = {d["class_name"] for d in detections}
                logger.info(f"Detected at {angle_name}: {', '.join(sorted(detected_names))}")
                plant_log_entry["detected_diseases"].update(detected_names)
                all_detections_in_scan.extend(detections)
                image_path_rel = self._save_detection_image(frame, mission_id, plant_num, angle_name, detected_names)
                if image_path_rel:
                    plant_log_entry["images"][angle_name] = image_path_rel
                    for det in detections:
                        db.log_detection(mission_id, plant_num, angle_name, det["class_name"], det["confidence"], image_path_rel)
            else:
                logger.info(f"No stress found at {angle_name}.")
            
            time.sleep(config.YOLO_POST_PROCESSING_DELAY_S)

        self.nano_comm.send_command(f"TILT:{config.CAMERA_ANGLES['tilt_middle']}", expect_ack=False)

        if not all_detections_in_scan:
            self.context.set_mission_message(f"Plant #{plant_num}: Healthy")
            logger.info(f"Plant #{plant_num} is Healthy.")
            plant_log_entry["detected_diseases"].add("Healthy")
            detection_found = False
            try:
                db.log_detection(
                    mission_id=mission_id,
                    plant_number=plant_num,
                    scan_angle='overall',
                    stress_detected='Healthy',
                    confidence=1.0,
                    image_path=None
                )
            except Exception as db_err:
                logger.error(f"Failed to log Healthy status to DB: {db_err}", exc_info=True)
        else:
            unique_diseases = sorted(list(plant_log_entry["detected_diseases"]))
            self.context.set_mission_message(f"Detected from 3 angles: {', '.join(unique_diseases)}")
            logger.info(f"Detections for Plant #{plant_num}: {unique_diseases}. Deciding treatment...")
            time.sleep(1)
            treatment_applied = self._decide_and_apply_treatment(all_detections_in_scan)
            if treatment_applied:
                plant_log_entry["treatment_applied"] = treatment_applied
            detection_found = True

        plant_log_entry["detected_diseases"] = sorted(list(plant_log_entry["detected_diseases"]))
        self.context.log_plant_analysis(plant_log_entry)
        logger.info(f"--- Plant #{plant_num} Analysis Complete ---")
        return detection_found

    def _decide_and_apply_treatment(self, detections: List[Dict[str, Any]]) -> Optional[str]:
        """
        Aggregates detections and applies the most appropriate treatment based on real sensor data.
        """
        if not detections:
            return None

        group_counts = Counter()
        for det in detections:
            group = self.treatment_planner.get_group_for_stress(det["class_name"])
            if group:
                group_counts[group["name"]] += 1
        
        if not group_counts:
            logger.warning("Detections found, but none mapped to a treatment group.")
            return None

        # Priority 1: Nutrient/Fertilizer Group.
        fertilizer_group_name = config.FERTILIZER_GROUP["name"]
        if fertilizer_group_name in group_counts:
            logger.info(f"Prioritizing treatment for '{fertilizer_group_name}'.")
            plan_step = self.treatment_planner.create_plan_for_group(
                config.FERTILIZER_GROUP, self.context.get_sensor_data()
            )
            if plan_step:
                self._execute_treatment_step(plan_step)
                return plan_step["treatment_name"]

        # Priority 2: Pesticides.
        group_counts.pop(fertilizer_group_name, None)
        if not group_counts:
            return None 

        dominant_group_name, _ = group_counts.most_common(1)[0]
        logger.info(f"Dominant pesticide group is '{dominant_group_name}'.")

        all_pesticide_groups = [config.PESTICIDE_GROUP_1, config.PESTICIDE_GROUP_2]
        dominant_group_config = next((g for g in all_pesticide_groups if g["name"] == dominant_group_name), None)

        if dominant_group_config:
            plan_step = self.treatment_planner.create_plan_for_group(
                dominant_group_config, self.context.get_sensor_data()
            )
            if plan_step:
                self._execute_treatment_step(plan_step)
                return plan_step["treatment_name"]

        return None

    def _execute_treatment_step(self, step: Dict[str, Any]) -> None:
        message = f"Applying treatment: {step['treatment_name']}..."
        self.context.set_mission_message(message)
        logger.info(message)
        duration_ms = int((step["volume_ml"] / config.ML_PER_SECOND) * 1000)
        timeout_s = (duration_ms / 1000.0) + 2.0
        self.uno_comm.send_command(f"SPRAY:{step['tank_num']}:{duration_ms}", timeout=timeout_s)

    def _save_detection_image(self, frame: np.ndarray, mission_id: Optional[str], plant_num: int, angle: str, detected_names: set) -> Optional[str]:
        try:
            timestamp = datetime.datetime.now().strftime("%H%M%S")
            primary_stress = sorted(list(detected_names))[0].replace(" ", "_")
            mission_suffix = (mission_id or "UNKNOWN").split("-")[-1]
            filename = f"msn_{mission_suffix}_p{plant_num}_{angle}_{primary_stress}_{timestamp}.jpg"
            abs_path = os.path.join(config.CAPTURED_IMAGES_DATA_PATH, filename)
            cv2.imwrite(abs_path, frame)
            return filename
        except Exception as e:
            logger.error(f"Failed to save detection image: {e}", exc_info=True)
            return None

    def _end_of_row_check(self) -> bool:
        ui_data = self.context.get_all_data_for_ui()
        plan, progress = ui_data.get("mission_plan", {}), ui_data.get("mission_progress", {})
        op_mode, map_rows = plan.get("operationMode"), plan.get("map", [])
        if not map_rows: return True
        current_row_idx = int(progress.get("current_row_index", 0))
        if current_row_idx >= len(map_rows): return True
        row_cfg = map_rows[current_row_idx]
        
        if op_mode == "individual":
            return int(progress.get("current_plant_index", 0)) >= int(row_cfg.get("num_plants", 1)) -1
        
        if op_mode == "continuous":
            total_length_cm = row_cfg.get("total_length_cm")
            if isinstance(total_length_cm, (int, float)) and total_length_cm > 0:
                return float(progress.get("total_distance_in_row_cm", 0.0)) >= float(total_length_cm)
            
            side_us = self.context.get_sensor_data().get("S", 0) or 0
            consec_empty = int(progress.get("consecutive_empty_scans", 0))
            if float(side_us) > config.SIDE_US_END_OF_ROW_THRESHOLD_CM and consec_empty >= config.NO_DETECTION_END_OF_ROW_CONSECUTIVE:
                logger.info(f"End-of-row by sensor: S={side_us}cm, empty_scans={consec_empty}")
                return True
        return False

    def _move_distance_cm(self, distance_cm: float, speed: int = config.AUTONOMOUS_MOVE_SPEED) -> bool:
        if distance_cm <= 0:
            return True

        self.uno_comm.send_command("RESET_ENCODER")
        time.sleep(0.1)

        target_pulses = (
            abs(distance_cm) / config.WHEEL_CIRCUMFERENCE_CM
        ) * config.ENCODER_PULSES_PER_ROTATION
        direction = 1 if distance_cm > 0 else -1
        start_time = time.time()

        self.uno_comm.send_command(f"MOVE:{speed * direction}:{speed * direction}")

        while True:
            sensors = self.uno_comm.get_sensors()
            if not sensors:
                self.uno_comm.send_command("STOP")
                return False

            encoder_pulses = sensors.get("E", 0) or 0

            if encoder_pulses >= target_pulses:
                break

            if time.time() - start_time > 20:
                self._handle_error("Movement timed out.")
                return False

            time.sleep(0.1)

        self.uno_comm.send_command("STOP")
        return True

    def _handle_error(self, message: str) -> None:
        logger.error(message)
        self.context.set_mission_message(f"ERROR: {message}")
        self.context.set_state(RobotState.ERROR)
        try:
            self.nano_comm.send_command("INDICATE:error", expect_ack=False)
            self.uno_comm.send_command("STOP")
        except Exception as e:
            logger.error(f"Failed to send error state to hardware: {e}")

    def _handle_web_commands(self) -> None:
        command_obj = self.context.get_web_command()
        if not command_obj: return
        
        command, payload, state = command_obj.get("command"), command_obj.get("payload"), self.context.get_state()
        logger.info(f"Processing web command: '{command}' in state {state.name}")

        if command == "save_mission":
            self.context.save_mission_plan(payload)
        elif command == "start_mission" and state == RobotState.MISSION_AWAITING_START:
            self.context.set_state(RobotState.EXECUTING_ROW)
        elif command == "stop_mission":
            self.uno_comm.send_command("STOP")
            self.context.set_mission_message("Mission stopped by user.")
            self.context.set_state(RobotState.IDLE)
        elif command == "go_to_wizard":
            self.context.clear_mission_plan()
            self.context.set_state(RobotState.MISSION_SETUP)
        elif command == "set_manual_mode":
            if state != RobotState.MANUAL_CONTROL:
                if state in [RobotState.EXECUTING_ROW, RobotState.PAUSED, RobotState.MISSION_AWAITING_START]:
                    self.uno_comm.send_command("STOP")
                self.context.set_state(RobotState.MANUAL_CONTROL)
            else:
                self.context.set_state(RobotState.IDLE)
        elif command == "pause" and state == RobotState.EXECUTING_ROW:
            self.uno_comm.send_command("STOP")
            self.context.set_pause_state(True)
        elif command == "resume" and state == RobotState.PAUSED:
            self.context.set_pause_state(False)
