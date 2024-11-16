// Main application code
document.addEventListener('DOMContentLoaded', () => {
    const root = document.getElementById('root');
    
    // Create main container
    const container = document.createElement('div');
    container.innerHTML = `
        <h1>Distributed File System</h1>
        <div id="buckets"></div>
    `;
    root.appendChild(container);

    // Fetch and display buckets
    fetchBuckets();
});

async function fetchBuckets() {
    try {
        const response = await fetch('/', {
            headers: {
                'Accept': 'application/json'
            }
        });
        const data = await response.json();
        
        if (data.error) {
            displayError(data.error);
            return;
        }

        displayBuckets(data.buckets);
    } catch (error) {
        displayError('Error fetching buckets: ' + error.message);
    }
}

function displayBuckets(buckets) {
    const bucketsContainer = document.getElementById('buckets');
    if (!buckets || buckets.length === 0) {
        bucketsContainer.innerHTML = '<p>No buckets found.</p>';
        return;
    }

    const bucketsList = buckets.map(bucket => `
        <div class="bucket">
            <h3>${bucket.Name}</h3>
            <p>Created: ${new Date(bucket.CreationDate).toLocaleString()}</p>
        </div>
    `).join('');

    bucketsContainer.innerHTML = bucketsList;
}

function displayError(message) {
    const bucketsContainer = document.getElementById('buckets');
    bucketsContainer.innerHTML = `<p class="error">${message}</p>`;
}
