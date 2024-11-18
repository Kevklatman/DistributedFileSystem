// Make sure the script is loaded
console.log('Main.js loading...');

// Global state
let currentBucket = null;

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

// Utility function to safely get elements
function getElement(id) {
    const element = document.getElementById(id);
    if (!element) {
        console.warn(`Element with id '${id}' not found`);
    }
    return element;
}

// API functions
async function listBuckets() {
    try {
        console.log('Fetching buckets...');
        const response = await fetch('/s3/', {
            headers: {
                'Accept': 'application/json'
            }
        });
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        console.log('Received bucket data:', data);
        return data.buckets || [];
    } catch (error) {
        console.error('Error in listBuckets:', error);
        throw error;
    }
}

async function createBucket() {
    const bucketName = document.getElementById('newBucketName').value.trim();
    if (!bucketName) return;

    try {
        const response = await fetch(`/s3/${bucketName}`, {
            method: 'PUT'
        });
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        await refreshBuckets();
        document.getElementById('newBucketName').value = '';
    } catch (error) {
        console.error('Error creating bucket:', error);
        alert('Failed to create bucket: ' + error.message);
    }
}

async function deleteBucket(bucketName) {
    if (!confirm(`Are you sure you want to delete bucket "${bucketName}"?`)) {
        return;
    }

    try {
        const response = await fetch(`/s3/${bucketName}`, {
            method: 'DELETE'
        });
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        await refreshBuckets();
        if (currentBucket === bucketName) {
            currentBucket = null;
            showWelcomeMessage();
        }
    } catch (error) {
        console.error('Error deleting bucket:', error);
        alert('Failed to delete bucket: ' + error.message);
    }
}

async function listObjects(bucketName) {
    try {
        const response = await fetch(`/s3/${bucketName}`, {
            headers: {
                'Accept': 'application/json'
            }
        });
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        return data.objects || [];
    } catch (error) {
        console.error('Error listing objects:', error);
        throw error;
    }
}

async function uploadFile(file, bucketName) {
    try {
        const response = await fetch(`/s3/${bucketName}/${file.name}`, {
            method: 'PUT',
            body: file
        });
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return true;
    } catch (error) {
        console.error('Error uploading file:', error);
        throw error;
    }
}

async function deleteObject(bucketName, objectKey) {
    try {
        const response = await fetch(`/s3/${bucketName}/${objectKey}`, {
            method: 'DELETE'
        });
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
    } catch (error) {
        console.error('Error deleting object:', error);
        throw error;
    }
}

async function getVersioning(bucketName) {
    try {
        const response = await fetch(`/s3/${bucketName}?versioning`, {
            headers: {
                'Accept': 'application/json'
            }
        });
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        return data.status === 'Enabled';
    } catch (error) {
        console.error('Error getting versioning status:', error);
        return false;
    }
}

async function setVersioning(bucketName, enabled) {
    try {
        const response = await fetch(`/s3/${bucketName}?versioning`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify({
                status: enabled ? 'Enabled' : 'Suspended'
            })
        });
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
    } catch (error) {
        console.error('Error setting versioning:', error);
        throw error;
    }
}

async function listVersions(bucketName, objectKey) {
    try {
        const response = await fetch(`/s3/${bucketName}/${objectKey}?versions`, {
            headers: {
                'Accept': 'application/json'
            }
        });
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        return data.versions || [];
    } catch (error) {
        console.error('Error listing versions:', error);
        throw error;
    }
}

async function getObjectVersion(bucketName, objectKey, versionId) {
    try {
        const response = await fetch(`/s3/${bucketName}/${objectKey}?versionId=${versionId}`, {
            headers: {
                'Accept': 'application/json'
            }
        });
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response;
    } catch (error) {
        console.error('Error getting object version:', error);
        throw error;
    }
}

async function deleteObjectVersion(bucketName, objectKey, versionId) {
    try {
        const response = await fetch(`/s3/${bucketName}/${objectKey}?versionId=${versionId}`, {
            method: 'DELETE'
        });
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
    } catch (error) {
        console.error('Error deleting object version:', error);
        throw error;
    }
}

