"""
Detection Storage Manager
Handles saving, loading, and managing detection images and metadata
Supports per-camera galleries with backward compatibility for single-camera setup
"""

import json
import cv2
from datetime import datetime, timedelta
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

DETECTIONS_DIR = Path(__file__).parent / "detections"
METADATA_FILE = DETECTIONS_DIR / "detections.json"  # Legacy: single metadata file


class DetectionStorage:
    """Manages storage of detection images and metadata (per-camera support)"""

    def __init__(self):
        """Initialize storage system"""
        # Ensure detections directory exists
        DETECTIONS_DIR.mkdir(exist_ok=True)

        # Load legacy metadata for backward compatibility
        self.metadata = self._load_metadata()
        logger.info(f"Detection storage initialized: {len(self.metadata)} detections on record (legacy)")

    def _get_camera_dir(self, camera_id: str) -> Path:
        """Get camera-specific directory"""
        camera_dir = DETECTIONS_DIR / camera_id
        camera_dir.mkdir(exist_ok=True)
        return camera_dir

    def _get_camera_metadata_file(self, camera_id: str) -> Path:
        """Get camera-specific metadata file"""
        return self._get_camera_dir(camera_id) / "detections.json"

    def _load_metadata(self):
        """Load detection metadata from legacy JSON file (backward compatibility)"""
        if METADATA_FILE.exists():
            try:
                with open(METADATA_FILE, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load legacy metadata: {e}")
                return []
        return []

    def _load_camera_metadata(self, camera_id: str):
        """Load camera-specific metadata"""
        metadata_file = self._get_camera_metadata_file(camera_id)
        if metadata_file.exists():
            try:
                with open(metadata_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load metadata for {camera_id}: {e}")
                return []
        return []

    def _save_metadata(self):
        """Save legacy metadata to JSON file (backward compatibility)"""
        try:
            with open(METADATA_FILE, 'w') as f:
                json.dump(self.metadata, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save legacy metadata: {e}")

    def _save_camera_metadata(self, camera_id: str, metadata: list):
        """Save camera-specific metadata"""
        try:
            metadata_file = self._get_camera_metadata_file(camera_id)
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save metadata for {camera_id}: {e}")

    def save_detection(self, camera_id: str, frame, detections, animal_type="deer"):
        """
        Save a detection image with metadata to camera-specific gallery

        Args:
            camera_id: Camera identifier (e.g., 'camera-front-yard')
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

            # Get camera-specific directory
            camera_dir = self._get_camera_dir(camera_id)
            filepath = camera_dir / filename

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

            # Load, update, and save camera-specific metadata
            camera_metadata = self._load_camera_metadata(camera_id)
            camera_metadata.append(metadata_entry)
            self._save_camera_metadata(camera_id, camera_metadata)

            logger.info(f"✅ Saved detection image: {camera_id}/{filename} ({animal_type}, conf: {max_confidence:.2f})")
            return filename

        except Exception as e:
            logger.error(f"Failed to save detection: {e}")
            return None

    def get_detections(self, camera_id: str = None, limit=None, offset=0):
        """
        Get detection records sorted by most recent first

        Args:
            camera_id: Camera ID for per-camera gallery (None = legacy/all)
            limit: Maximum number of records to return (None = all)
            offset: Number of records to skip

        Returns:
            list: Detection metadata records
        """
        # Load appropriate metadata
        if camera_id:
            # Per-camera gallery
            metadata = self._load_camera_metadata(camera_id)
        else:
            # All cameras: aggregate from all camera subdirectories
            metadata = []
            try:
                for camera_subdir in DETECTIONS_DIR.iterdir():
                    if camera_subdir.is_dir():
                        camera_metadata = self._load_camera_metadata(camera_subdir.name)
                        # Add camera_id to each detection for display purposes
                        for detection in camera_metadata:
                            detection['camera_id'] = camera_subdir.name
                        metadata.extend(camera_metadata)
            except Exception as e:
                logger.error(f"Error loading all camera detections: {e}")
                metadata = self.metadata  # Fallback to legacy

        # Sort by timestamp (newest first)
        sorted_detections = sorted(
            metadata,
            key=lambda x: x['timestamp'],
            reverse=True
        )

        # Apply offset and limit
        if limit:
            return sorted_detections[offset:offset + limit]
        return sorted_detections[offset:]

    def get_detection_stats(self, camera_id: str = None):
        """
        Get statistics about detections

        Args:
            camera_id: Camera ID for per-camera stats (None = legacy/all)
        """
        # Load appropriate metadata
        if camera_id:
            metadata = self._load_camera_metadata(camera_id)
        else:
            # All cameras: aggregate from all camera subdirectories
            metadata = []
            try:
                for camera_subdir in DETECTIONS_DIR.iterdir():
                    if camera_subdir.is_dir():
                        camera_metadata = self._load_camera_metadata(camera_subdir.name)
                        metadata.extend(camera_metadata)
            except Exception as e:
                logger.error(f"Error loading all camera stats: {e}")
                metadata = self.metadata  # Fallback to legacy

        if not metadata:
            return {
                'total': 0,
                'by_animal': {},
                'oldest': None,
                'newest': None
            }

        # Count by animal type
        by_animal = {}
        for detection in metadata:
            animal = detection['animal_type']
            by_animal[animal] = by_animal.get(animal, 0) + 1

        # Get date range
        timestamps = [d['timestamp'] for d in metadata]
        oldest = min(timestamps)
        newest = max(timestamps)

        return {
            'total': len(metadata),
            'by_animal': by_animal,
            'oldest': oldest,
            'newest': newest
        }

    def delete_detections_by_age(self, age_filter, camera_id: str = None):
        """
        Delete detections based on age filter

        Args:
            age_filter: One of: 'all', 'year', 'month', 'week', 'day', 'hour', '10min'
            camera_id: Camera ID for per-camera deletion (None = legacy/all)

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

        # Load appropriate metadata
        if camera_id:
            metadata = self._load_camera_metadata(camera_id)
            delete_dir = self._get_camera_dir(camera_id)
        else:
            metadata = self.metadata
            delete_dir = DETECTIONS_DIR

        # Find detections to delete
        to_delete = []
        to_keep = []

        for detection in metadata:
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
                filepath = delete_dir / detection['filename']
                if filepath.exists():
                    filepath.unlink()
                    deleted_count += 1
                    logger.info(f"Deleted: {detection['filename']}")
            except Exception as e:
                logger.error(f"Failed to delete {detection['filename']}: {e}")

        # Update metadata
        if camera_id:
            self._save_camera_metadata(camera_id, to_keep)
        else:
            self.metadata = to_keep
            self._save_metadata()

        logger.info(f"🗑️  Deleted {deleted_count} detection images (filter: {age_filter})")
        return deleted_count

    def get_detection_image_path(self, camera_id: str = None, filename: str = None):
        """
        Get full path to detection image

        Args:
            camera_id: Camera ID (None = legacy)
            filename: Filename

        Returns:
            Path: Full path to image
        """
        if camera_id:
            return self._get_camera_dir(camera_id) / filename
        else:
            return DETECTIONS_DIR / filename

    def cleanup_old_detections(self, max_age_days=7, camera_id: str = None):
        """
        Remove detection images and metadata older than max_age_days

        Args:
            max_age_days: Maximum age in days to keep (default: 7)
            camera_id: Camera ID for per-camera cleanup (None = legacy)

        Returns:
            tuple: (files_deleted: int, space_freed_mb: float)
        """
        try:
            cutoff = datetime.now() - timedelta(days=max_age_days)
            files_deleted = 0
            space_freed = 0

            # Determine directory and metadata
            if camera_id:
                cleanup_dir = self._get_camera_dir(camera_id)
                metadata = self._load_camera_metadata(camera_id)
            else:
                cleanup_dir = DETECTIONS_DIR
                metadata = self.metadata

            # Clean up image files (only JPGs in root or camera subdirs)
            if camera_id:
                # Per-camera: clean JPGs in camera directory only
                for img_file in cleanup_dir.glob("*.jpg"):
                    file_time = datetime.fromtimestamp(img_file.stat().st_mtime)
                    if file_time < cutoff:
                        space_freed += img_file.stat().st_size
                        img_file.unlink()
                        files_deleted += 1
            else:
                # Legacy: clean JPGs only in root (not in subdirectories)
                for img_file in cleanup_dir.glob("*.jpg"):
                    file_time = datetime.fromtimestamp(img_file.stat().st_mtime)
                    if file_time < cutoff:
                        space_freed += img_file.stat().st_size
                        img_file.unlink()
                        files_deleted += 1

            # Clean up metadata entries
            original_count = len(metadata)
            cleaned_metadata = [
                entry for entry in metadata
                if datetime.fromisoformat(entry['timestamp']) >= cutoff
            ]

            if len(cleaned_metadata) < original_count:
                if camera_id:
                    self._save_camera_metadata(camera_id, cleaned_metadata)
                else:
                    self.metadata = cleaned_metadata
                    self._save_metadata()

            space_freed_mb = space_freed / (1024 * 1024)
            logger.info(f"Cleanup: Deleted {files_deleted} files older than {max_age_days} days ({space_freed_mb:.2f} MB freed)")
            return files_deleted, space_freed_mb

        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            return 0, 0.0


# Singleton instance
_storage_instance = None


def get_detection_storage():
    """Get singleton DetectionStorage instance"""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = DetectionStorage()
    return _storage_instance
