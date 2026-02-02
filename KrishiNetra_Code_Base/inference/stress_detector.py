# inference/stress_detector.py

import logging
import sys
import os
from typing import List, Dict, Optional

# This allows importing from the parent directory (project root)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import config
from inference.onnx_model_wrapper import ONNXModelWrapper

logger = logging.getLogger(__name__)

class StressDetector(ONNXModelWrapper):
    """
    A specialized class for detecting various plant stresses and diseases
    using the multi-class YOLOv8 ONNX model. This is the only vision model
    used in the new mission-based architecture.
    """

    def __init__(self):
        """
        Initializes the StressDetector with settings from the main config file.
        """
        logger.info("Initializing Stress Detector...")
        
        super().__init__(
            model_path=config.STRESS_DETECTOR_MODEL_PATH,
            input_size=config.STRESS_MODEL_INPUT_SIZE,
            class_names=config.STRESS_CLASS_NAMES,
            confidence_thresh=config.INFERENCE_CONFIDENCE_THRESHOLD
        )

        if self.is_initialized:
            logger.info("Stress Detector initialized successfully.")
        else:
            logger.error("Failed to initialize Stress Detector.")

    def get_primary_stress(self, detections: List[Dict]) -> Optional[Dict]:
        """
        A helper method to identify the most significant stress from a list of detections.
        
        The current heuristic is to return the detection with the highest confidence score.
        This is effective for deciding the primary treatment action when multiple
        stresses might be visible on a plant.

        Args:
            detections (List[Dict]): A list of detection dictionaries from the detect() method.

        Returns:
            Optional[Dict]: The dictionary of the highest-confidence stress detection,
                            or None if no stresses were detected.
        """
        if not detections:
            return None

        # Find and return the detection with the maximum confidence score.
        primary_stress = max(detections, key=lambda det: det['confidence'])
        
        return primary_stress