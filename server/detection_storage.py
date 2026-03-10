"""
Detection Storage Manager
Handles saving, loading, and managing detection images and metadata
"""

import json
import os
import cv2
from datetime import datetime, timedelta
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

DETECTIONS_DIR = Path(__file__).parent / "detections"
METADATA_FILE = DETECTIONS_DIR / "detections.json"


class DetectionStorage:
    """Manages storage of detection images and metadata"""

    def __init__(self):
        """Initialize storage system"""
        # Ensure detections directory exists
        DETECTIONS_DIR.mkdir(exist_ok=True)

        # Load or initialize metadata
        self.metadata = self._load_metadata()
        logger.info(f"Detection storage initialized: {len(self.metadata)} detections on record")

    def _load_metadata(self):
        """Load detection metadata from JSON file"""
        if METADATA_FILE.exists():
            try:
                with open(METADATA_FILE, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load metadata: {e}")
                return []
        return []

    def _save_metadata(self):
        """Save metadata to JSON file"""
        try:
            with open(METADATA_FILE, 'w') as f:
                json.dump(self.metadata, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save metadata: {e}")

    def save_detection(self, frame, detections, animal_type="deer"):
        """
        Save a detection image with metadata

        Args:
            frame: OpenCV image (annotated with bounding boxes)
            detections: List of detection dicts with bbox, confidence, class
            animal_type: Type of animal detected

        Returns:
            str: Filename of saved image
        """
        try:
            # Generate timestamp and filename
            timestamp = datetime.now()
            timestamp_str = timestamp.strftime("%Y-%m-%d_%H-%M-%S")

            # Get highest confidence detection
            max_confidence = max([d['confidence'] for d in detections]) if detections else 0.0

            # Create filename: YYYY-MM-DD_HH-MM-SS_animal_confidence.jpg
            filename = f"{timestamp_str}_{animal_type}_{max_confidence:.2f}.jpg"
            filepath = DETECTIONS_DIR / filename

            # Save image
            cv2.imwrite(str(filepath), frame)

            # Create metadata entry
            metadata_entry = {
                'filename': filename,
                'timestamp': timestamp.isoformat(),
                'animal_type': animal_type,
                'confidence': max_confidence,
                'detection_count': len(detections),
                'detections': [
                    {
                        'class': d['class'],
                        'confidence': d['confidence'],
                        'bbox': d['bbox']
                    }
                    for d in detections
                ]
            }

            # Add to metadata and save
            self.metadata.append(metadata_entry)
            self._save_metadata()

            logger.info(f"✅ Saved detection image: {filename} ({animal_type}, conf: {max_confidence:.2f})")
            return filename

        except Exception as e:
            logger.error(f"Failed to save detection: {e}")
            return None

    def get_detections(self, limit=None, offset=0):
        """
        Get detection records sorted by most recent first

        Args:
            limit: Maximum number of records to return (None = all)
            offset: Number of records to skip

        Returns:
            list: Detection metadata records
        """
        # Sort by timestamp (newest first)
        sorted_detections = sorted(
            self.metadata,
            key=lambda x: x['timestamp'],
            reverse=True
        )

        # Apply offset and limit
        if limit:
            return sorted_detections[offset:offset + limit]
        return sorted_detections[offset:]

    def get_detection_stats(self):
        """Get statistics about detections"""
        if not self.metadata:
            return {
                'total': 0,
                'by_animal': {},
                'oldest': None,
                'newest': None
            }

        # Count by animal type
        by_animal = {}
        for detection in self.metadata:
            animal = detection['animal_type']
            by_animal[animal] = by_animal.get(animal, 0) + 1

        # Get date range
        timestamps = [d['timestamp'] for d in self.metadata]
        oldest = min(timestamps)
        newest = max(timestamps)

        return {
            'total': len(self.metadata),
            'by_animal': by_animal,
            'oldest': oldest,
            'newest': newest
        }

    def delete_detections_by_age(self, age_filter):
        """
        Delete detections based on age filter

        Args:
            age_filter: One of: 'all', 'year', 'month', 'week', 'day', 'hour', '10min'

        Returns:
            int: Number of detections deleted
        """
        now = datetime.now()
        cutoff_time = None

        # Calculate cutoff time based on filter
        if age_filter == 'all':
            cutoff_time = None  # Delete everything
        elif age_filter == 'year':
            cutoff_time = now - timedelta(days=365)
        elif age_filter == 'month':
            cutoff_time = now - timedelta(days=30)
        elif age_filter == 'week':
            cutoff_time = now - timedelta(weeks=1)
        elif age_filter == 'day':
            cutoff_time = now - timedelta(days=1)
        elif age_filter == 'hour':
            cutoff_time = now - timedelta(hours=1)
        elif age_filter == '10min':
            cutoff_time = now - timedelta(minutes=10)
        else:
            logger.error(f"Invalid age filter: {age_filter}")
            return 0

        # Find detections to delete
        to_delete = []
        to_keep = []

        for detection in self.metadata:
            detection_time = datetime.fromisoformat(detection['timestamp'])

            # Check if should be deleted
            if cutoff_time is None or detection_time < cutoff_time:
                to_delete.append(detection)
            else:
                to_keep.append(detection)

        # Delete image files
        deleted_count = 0
        for detection in to_delete:
            try:
                filepath = DETECTIONS_DIR / detection['filename']
                if filepath.exists():
                    filepath.unlink()
                    deleted_count += 1
                    logger.info(f"Deleted: {detection['filename']}")
            except Exception as e:
                logger.error(f"Failed to delete {detection['filename']}: {e}")

        # Update metadata
        self.metadata = to_keep
        self._save_metadata()

        logger.info(f"🗑️  Deleted {deleted_count} detection images (filter: {age_filter})")
        return deleted_count

    def get_detection_image_path(self, filename):
        """Get full path to detection image"""
        return DETECTIONS_DIR / filename


# Singleton instance
_storage_instance = None


def get_detection_storage():
    """Get singleton DetectionStorage instance"""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = DetectionStorage()
    return _storage_instance
