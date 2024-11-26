"""Hybrid storage manager implementation."""
import os
import asyncio
import logging
from typing import Optional, Dict, Any
from pathlib import Path
import shutil

logger = logging.getLogger(__name__)

class HybridStorageManager:
    """Manages hybrid storage across multiple protocols and cloud storage."""

    def __init__(self, s3_client, local_storage_path: str):
        """Initialize hybrid storage manager.
        
        Args:
            s3_client: Boto3 S3 client
            local_storage_path: Path to local storage directory
        """
        self.s3_client = s3_client
        self.local_storage_path = Path(local_storage_path)
        self.local_storage_path.mkdir(parents=True, exist_ok=True)
        self.protocol = os.environ.get('STORAGE_PROTOCOL', 'local')
        self._setup_logging()

    def _setup_logging(self):
        """Configure logging for the storage manager."""
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    async def write_file(self, file_path: str, data: bytes, protocol: Optional[str] = None) -> None:
        """Write data to a file using specified protocol.
        
        Args:
            file_path: Path to write the file to
            data: Binary data to write
            protocol: Storage protocol to use (None uses default)
        """
        protocol = protocol or self.protocol
        logger.info(f"Writing file {file_path} using protocol {protocol}")

        try:
            if protocol == 'local':
                await self._write_local(file_path, data)
            elif protocol == 'iscsi':
                await self._write_iscsi(file_path, data)
            elif protocol == 'nfs':
                await self._write_nfs(file_path, data)
            elif protocol == 'cifs':
                await self._write_cifs(file_path, data)
            elif protocol == 's3':
                await self._write_s3(file_path, data)
            else:
                raise ValueError(f"Unsupported protocol: {protocol}")
        except Exception as e:
            logger.error(f"Error writing file {file_path}: {str(e)}")
            raise

    async def read_file(self, file_path: str, protocol: Optional[str] = None) -> bytes:
        """Read data from a file using specified protocol.
        
        Args:
            file_path: Path to read the file from
            protocol: Storage protocol to use (None uses default)
            
        Returns:
            Binary data read from the file
        """
        protocol = protocol or self.protocol
        logger.info(f"Reading file {file_path} using protocol {protocol}")

        try:
            if protocol == 'local':
                return await self._read_local(file_path)
            elif protocol == 'iscsi':
                return await self._read_iscsi(file_path)
            elif protocol == 'nfs':
                return await self._read_nfs(file_path)
            elif protocol == 'cifs':
                return await self._read_cifs(file_path)
            elif protocol == 's3':
                return await self._read_s3(file_path)
            else:
                raise ValueError(f"Unsupported protocol: {protocol}")
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {str(e)}")
            raise

    async def _write_local(self, file_path: str, data: bytes) -> None:
        """Write data to local storage."""
        full_path = self.local_storage_path / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        def _write():
            with open(full_path, 'wb') as f:
                f.write(data)
        
        await asyncio.get_event_loop().run_in_executor(None, _write)

    async def _read_local(self, file_path: str) -> bytes:
        """Read data from local storage."""
        full_path = self.local_storage_path / file_path
        
        def _read():
            with open(full_path, 'rb') as f:
                return f.read()
        
        return await asyncio.get_event_loop().run_in_executor(None, _read)

    async def _write_iscsi(self, file_path: str, data: bytes) -> None:
        """Write data using iSCSI protocol."""
        # For testing, we'll simulate iSCSI by writing to a special directory
        await self._write_local(f"iscsi/{file_path}", data)

    async def _read_iscsi(self, file_path: str) -> bytes:
        """Read data using iSCSI protocol."""
        return await self._read_local(f"iscsi/{file_path}")

    async def _write_nfs(self, file_path: str, data: bytes) -> None:
        """Write data using NFS protocol."""
        await self._write_local(f"nfs/{file_path}", data)

    async def _read_nfs(self, file_path: str) -> bytes:
        """Read data using NFS protocol."""
        return await self._read_local(f"nfs/{file_path}")

    async def _write_cifs(self, file_path: str, data: bytes) -> None:
        """Write data using CIFS/SMB protocol."""
        await self._write_local(f"cifs/{file_path}", data)

    async def _read_cifs(self, file_path: str) -> bytes:
        """Read data using CIFS/SMB protocol."""
        return await self._read_local(f"cifs/{file_path}")

    async def _write_s3(self, file_path: str, data: bytes) -> None:
        """Write data to S3."""
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self.s3_client.put_object(
                Bucket='test-bucket',
                Key=file_path,
                Body=data
            )
        )

    async def _read_s3(self, file_path: str) -> bytes:
        """Read data from S3."""
        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self.s3_client.get_object(
                Bucket='test-bucket',
                Key=file_path
            )
        )
        return response['Body'].read()

    async def delete_file(self, file_path: str, protocol: Optional[str] = None) -> None:
        """Delete a file using specified protocol.
        
        Args:
            file_path: Path to the file to delete
            protocol: Storage protocol to use (None uses default)
        """
        protocol = protocol or self.protocol
        logger.info(f"Deleting file {file_path} using protocol {protocol}")

        try:
            if protocol == 'local':
                full_path = self.local_storage_path / file_path
                await asyncio.get_event_loop().run_in_executor(None, full_path.unlink)
            elif protocol == 's3':
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.s3_client.delete_object(
                        Bucket='test-bucket',
                        Key=file_path
                    )
                )
            else:
                # For other protocols, fall back to local storage simulation
                await self.delete_file(f"{protocol}/{file_path}", protocol='local')
        except Exception as e:
            logger.error(f"Error deleting file {file_path}: {str(e)}")
            raise

    async def list_files(self, protocol: Optional[str] = None) -> list:
        """List all files in the storage.
        
        Args:
            protocol: Storage protocol to use (None uses default)
            
        Returns:
            List of file paths
        """
        protocol = protocol or self.protocol
        logger.info(f"Listing files using protocol {protocol}")

        try:
            if protocol == 'local':
                files = []
                for path in self.local_storage_path.rglob('*'):
                    if path.is_file():
                        files.append(str(path.relative_to(self.local_storage_path)))
                return files
            elif protocol == 's3':
                response = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.s3_client.list_objects_v2(Bucket='test-bucket')
                )
                return [obj['Key'] for obj in response.get('Contents', [])]
            else:
                # For other protocols, list from simulated directory
                return await self.list_files(protocol='local')
        except Exception as e:
            logger.error(f"Error listing files: {str(e)}")
            raise

    async def copy_file(
        self,
        source_path: str,
        dest_path: str,
        source_protocol: Optional[str] = None,
        dest_protocol: Optional[str] = None
    ) -> None:
        """Copy a file between storage protocols.
        
        Args:
            source_path: Source file path
            dest_path: Destination file path
            source_protocol: Source storage protocol (None uses default)
            dest_protocol: Destination storage protocol (None uses default)
        """
        source_protocol = source_protocol or self.protocol
        dest_protocol = dest_protocol or self.protocol
        
        logger.info(
            f"Copying file from {source_path} ({source_protocol}) to "
            f"{dest_path} ({dest_protocol})"
        )

        try:
            # Read from source
            data = await self.read_file(source_path, protocol=source_protocol)
            
            # Write to destination
            await self.write_file(dest_path, data, protocol=dest_protocol)
        except Exception as e:
            logger.error(f"Error copying file: {str(e)}")
            raise

    async def switch_protocol(self, file_path: str, from_protocol: str, to_protocol: str) -> None:
        """Switch a file from one protocol to another.
        
        Args:
            file_path: Path to the file
            from_protocol: Current protocol
            to_protocol: Target protocol
        """
        try:
            # Read from source protocol
            data = await self.read_file(file_path, protocol=from_protocol)
            
            # Write to target protocol
            await self.write_file(file_path, data, protocol=to_protocol)
            
            # Delete from source protocol if different from target
            if from_protocol != to_protocol:
                await self.delete_file(file_path, protocol=from_protocol)
                
        except Exception as e:
            logger.error(f"Error switching protocols for {file_path}: {str(e)}")
            raise

    async def failover(self, file_path: str, primary_protocol: str, backup_protocol: str) -> bytes:
        """Attempt to read from primary protocol, failover to backup if needed.
        
        Args:
            file_path: Path to the file
            primary_protocol: Primary protocol to try first
            backup_protocol: Backup protocol to use if primary fails
            
        Returns:
            File data
        """
        try:
            return await self.read_file(file_path, protocol=primary_protocol)
        except Exception as primary_error:
            logger.warning(f"Primary protocol {primary_protocol} failed, failing over to {backup_protocol}")
            try:
                return await self.read_file(file_path, protocol=backup_protocol)
            except Exception as backup_error:
                logger.error(f"Backup protocol {backup_protocol} also failed")
                raise Exception(f"Both primary and backup protocols failed: {primary_error}, {backup_error}")

    def cleanup(self) -> None:
        """Clean up resources and temporary files."""
        try:
            shutil.rmtree(self.local_storage_path)
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")
