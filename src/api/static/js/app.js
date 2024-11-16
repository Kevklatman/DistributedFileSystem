// Main application code
document.addEventListener('DOMContentLoaded', () => {
    const root = document.getElementById('root');
    
    // Create main container
    const container = document.createElement('div');
    container.innerHTML = `
        <h1>Distributed File System</h1>
        <div id="error" class="error" style="display: none;"></div>
        <div id="buckets"></div>
        <div id="bucketList"></div>
        <div id="welcomeMessage" style="display: none;">Select a bucket to view its objects.</div>
        <div id="objectList" style="display: none;">
            <h2 id="currentBucketName"></h2>
            <div id="objects"></div>
        </div>
        <div id="versionModal" class="modal fade" tabindex="-1" role="dialog" aria-hidden="true">
            <div class="modal-dialog" role="document">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Object Versions</h5>
                        <button type="button" class="close" data-dismiss="modal" aria-label="Close">
                            <span aria-hidden="true">&times;</span>
                        </button>
                    </div>
                    <div class="modal-body">
                        <div id="versions"></div>
                    </div>
                </div>
            </div>
        </div>
    `;
    root.appendChild(container);

    // Global state
    let currentBucket = null;
    const versionModal = new bootstrap.Modal(document.getElementById('versionModal'));

    // Utility functions
    function formatSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    function formatDate(dateString) {
        return new Date(dateString).toLocaleString();
    }

    // API functions
    async function fetchBuckets() {
        console.log('Fetching buckets...');
        try {
            const response = await fetch('/api/v1/s3/buckets', {
                headers: {
                    'Accept': 'application/json'
                }
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            console.log('Received data:', data);
            
            if (data.error) {
                throw new Error(data.error);
            }

            displayBuckets(data.buckets || []);
        } catch (error) {
            console.error('Error fetching buckets:', error);
            displayError(`Error: ${error.message}`);
        }
    }

    async function createBucket() {
        const bucketName = document.getElementById('newBucketName').value.trim();
        if (!bucketName) return;

        try {
            const response = await fetch(`/api/v1/s3/buckets/${bucketName}`, {
                method: 'PUT'
            });
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Failed to create bucket');
            }
            document.getElementById('newBucketName').value = '';
            fetchBuckets();
        } catch (error) {
            displayError('Error creating bucket: ' + error.message);
        }
    }

    async function deleteBucket(bucketName) {
        if (!confirm(`Are you sure you want to delete bucket "${bucketName}"?`)) return;

        try {
            const response = await fetch(`/api/v1/s3/buckets/${bucketName}`, {
                method: 'DELETE'
            });
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Failed to delete bucket');
            }
            fetchBuckets();
            if (currentBucket === bucketName) {
                currentBucket = null;
                showWelcomeMessage();
            }
        } catch (error) {
            displayError('Error deleting bucket: ' + error.message);
        }
    }

    function displayBuckets(buckets) {
        const bucketsContainer = document.getElementById('bucketList');
        if (!buckets || buckets.length === 0) {
            bucketsContainer.innerHTML = '<p>No buckets found. Create one to get started!</p>';
            return;
        }

        const bucketsList = buckets.map(bucket => {
            const bucketName = bucket.Name || bucket.name;
            const creationDate = bucket.CreationDate || bucket.creation_date;
            return `
                <div class="list-group-item d-flex justify-content-between align-items-center">
                    <span class="bucket-name" onclick="selectBucket('${bucketName}')">${bucketName}</span>
                    ${creationDate ? `<small class="text-muted">${formatDate(creationDate)}</small>` : ''}
                    <button class="btn btn-danger btn-sm" onclick="deleteBucket('${bucketName}')">Delete</button>
                </div>
            `;
        }).join('');

        bucketsContainer.innerHTML = bucketsList;
    }

    function displayError(message) {
        const errorDiv = document.getElementById('error');
        errorDiv.textContent = message;
        errorDiv.style.display = 'block';
        setTimeout(() => {
            errorDiv.style.display = 'none';
        }, 5000);
    }

    function showWelcomeMessage() {
        document.getElementById('welcomeMessage').style.display = 'block';
        document.getElementById('objectList').style.display = 'none';
    }

    function selectBucket(bucketName) {
        currentBucket = bucketName;
        document.getElementById('welcomeMessage').style.display = 'none';
        document.getElementById('objectList').style.display = 'block';
        document.getElementById('currentBucketName').textContent = bucketName;
        refreshCurrentBucket();
    }

    async function refreshCurrentBucket() {
        try {
            const response = await fetch(`/api/v1/s3/buckets/${currentBucket}/objects`, {
                headers: {
                    'Accept': 'application/json'
                }
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            console.log('Received data:', data);
            
            if (data.error) {
                throw new Error(data.error);
            }

            displayObjects(data.objects || []);
        } catch (error) {
            console.error('Error fetching objects:', error);
            displayError(`Error: ${error.message}`);
        }
    }

    function displayObjects(objects) {
        const objectsContainer = document.getElementById('objects');
        if (!objects || objects.length === 0) {
            objectsContainer.innerHTML = '<p>No objects found in this bucket.</p>';
            return;
        }

        const objectsList = objects.map(object => {
            const objectName = object.Key || object.key;
            const lastModified = object.LastModified || object.last_modified;
            const size = object.Size || object.size;
            return `
                <div class="list-group-item d-flex justify-content-between align-items-center">
                    <span class="object-name">${objectName}</span>
                    ${lastModified ? `<small class="text-muted">${formatDate(lastModified)}</small>` : ''}
                    <small class="text-muted">${formatSize(size)}</small>
                    <button class="btn btn-primary btn-sm" onclick="showVersions('${objectName}')">Versions</button>
                </div>
            `;
        }).join('');

        objectsContainer.innerHTML = objectsList;
    }

    function showVersions(objectName) {
        versionModal.show();
        const versionsContainer = document.getElementById('versions');
        // Fetch and display versions of the object
        fetch(`/api/v1/s3/buckets/${currentBucket}/objects/${objectName}/versions`)
            .then(response => response.json())
            .then(data => {
                const versionsList = data.versions.map(version => {
                    const versionId = version.VersionId || version.version_id;
                    const lastModified = version.LastModified || version.last_modified;
                    return `
                        <div class="list-group-item d-flex justify-content-between align-items-center">
                            <span class="version-id">${versionId}</span>
                            ${lastModified ? `<small class="text-muted">${formatDate(lastModified)}</small>` : ''}
                        </div>
                    `;
                }).join('');
                versionsContainer.innerHTML = versionsList;
            })
            .catch(error => console.error('Error fetching versions:', error));
    }
});