// Dashboard Metrics functions
async function fetchDashboardMetrics() {
    try {
        console.log('Fetching dashboard metrics...');
        const response = await fetch('/dashboard/metrics', {
            headers: {
                'Accept': 'application/json'
            }
        });
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const metrics = await response.json();
        console.log('Received metrics:', metrics);
        updateDashboardUI(metrics);
    } catch (error) {
        console.error('Error fetching metrics:', error);
    }
}

function updateDashboardUI(metrics) {
    try {
        console.log('Updating UI with metrics:', metrics);

        // System Health
        const elements = {
            'cpu-usage': metrics.health.cpu_usage.toFixed(1) + '%',
            'memory-usage': metrics.health.memory_usage.toFixed(1) + '%',
            'io-latency': metrics.health.io_latency_ms.toFixed(1) + ' ms',
            'network-bandwidth': metrics.health.network_bandwidth_mbps.toFixed(1) + ' Mbps',
            'storage-usage': metrics.storage.usage_percent.toFixed(1) + '%',
            'dedup-ratio': metrics.storage.dedup_ratio.toFixed(2) + 'x',
            'compression-ratio': metrics.storage.compression_ratio.toFixed(2) + 'x',
            'iops': metrics.storage.iops,
            'bytes-in': formatSize(metrics.storage.bytes_in),
            'bytes-out': formatSize(metrics.storage.bytes_out),
            'total-cost': '$' + metrics.cost.total_cost_month.toFixed(2),
            'total-savings': '$' + metrics.cost.total_savings.toFixed(2),
            'ml-accuracy': (metrics.policy.ml_policy_accuracy * 100).toFixed(1) + '%',
            'data-moved': metrics.policy.data_moved_24h_gb.toFixed(1) + ' GB'
        };

        // Update each element if it exists
        Object.entries(elements).forEach(([id, value]) => {
            const element = getElement(id);
            if (element) {
                element.textContent = value;
            }
        });

        // Update recommendations
        const recsContainer = getElement('recommendations');
        if (recsContainer) {
            recsContainer.innerHTML = '';
            metrics.recommendations.forEach(rec => {
                const recElement = document.createElement('div');
                recElement.className = `alert alert-${rec.severity}`;
                recElement.innerHTML = `
                    <h5>${rec.title}</h5>
                    <p>${rec.description}</p>
                    <ul>
                        ${rec.suggestions.map(s => `<li>${s}</li>`).join('')}
                    </ul>
                `;
                recsContainer.appendChild(recElement);
            });
        }
        console.log('UI update complete');
    } catch (error) {
        console.error('Error updating UI:', error);
        console.error('Error details:', error.message);
        console.error('Stack trace:', error.stack);
    }
}

// UI update functions
async function refreshBuckets() {
    try {
        const buckets = await listBuckets();
        const bucketList = getElement('bucketList');
        if (bucketList) {
            bucketList.innerHTML = '';

            buckets.forEach(bucket => {
                const bucketName = bucket.Name || bucket.name; // Support both Name and name fields
                const li = document.createElement('li');
                li.className = 'list-group-item d-flex justify-content-between align-items-center';
                li.innerHTML = `
                    <span class="bucket-name" onclick="selectBucket('${bucketName}')">${bucketName}</span>
                    <button class="btn btn-danger btn-sm" onclick="deleteBucket('${bucketName}')">Delete</button>
                `;
                bucketList.appendChild(li);
            });
        }
    } catch (error) {
        console.error('Error refreshing buckets:', error);
        alert('Error loading buckets: ' + error.message);
    }
}

async function refreshCurrentBucket() {
    if (!currentBucket) return;

    try {
        // Update versioning switch
        const versioning = await getVersioning(currentBucket);
        const versioningSwitch = getElement('versioningSwitch');
        if (versioningSwitch) {
            versioningSwitch.checked = versioning;
        }

        // Update objects list
        const objects = await listObjects(currentBucket);
        const objectsList = getElement('objectsList');
        if (objectsList) {
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
        }
    } catch (error) {
        alert('Error refreshing bucket: ' + error.message);
    }
}

