"""Advanced storage feature routes."""

from flask import Blueprint, request, jsonify, make_response
import logging
from typing import Dict

from ..services.advanced_storage_service import AdvancedStorageService
from ..services.config import current_config

logger = logging.getLogger(__name__)

# Create Blueprint for advanced storage routes
advanced_storage = Blueprint("advanced_storage", __name__)

# Initialize service
storage_service = AdvancedStorageService(current_config["storage_root"])


@advanced_storage.route("/volumes", methods=["POST"])
def create_volume():
    """Create a new volume with advanced features."""
    try:
        data = request.json
        if not all(k in data for k in ["name", "size_gb", "pool_id"]):
            return jsonify({"error": "Missing required fields"}), 400
            
        volume = storage_service.create_volume(
            name=data["name"],
            size_gb=data["size_gb"],
            pool_id=data["pool_id"],
            dedup=data.get("dedup", False),
            compression=data.get("compression", False),
            cloud_backup=data.get("cloud_backup", False),
        )
        return jsonify({"volume_id": volume.id}), 201
    except ValueError as e:
        logger.error(f"Invalid input: {str(e)}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Failed to create volume: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@advanced_storage.route("/volumes/<volume_id>/snapshots", methods=["POST"])
def create_snapshot(volume_id: str):
    """Create a volume snapshot."""
    try:
        data = request.json
        snapshot_id = storage_service.create_snapshot(
            volume_id=volume_id, name=data["name"]
        )
        return jsonify({"snapshot_id": snapshot_id}), 201
    except ValueError as e:
        logger.error(f"Invalid volume: {str(e)}")
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        logger.error(f"Failed to create snapshot: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@advanced_storage.route("/volumes/<volume_id>/snapshots/<snapshot_id>/restore", methods=["POST"])
def restore_snapshot(volume_id: str, snapshot_id: str):
    """Restore a volume from snapshot."""
    try:
        if not volume_id or not snapshot_id:
            return jsonify({"error": "Volume ID and snapshot ID are required"}), 400
            
        success = storage_service.restore_snapshot(volume_id, snapshot_id)
        if success:
            return jsonify({"status": "success"}), 200
        return jsonify({"error": "Failed to restore snapshot"}), 500
    except ValueError as e:
        logger.error(f"Invalid volume or snapshot: {str(e)}")
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        logger.error(f"Failed to restore snapshot: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@advanced_storage.route("/volumes/<volume_id>/backups", methods=["POST"])
def create_backup(volume_id: str):
    """Create a backup."""
    try:
        data = request.json
        backup_id = storage_service.create_backup(
            volume_id=volume_id, target_location=data["target_location"]
        )
        return jsonify({"backup_id": backup_id}), 201
    except ValueError as e:
        logger.error(f"Invalid volume: {str(e)}")
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        logger.error(f"Failed to create backup: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@advanced_storage.route("/volumes/<volume_id>/backups/<backup_id>/restore", methods=["POST"])
def restore_backup(volume_id: str, backup_id: str):
    """Restore from a backup."""
    try:
        if not volume_id or not backup_id:
            return jsonify({"error": "Volume ID and backup ID are required"}), 400
            
        success = storage_service.restore_backup(volume_id, backup_id)
        if success:
            return jsonify({"status": "success"}), 200
        return jsonify({"error": "Failed to restore backup"}), 500
    except ValueError as e:
        logger.error(f"Invalid volume or backup: {str(e)}")
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        logger.error(f"Failed to restore backup: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@advanced_storage.route("/volumes/<volume_id>/efficiency", methods=["GET"])
def get_efficiency_stats(volume_id: str):
    """Get storage efficiency statistics."""
    try:
        if not volume_id:
            return jsonify({"error": "Volume ID is required"}), 400
            
        stats = storage_service.get_efficiency_stats(volume_id)
        return jsonify(stats), 200
    except ValueError as e:
        logger.error(f"Invalid volume: {str(e)}")
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        logger.error(f"Failed to get efficiency stats: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@advanced_storage.route("/volumes/<volume_id>/protection", methods=["GET"])
def get_protection_status(volume_id: str):
    """Get data protection status."""
    try:
        if not volume_id:
            return jsonify({"error": "Volume ID is required"}), 400
            
        status = storage_service.get_protection_status(volume_id)
        return jsonify(status), 200
    except ValueError as e:
        logger.error(f"Invalid volume: {str(e)}")
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        logger.error(f"Failed to get protection status: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500
