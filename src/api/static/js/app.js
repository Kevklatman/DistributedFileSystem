// Main application code
document.addEventListener('DOMContentLoaded', () => {
    const root = document.getElementById('root');
    
    // Create main container
    const container = document.createElement('div');
    container.innerHTML = `
        <h1>Distributed File System</h1>
        <div id="error" class="error" style="display: none;"></div>
        <div id="buckets"></div>
    `;
    root.appendChild(container);

    // Fetch and display buckets
    fetchBuckets();
});

async function fetchBuckets() {
    console.log('Fetching buckets...');
    try {
        const response = await fetch('/', {
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

function displayBuckets(buckets) {
    const bucketsContainer = document.getElementById('buckets');
    if (!buckets || buckets.length === 0) {
        bucketsContainer.innerHTML = '<p>No buckets found. Create one to get started!</p>';
        return;
    }

    const bucketsList = buckets.map(bucket => `
        <div class="bucket">
            <h3>${bucket.name}</h3>
            ${bucket.creation_date ? 
                `<p>Created: ${new Date(bucket.creation_date).toLocaleString()}</p>` : 
                ''}
        </div>
    `).join('');

    bucketsContainer.innerHTML = bucketsList;
}

function displayError(message) {
    const errorDiv = document.getElementById('error');
    errorDiv.textContent = message;
    errorDiv.style.display = 'block';
    
    // Clear buckets display
    const bucketsContainer = document.getElementById('buckets');
    bucketsContainer.innerHTML = '';
}