async function selectBucket(bucketName) {
    currentBucket = bucketName;
    const currentBucketName = getElement('currentBucketName');
    if (currentBucketName) {
        currentBucketName.textContent = bucketName;
    }
    const welcomeMessage = getElement('welcomeMessage');
    if (welcomeMessage) {
        welcomeMessage.style.display = 'none';
    }
    const bucketInfo = getElement('bucketInfo');
    if (bucketInfo) {
        bucketInfo.style.display = 'block';
    }
    refreshBuckets();
    refreshCurrentBucket();
}

function showWelcomeMessage() {
    const welcomeMessage = getElement('welcomeMessage');
    if (welcomeMessage) {
        welcomeMessage.style.display = 'block';
    }
    const bucketInfo = getElement('bucketInfo');
    if (bucketInfo) {
        bucketInfo.style.display = 'none';
    }
}

async function showVersions(objectKey) {
    try {
        const versions = await listVersions(currentBucket, objectKey);
        const versionsList = getElement('versionsList');
        if (versionsList) {
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
        }
        const versionModal = getElement('versionModal');
        if (versionModal) {
            versionModal.show();
        }
    } catch (error) {
        alert('Error showing versions: ' + error.message);
    }
}

// Event handlers
const versioningSwitch = getElement('versioningSwitch');
if (versioningSwitch) {
    versioningSwitch.addEventListener('change', async function (e) {
        try {
            await setVersioning(currentBucket, e.target.checked);
        } catch (error) {
            alert('Error updating versioning: ' + error.message);
            e.target.checked = !e.target.checked;
        }
    });
}

const uploadZone = getElement('uploadZone');
const fileInput = getElement('fileUpload');  // Changed from 'fileInput' to 'fileUpload'
const progressBar = getElement('progressBar');
const progressBarInner = getElement('progressBarInner');

if (uploadZone) {
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
}

if (fileInput) {
    fileInput.addEventListener('change', function(e) {
        handleFiles(e.target.files);
    });
}

async function handleFiles(files) {
    if (!currentBucket) return;

    if (progressBar) {
        progressBar.style.display = 'block';
    }
    let completed = 0;

    for (const file of files) {
        try {
            await uploadFile(file, currentBucket);
            completed++;
            if (progressBarInner) {
                progressBarInner.style.width = `${(completed / files.length) * 100}%`;
            }
        } catch (error) {
            alert(`Error uploading ${file.name}: ${error.message}`);
        }
    }

    setTimeout(() => {
        if (progressBar) {
            progressBar.style.display = 'none';
        }
        if (progressBarInner) {
            progressBarInner.style.width = '0%';
        }
    }, 1000);

    refreshCurrentBucket();
}

function updateProgress(percent) {
    const progressContainer = fileInput.parentElement.querySelector('.progress');
    const progressBar = progressContainer.querySelector('.progress-bar');
    const progressText = progressBar.querySelector('span');

    if (progressContainer && progressBar && progressText) {
        progressContainer.style.display = 'block';
        progressBar.style.width = percent + '%';
        progressText.textContent = percent + '%';
    }
}

async function downloadObject(objectKey) {
    try {
        const response = await fetch(`/s3/${currentBucket}/${objectKey}`);
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
        const response = await fetch(`/s3/${currentBucket}/${objectKey}?versionId=${versionId}`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
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
        console.error('Error downloading version:', error);
        alert('Failed to download version: ' + error.message);
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

// Initialize everything after DOM is loaded
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeDashboard);
} else {
    // DOM is already ready, call the initialization function directly
    initializeDashboard();
}

async function initializeDashboard() {
    console.log('Initializing dashboard...');

    try {
        // Initialize Bootstrap components if they exist
        const versionModalElement = getElement('versionModal');
        if (versionModalElement && typeof bootstrap !== 'undefined') {
            const versionModal = new bootstrap.Modal(versionModalElement);
        }

        // Initial metrics fetch
        console.log('Fetching initial metrics...');
        await fetchDashboardMetrics();

        // Start periodic updates
        console.log('Starting periodic updates...');
        setInterval(fetchDashboardMetrics, 30000);

        // Initialize file system
        console.log('Initializing file system...');
        await refreshBuckets();

        console.log('Initialization complete');
    } catch (error) {
        console.error('Error during initialization:', error);
    }
}

console.log('Main.js loaded');
