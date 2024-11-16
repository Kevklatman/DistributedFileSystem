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
async function listBuckets() {
    const response = await fetch('/api/s3/buckets');
    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }
    const data = await response.json();
    return data.buckets || [];
}

async function createBucket() {
    const bucketName = document.getElementById('newBucketName').value.trim();
    if (!bucketName) return;

    try {
        const response = await fetch(`/api/s3/buckets/${bucketName}`, {
            method: 'PUT'
        });
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Failed to create bucket');
        }
        document.getElementById('newBucketName').value = '';
        refreshBuckets();
    } catch (error) {
        alert('Error creating bucket: ' + error.message);
    }
}

async function deleteBucket(bucketName) {
    if (!confirm(`Are you sure you want to delete bucket "${bucketName}"?`)) return;

    try {
        const response = await fetch(`/api/s3/buckets/${bucketName}`, {
            method: 'DELETE'
        });
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Failed to delete bucket');
        }
        refreshBuckets();
        if (currentBucket === bucketName) {
            currentBucket = null;
            showWelcomeMessage();
        }
    } catch (error) {
        alert('Error deleting bucket: ' + error.message);
    }
}

async function listObjects(bucketName) {
    const response = await fetch(`/api/s3/buckets/${bucketName}/objects`);
    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }
    const data = await response.json();
    return data.objects || [];
}

async function uploadFile(file, bucketName) {
    const response = await fetch(`/api/s3/buckets/${bucketName}/objects/${file.name}`, {
        method: 'PUT',
        body: file
    });
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Failed to upload file');
    }
}

async function deleteObject(bucketName, objectKey) {
    const response = await fetch(`/api/s3/buckets/${bucketName}/objects/${objectKey}`, {
        method: 'DELETE'
    });
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Failed to delete object');
    }
}

async function getVersioning(bucketName) {
    const response = await fetch(`/api/s3/buckets/${bucketName}/versioning`);
    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }
    const data = await response.json();
    return data.Status === 'Enabled';
}

async function setVersioning(bucketName, enabled) {
    const response = await fetch(`/api/s3/buckets/${bucketName}/versioning`, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            VersioningEnabled: enabled
        })
    });
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Failed to update versioning');
    }
}

async function listVersions(bucketName, objectKey) {
    const response = await fetch(`/api/s3/buckets/${bucketName}/objects/${objectKey}/versions`);
    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }
    const data = await response.json();
    return data.Versions || [];
}

async function getObjectVersion(bucketName, objectKey, versionId) {
    const response = await fetch(`/api/s3/buckets/${bucketName}/objects/${objectKey}?versionId=${versionId}`);
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Failed to get version');
    }
    return response.blob();
}

async function deleteObjectVersion(bucketName, objectKey, versionId) {
    const response = await fetch(`/api/s3/buckets/${bucketName}/objects/${objectKey}?versionId=${versionId}`, {
        method: 'DELETE'
    });
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Failed to delete version');
    }
}

// UI update functions
async function refreshBuckets() {
    try {
        const buckets = await listBuckets();
        const bucketList = document.getElementById('bucketList');
        bucketList.innerHTML = buckets.map(bucket => `
            <a href="#" class="list-group-item list-group-item-action d-flex justify-content-between align-items-center ${bucket === currentBucket ? 'active' : ''}"
               onclick="selectBucket('${bucket}')">
                <span><i class="fas fa-folder me-2"></i>${bucket}</span>
                <button class="btn btn-sm btn-danger" onclick="event.stopPropagation(); deleteBucket('${bucket}')">
                    <i class="fas fa-trash"></i>
                </button>
            </a>
        `).join('');
    } catch (error) {
        alert('Error refreshing buckets: ' + error.message);
    }
}

async function refreshCurrentBucket() {
    if (!currentBucket) return;

    try {
        // Update versioning switch
        const versioning = await getVersioning(currentBucket);
        document.getElementById('versioningSwitch').checked = versioning;

        // Update objects list
        const objects = await listObjects(currentBucket);
        const objectsList = document.getElementById('objectsList');
        objectsList.innerHTML = objects.map(object => `
            <tr>
                <td><i class="fas fa-file me-2"></i>${object}</td>
                <td>-</td>
                <td>-</td>
                <td>
                    <div class="btn-group btn-group-sm">
                        <button class="btn btn-outline-primary" onclick="downloadObject('${object}')">
                            <i class="fas fa-download"></i>
                        </button>
                        <button class="btn btn-outline-info" onclick="showVersions('${object}')">
                            <i class="fas fa-history"></i>
                        </button>
                        <button class="btn btn-outline-danger" onclick="deleteObject('${currentBucket}', '${object}')">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `).join('');
    } catch (error) {
        alert('Error refreshing bucket: ' + error.message);
    }
}

