# hardware/camera_manager.py

import logging
import time
import cv2
import numpy as np
from typing import Optional

# Attempt to import Raspberry Pi specific libraries
try:
    from picamera2 import Picamera2
except ImportError:
    # This allows the code to be syntax-checked on a non-Pi machine.
    print("WARNING: RPi-specific library 'picamera2' not found. Using mock object.")
    Picamera2 = None

logger = logging.getLogger(__name__)

class CameraManager:
    """
    Manages the Raspberry Pi camera for the Krishinetra project.
    
    This class is a pure camera interface, responsible only for initializing,
    capturing frames, and shutting down the camera hardware. All servo control
    has been offloaded to the Arduino Nano for better real-time performance.
    """
    def __init__(self):
        self.is_operational: bool = False
        self.picam2: Optional[Picamera2] = None

        if not Picamera2:
            logger.critical("Failed to initialize CameraManager: picamera2 library is not installed.")
            return

        try:
            # Initialize the Picamera2 object
            self.picam2 = Picamera2()
            
            # Create a configuration for the camera. 640x480 is a good balance
            # between performance and detail for object detection on a Pi.
            cam_config = self.picam2.create_preview_configuration(
                main={"size": (640, 480), "format": "XRGB8888"}
            )
            self.picam2.configure(cam_config)
            
            self.is_operational = True
            logger.info("CameraManager initialized successfully.")

        except Exception as e:
            # This can happen if the camera is not connected or enabled in raspi-config
            logger.critical(f"Failed to initialize CameraManager hardware: {e}", exc_info=True)
            self.is_operational = False

    def start(self) -> None:
        """Starts the camera stream."""
        if not self.is_operational:
            logger.error("Cannot start CameraManager, not operational.")
            return
        
        try:
            if self.picam2 and not self.picam2.started:
                logger.info("Starting camera stream...")
                self.picam2.start()
                # Allow time for the sensor to initialize and adjust exposure.
                time.sleep(1.5)
                logger.info("Camera stream started.")
            else:
                logger.info("Camera stream is already running or object is None.")
        except Exception as e:
            logger.error(f"Failed to start camera: {e}", exc_info=True)
            self.is_operational = False

    def shutdown(self) -> None:
        """Stops the camera stream and releases the hardware resource."""
        if not self.is_operational:
            return
            
        logger.info("Shutting down CameraManager.")
        try:
            if self.picam2 and self.picam2.started:
                self.picam2.stop()
            logger.info("CameraManager shutdown complete.")
        except Exception as e:
            logger.error(f"Error during CameraManager shutdown: {e}", exc_info=True)

    def capture_frame(self) -> Optional[np.ndarray]:
        """
        Captures a single frame from the camera.

        Returns:
            np.ndarray: The captured frame as a NumPy array in BGR format (for OpenCV),
                        or None if an error occurs.
        """
        if not self.is_operational or not self.picam2 or not self.picam2.started:
            logger.error("Cannot capture frame, camera is not running.")
            return None
        
        try:
            # Capture the frame. The picamera2 library returns it in RGB format.
            frame_rgb = self.picam2.capture_array()
            
            # Convert the frame from RGB to BGR, which is the standard format used by OpenCV.
            frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
            return frame_bgr
            
        except Exception as e:
            logger.error(f"Failed to capture frame: {e}", exc_info=True)
            return None