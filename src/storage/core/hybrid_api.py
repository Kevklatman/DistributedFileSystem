from flask import Flask, request, jsonify, send_file
from flask_restx import Api, Resource, fields
from pathlib import Path
from typing import Dict
import io

from src.models.models import StorageLocation, StoragePool, Volume
from .hybrid_storage import HybridStorageManager

app = Flask(__name__)
api = Api(app, version='1.0', title='Hybrid Storage API',
          description='API for managing hybrid cloud-enterprise storage')

# Initialize storage manager
storage_manager = HybridStorageManager(str(Path.home() / "hybrid_storage"))

# API Models
location_model = api.model('StorageLocation', {
    'type': fields.String(required=True, enum=['on_prem', 'aws_s3', 'azure_blob', 'gcp_storage']),
    'path': fields.String(required=True),
    'region': fields.String(required=False),
    'availability_zone': fields.String(required=False),
    'performance_tier': fields.String(required=False, enum=['standard', 'premium'])
})

pool_model = api.model('StoragePool', {
    'name': fields.String(required=True),
    'location': fields.Nested(location_model),
    'capacity_gb': fields.Integer(required=True)
})

volume_model = api.model('Volume', {
    'name': fields.String(required=True),
    'size_gb': fields.Integer(required=True),
    'pool_id': fields.String(required=True),
    'cloud_backup': fields.Boolean(required=False, default=False),
    'cloud_tiering': fields.Boolean(required=False, default=False)
})

@api.route('/pools')
class StoragePoolResource(Resource):
    @api.expect(pool_model)
    def post(self):
        """Create a new storage pool"""
        data = request.json

        location = StorageLocation(
            type=data['location']['type'],
            path=data['location']['path'],
            region=data['location'].get('region'),
            availability_zone=data['location'].get('availability_zone'),
            performance_tier=data['location'].get('performance_tier', 'standard')
        )

        try:
            pool = storage_manager.create_storage_pool(
                name=data['name'],
                location=location,
                capacity_gb=data['capacity_gb']
            )
            return {
                'id': pool.id,
                'name': pool.name,
                'total_capacity_gb': pool.total_capacity_gb,
                'available_capacity_gb': pool.available_capacity_gb
            }
        except Exception as e:
            return {'error': str(e)}, 400

    def get(self):
        """List all storage pools"""
        pools = []
        for pool_id, pool in storage_manager.system.storage_pools.items():
            pools.append({
                'id': pool.id,
                'name': pool.name,
                'total_capacity_gb': pool.total_capacity_gb,
                'available_capacity_gb': pool.available_capacity_gb
            })
        return pools

@api.route('/volumes')
class VolumeResource(Resource):
    @api.expect(volume_model)
    def post(self):
        """Create a new volume"""
        data = request.json

        try:
            volume = storage_manager.create_volume(
                name=data['name'],
                size_gb=data['size_gb'],
                pool_id=data['pool_id'],
                cloud_backup=data.get('cloud_backup', False),
                cloud_tiering=data.get('cloud_tiering', False)
            )
            return {
                'id': volume.id,
                'name': volume.name,
                'size_gb': volume.size_gb,
                'pool_id': volume.primary_pool_id
            }
        except Exception as e:
            return {'error': str(e)}, 400

    def get(self):
        """List all volumes"""
        volumes = []
        for volume_id, volume in storage_manager.system.volumes.items():
            volumes.append({
                'id': volume.id,
                'name': volume.name,
                'size_gb': volume.size_gb,
                'pool_id': volume.primary_pool_id
            })
        return volumes

@api.route('/volumes/<volume_id>/data/<path:file_path>')
class VolumeDataResource(Resource):
    def put(self, volume_id: str, file_path: str):
        """Write data to a volume"""
        try:
            data = request.get_data()
            storage_manager.write_data(volume_id, file_path, data)
            return {'message': 'Data written successfully'}
        except Exception as e:
            return {'error': str(e)}, 400

    def get(self, volume_id: str, file_path: str):
        """Read data from a volume"""
        try:
            data = storage_manager.read_data(volume_id, file_path)
            return send_file(
                io.BytesIO(data),
                mimetype='application/octet-stream',
                as_attachment=True,
                download_name=Path(file_path).name
            )
        except FileNotFoundError:
            return {'error': 'File not found'}, 404
        except Exception as e:
            return {'error': str(e)}, 400

if __name__ == '__main__':
    app.run(debug=True)