async function selectBucket(bucketName) {
    currentBucket = bucketName;
    document.getElementById('currentBucketName').textContent = bucketName;
    document.getElementById('welcomeMessage').style.display = 'none';
    document.getElementById('bucketInfo').style.display = 'block';
    refreshBuckets();
    refreshCurrentBucket();
}

function showWelcomeMessage() {
    document.getElementById('welcomeMessage').style.display = 'block';
    document.getElementById('bucketInfo').style.display = 'none';
}

async function showVersions(objectKey) {
    try {
        const versions = await listVersions(currentBucket, objectKey);
        const versionsList = document.getElementById('versionsList');
        versionsList.innerHTML = versions.map(version => `
            <tr>
                <td>${version.VersionId}</td>
                <td>${formatDate(version.LastModified)}</td>
                <td>${formatSize(version.Size)}</td>
                <td>
                    <div class="btn-group btn-group-sm">
                        <button class="btn btn-outline-primary" onclick="downloadVersion('${objectKey}', '${version.VersionId}')">
                            <i class="fas fa-download"></i>
                        </button>
                        <button class="btn btn-outline-danger" onclick="deleteVersion('${objectKey}', '${version.VersionId}')">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `).join('');
        versionModal.show();
    } catch (error) {
        alert('Error showing versions: ' + error.message);
    }
}

// Event handlers
document.getElementById('versioningSwitch').addEventListener('change', async function(e) {
    try {
        await setVersioning(currentBucket, e.target.checked);
    } catch (error) {
        alert('Error updating versioning: ' + error.message);
        e.target.checked = !e.target.checked;
    }
});

const uploadZone = document.getElementById('uploadZone');
const fileInput = document.getElementById('fileInput');
const progressBar = document.querySelector('.progress');
const progressBarInner = document.querySelector('.progress-bar');

uploadZone.addEventListener('click', () => fileInput.click());

uploadZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadZone.classList.add('dragover');
});

uploadZone.addEventListener('dragleave', () => {
    uploadZone.classList.remove('dragover');
});

uploadZone.addEventListener('drop', async (e) => {
    e.preventDefault();
    uploadZone.classList.remove('dragover');
    const files = e.dataTransfer.files;
    handleFiles(files);
});

fileInput.addEventListener('change', () => {
    handleFiles(fileInput.files);
});

async function handleFiles(files) {
    if (!currentBucket) return;

    progressBar.style.display = 'block';
    let completed = 0;

    for (const file of files) {
        try {
            await uploadFile(file, currentBucket);
            completed++;
            progressBarInner.style.width = `${(completed / files.length) * 100}%`;
        } catch (error) {
            alert(`Error uploading ${file.name}: ${error.message}`);
        }
    }

    setTimeout(() => {
        progressBar.style.display = 'none';
        progressBarInner.style.width = '0%';
    }, 1000);

    refreshCurrentBucket();
}

async function downloadObject(objectKey) {
    try {
        const response = await fetch(`/api/s3/buckets/${currentBucket}/objects/${objectKey}`);
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Failed to download object');
        }
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = objectKey;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
    } catch (error) {
        alert('Error downloading object: ' + error.message);
    }
}

async function downloadVersion(objectKey, versionId) {
    try {
        const blob = await getObjectVersion(currentBucket, objectKey, versionId);
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${objectKey}_${versionId}`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
    } catch (error) {
        alert('Error downloading version: ' + error.message);
    }
}

async function deleteVersion(objectKey, versionId) {
    if (!confirm('Are you sure you want to delete this version?')) return;

    try {
        await deleteObjectVersion(currentBucket, objectKey, versionId);
        showVersions(objectKey);
        refreshCurrentBucket();
    } catch (error) {
        alert('Error deleting version: ' + error.message);
    }
}

// Initialize
refreshBuckets();
