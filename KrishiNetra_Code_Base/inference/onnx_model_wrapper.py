# inference/onnx_model_wrapper.py

import logging
import time
import cv2
import numpy as np
import onnxruntime as ort
import sys
import os
from typing import List, Dict, Tuple

# This allows importing the config file from the project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import config

logger = logging.getLogger(__name__)

class ONNXModelWrapper:
    """
    A generic wrapper for running YOLOv8 object detection models in ONNX format.

    This class handles all the core logic for inference:
    1. Loading the ONNX model into an ONNX Runtime session.
    2. Pre-processing an input image (resizing, padding, normalizing).
    3. Running the inference.
    4. Post-processing the model's output (scaling boxes, applying non-max suppression).
    """

    def __init__(self, model_path: str, input_size: Tuple[int, int], class_names: List[str], confidence_thresh: float):
        """
        Initializes the ONNX model loader and processor.

        Args:
            model_path (str): The absolute path to the .onnx model file.
            input_size (Tuple[int, int]): The expected input size of the model (width, height).
            class_names (List[str]): A list of class names the model can detect.
            confidence_thresh (float): The minimum confidence score to consider a detection.
        """
        self.model_path = model_path
        self.input_width, self.input_height = input_size
        self.class_names = class_names
        self.confidence_thresh = confidence_thresh
        self.session = None
        self.is_initialized = False

        self._initialize_model()

    def _initialize_model(self):
        """Loads the ONNX model into an ONNX Runtime inference session."""
        if not os.path.exists(self.model_path):
            logger.critical(f"Model file not found at path: {self.model_path}")
            return
        
        logger.info(f"Initializing ONNX model from: {os.path.basename(self.model_path)}")
        try:
            # For Raspberry Pi, 'CPUExecutionProvider' is the recommended and most stable option.
            providers = ['CPUExecutionProvider']
            self.session = ort.InferenceSession(self.model_path, providers=providers)
            
            model_inputs = self.session.get_inputs()
            model_outputs = self.session.get_outputs()
            logger.debug(f"Model inputs: {[inp.name for inp in model_inputs]}")
            logger.debug(f"Model outputs: {[out.name for out in model_outputs]}")
            
            self.is_initialized = True
            logger.info(f"ONNX model '{os.path.basename(self.model_path)}' initialized successfully.")

        except Exception as e:
            logger.critical(f"Failed to initialize ONNX model '{self.model_path}': {e}", exc_info=True)
            self.session = None

    def _preprocess(self, image: np.ndarray) -> np.ndarray:
        """
        Prepares an input image for the YOLOv8 model.
        """
        img_height, img_width = image.shape[:2]

        ratio = min(self.input_width / img_width, self.input_height / img_height)
        new_width = int(img_width * ratio)
        new_height = int(img_height * ratio)
        resized_img = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_LINEAR)

        padded_img = np.full((self.input_height, self.input_width, 3), 114, dtype=np.uint8)
        dw, dh = (self.input_width - new_width) // 2, (self.input_height - new_height) // 2
        padded_img[dh:dh + new_height, dw:dw + new_width] = resized_img

        transposed_img = padded_img.transpose(2, 0, 1)
        normalized_img = transposed_img / 255.0
        
        return np.expand_dims(normalized_img, axis=0).astype(np.float32)

    def _postprocess(self, model_output: np.ndarray, original_image_shape: Tuple[int, int]) -> List[Dict]:
        """
        Processes the raw output from the YOLOv8 model.
        """
        outputs = np.transpose(np.squeeze(model_output[0]))
        
        rows = outputs.shape[0]
        boxes, scores, class_ids = [], [], []
        
        img_height, img_width = original_image_shape
        x_scale = self.input_width / img_width
        y_scale = self.input_height / img_height

        for i in range(rows):
            classes_scores = outputs[i][4:]
            max_score = np.amax(classes_scores)

            if max_score >= self.confidence_thresh:
                class_id = np.argmax(classes_scores)
                
                x, y, w, h = outputs[i, 0], outputs[i, 1], outputs[i, 2], outputs[i, 3]

                left = int((x - (w / 2) - ((self.input_width - img_width * x_scale) / 2)) / x_scale)
                top = int((y - (h / 2) - ((self.input_height - img_height * y_scale) / 2)) / y_scale)
                width = int(w / x_scale)
                height = int(h / y_scale)
                
                class_ids.append(class_id)
                scores.append(max_score)
                boxes.append([left, top, width, height])

        indices = cv2.dnn.NMSBoxes(boxes, np.array(scores), self.confidence_thresh, 0.45)
        
        detections = []
        if len(indices) > 0:
            for i in indices.flatten():
                detections.append({
                    "class_id": class_ids[i],
                    "class_name": self.class_names[class_ids[i]],
                    "confidence": float(scores[i]),
                    "box": boxes[i]
                })
        
        return detections

    def detect(self, image: np.ndarray) -> List[Dict]:
        """
        The main public method for performing object detection.
        """
        if not self.is_initialized or self.session is None:
            logger.error("Cannot perform detection, model is not initialized.")
            return []
        
        original_shape = image.shape[:2]
        
        preprocessed_image = self._preprocess(image)
        
        model_inputs = self.session.get_inputs()
        input_name = model_inputs[0].name
        
        try:
            start_time = time.perf_counter()
            outputs = self.session.run(None, {input_name: preprocessed_image})
            inference_time = (time.perf_counter() - start_time) * 1000
            logger.debug(f"Inference on '{os.path.basename(self.model_path)}' took {inference_time:.2f} ms")
        except Exception as e:
            logger.error(f"Error during model inference: {e}", exc_info=True)
            return []

        detections = self._postprocess(outputs, original_shape)
        
        return detections