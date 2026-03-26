"""
Deer Detection Engine using YOLOv8
Loads model and processes frames to detect deer
"""

import cv2
import numpy as np
from ultralytics import YOLO
from config import DETECTION_CONFIDENCE, TARGET_CLASS_IDS, PERSON_CLASS_ID, MODEL_PATH
import logging

logger = logging.getLogger(__name__)


class DeerDetector:
    """YOLOv8-based animal detection with safety checks"""

    def __init__(self):
        """Initialize the YOLO model"""
        logger.info(f"Loading YOLOv8 model: {MODEL_PATH}")
        try:
            self.model = YOLO(MODEL_PATH)
            logger.info("Model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise

        self.confidence_threshold = DETECTION_CONFIDENCE
        self.target_class_ids = TARGET_CLASS_IDS
        self.person_class_id = PERSON_CLASS_ID
        logger.info(f"Target animals: {TARGET_CLASS_IDS} (deer, cow, sheep)")
        logger.info(f"Safety check: Will NOT activate if person (class {PERSON_CLASS_ID}) detected")

    def detect_deer(self, frame):
        """
        Detect target animals (deer, cow, sheep) with safety checks

        Args:
            frame: OpenCV image (BGR format)

        Returns:
            tuple: (animal_detected: bool, detections: list, annotated_frame: np.array)
            detections format: [{'bbox': (x1, y1, x2, y2), 'confidence': float, 'class': str}, ...]
        """
        if frame is None or frame.size == 0:
            return False, [], frame

        try:
            # Run inference
            results = self.model(frame, conf=self.confidence_threshold, verbose=False)

            animal_detected = False
            person_detected = False
            detections = []

            # Process results
            for result in results:
                boxes = result.boxes
                for box in boxes:
                    class_id = int(box.cls[0])
                    confidence = float(box.conf[0])
                    class_name = result.names[class_id]

                    # Log all detections for debugging
                    logger.info(f"Detected: {class_name} (class {class_id}) with confidence: {confidence:.2f}")

                    # SAFETY CHECK: Detect if person is present
                    if class_id == self.person_class_id:
                        person_detected = True
                        logger.warning(f"⚠️ PERSON DETECTED - Will NOT activate sprinkler!")

                    # Check if this is a target animal (deer, cow, sheep)
                    if class_id in self.target_class_ids:
                        animal_detected = True

                        # Get bounding box coordinates
                        x1, y1, x2, y2 = box.xyxy[0].tolist()

                        detections.append({
                            'bbox': (int(x1), int(y1), int(x2), int(y2)),
                            'confidence': confidence,
                            'class': class_name,
                            'class_id': class_id
                        })

                        logger.info(f"🎯 TARGET ANIMAL ({class_name.upper()}) detected with confidence: {confidence:.2f}")

            # Get annotated frame
            annotated_frame = results[0].plot() if results else frame

            # SAFETY: Only return True if animal detected AND no person detected
            safe_to_activate = animal_detected and not person_detected

            if animal_detected and person_detected:
                logger.warning(f"❌ Animal detected but PERSON also present - BLOCKING activation for safety!")

            return safe_to_activate, detections, annotated_frame

        except Exception as e:
            logger.error(f"Detection error: {e}")
            return False, [], frame

