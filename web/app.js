// Deer Detection System - Frontend JavaScript

// WebSocket connection
let socket;
let isConnected = false;

// UI Elements
const elements = {
    systemStatus: document.getElementById('system-status'),
    valveStatus: document.getElementById('valve-status'),
    lastDetection: document.getElementById('last-detection'),
    sessionDetections: document.getElementById('session-detections'),
    cooldownStatus: document.getElementById('cooldown-status'),
    eventLog: document.getElementById('event-log'),
    connectionIndicator: document.getElementById('connection-indicator'),
    connectionText: document.getElementById('connection-text'),
    videoFeed: document.getElementById('video-feed'),
    noFeedMessage: document.getElementById('no-feed-message'),

    // Buttons
    btnEnable: document.getElementById('btn-enable'),
    btnDisable: document.getElementById('btn-disable'),
    btnToggleCamera: document.getElementById('btn-toggle-camera'),
    btnStopSprinkler: document.getElementById('btn-stop-sprinkler'),
    btnTestSprinkler: document.getElementById('btn-test-sprinkler'),
    btnTriggerMotion: document.getElementById('btn-trigger-motion')
};

// Camera state
let cameraActive = false;
let cameraKeepAliveInterval = null;

// Initialize WebSocket connection
function connectWebSocket() {
    console.log('Connecting to WebSocket...');

    socket = io();

    socket.on('connect', () => {
        console.log('WebSocket connected');
        isConnected = true;
        updateConnectionStatus(true);
        addLogEntry('system', 'Connected to server');
    });

    socket.on('disconnect', () => {
        console.log('WebSocket disconnected');
        isConnected = false;
        updateConnectionStatus(false);
        addLogEntry('error', 'Disconnected from server');
    });

    socket.on('status', (data) => {
        updateStatus(data);
    });

    socket.on('state', (data) => {
        updateSystemState(data.state);
    });

    socket.on('event', (data) => {
        handleEvent(data);
    });
}

// Update connection status indicator
function updateConnectionStatus(connected) {
    if (connected) {
        elements.connectionIndicator.textContent = '🟢';
        elements.connectionIndicator.className = 'indicator connected';
        elements.connectionText.textContent = 'Connected';
    } else {
        elements.connectionIndicator.textContent = '🔴';
        elements.connectionIndicator.className = 'indicator disconnected';
        elements.connectionText.textContent = 'Disconnected';
    }
}

// Update system status
function updateStatus(status) {
    console.log('Status update:', status);

    // System state
    updateSystemState(status.state);

    // Valve status
    if (status.valve_on) {
        elements.valveStatus.textContent = 'ON';
        elements.valveStatus.className = 'status-badge enabled';
    } else {
        elements.valveStatus.textContent = 'OFF';
        elements.valveStatus.className = 'status-badge disabled';
    }

    // Last detection
    if (status.last_detection) {
        const date = new Date(status.last_detection);
        elements.lastDetection.textContent = date.toLocaleTimeString();
    } else {
        elements.lastDetection.textContent = 'Never';
    }

    // Session info
    elements.sessionDetections.textContent = status.session_detections || 0;

    // Cooldown
    if (status.cooldown_remaining > 0) {
        elements.cooldownStatus.textContent = `${status.cooldown_remaining}s`;
        elements.cooldownStatus.style.color = '#ffa726';
    } else {
        elements.cooldownStatus.textContent = 'None';
        elements.cooldownStatus.style.color = '#00c853';
    }

    // Update button states
    updateButtonStates(status);
}

// Update system state
function updateSystemState(state) {
    const stateMap = {
        'disabled': { text: 'Disabled', class: 'disabled' },
        'idle': { text: 'Armed', class: 'enabled' },
        'active': { text: 'Active', class: 'active' },
        'deer_detected': { text: 'Deer Detected!', class: 'active' },
        'sprinkler_on': { text: 'Sprinkler Active', class: 'enabled' },
        'cooldown': { text: 'Cooldown', class: 'active' }
    };

    const stateInfo = stateMap[state] || { text: state, class: '' };
    elements.systemStatus.textContent = stateInfo.text;
    elements.systemStatus.className = `status-badge ${stateInfo.class}`;
}

// Update button states based on system status
function updateButtonStates(status) {
    // Enable/Disable buttons
    if (status.enabled) {
        elements.btnEnable.disabled = true;
        elements.btnDisable.disabled = false;
    } else {
        elements.btnEnable.disabled = false;
        elements.btnDisable.disabled = true;
    }

    // Sprinkler controls
    const canControlSprinkler = status.valve_configured && isConnected;
    elements.btnStopSprinkler.disabled = !canControlSprinkler;
    elements.btnTestSprinkler.disabled = !canControlSprinkler || status.valve_on;

    // Manual trigger
    elements.btnTriggerMotion.disabled = !status.enabled || !isConnected;
}

// Handle events from server
function handleEvent(event) {
    console.log('Event:', event);

    const eventType = event.type || 'info';
    addLogEntry(eventType, event.message);

    // Play sound for deer detection (optional)
    if (eventType === 'detection' && event.message.includes('Deer detected')) {
        playAlert();
    }
}

// Add entry to event log
function addLogEntry(type, message) {
    const timestamp = new Date().toLocaleTimeString();
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    entry.innerHTML = `
        <span class="log-time">${timestamp}</span>
        <span class="log-message">${message}</span>
    `;

    elements.eventLog.insertBefore(entry, elements.eventLog.firstChild);

    // Keep only last 100 entries
    while (elements.eventLog.children.length > 100) {
        elements.eventLog.removeChild(elements.eventLog.lastChild);
    }
}

// Play alert sound (optional)
function playAlert() {
    // You can implement audio alert here
    console.log('ALERT: Deer detected!');
}

// API call helper
async function apiCall(endpoint, method = 'GET', data = null) {
    try {
        const options = {
            method: method,
            headers: {
                'Content-Type': 'application/json'
            }
        };

        if (data && method !== 'GET') {
            options.body = JSON.stringify(data);
        }

        const response = await fetch(`/api${endpoint}`, options);
        const result = await response.json();

        return result;
    } catch (error) {
        console.error('API call failed:', error);
        addLogEntry('error', `API call failed: ${error.message}`);
        return { success: false, error: error.message };
    }
}

// Button event handlers
elements.btnEnable.addEventListener('click', async () => {
    addLogEntry('system', 'Enabling system...');
    const result = await apiCall('/system/enable', 'POST');
    if (!result.success) {
        addLogEntry('error', 'Failed to enable system');
    }
});

elements.btnDisable.addEventListener('click', async () => {
    addLogEntry('system', 'Disabling system...');
    const result = await apiCall('/system/disable', 'POST');
    if (!result.success) {
        addLogEntry('error', 'Failed to disable system');
    }
});

elements.btnToggleCamera.addEventListener('click', async () => {
    if (!cameraActive) {
        // Activate camera
        addLogEntry('camera', 'Activating live camera feed...');
        const result = await apiCall('/trigger', 'POST');

        if (result.success !== false) {
            cameraActive = true;
            elements.btnToggleCamera.textContent = '⏹️ Stop Camera';
            elements.btnToggleCamera.classList.remove('btn-secondary');
            elements.btnToggleCamera.classList.add('btn-warning');
            elements.noFeedMessage.style.display = 'none';

            // Keep camera alive by polling status
            cameraKeepAliveInterval = setInterval(() => {
                if (cameraActive) {
                    pollStatus();
                }
            }, 3000);

            addLogEntry('camera', 'Camera feed active');
        }
    } else {
        // Deactivate camera
        cameraActive = false;
        elements.btnToggleCamera.textContent = '📹 View Live Camera';
        elements.btnToggleCamera.classList.remove('btn-warning');
        elements.btnToggleCamera.classList.add('btn-secondary');

        if (cameraKeepAliveInterval) {
            clearInterval(cameraKeepAliveInterval);
            cameraKeepAliveInterval = null;
        }

        addLogEntry('camera', 'Camera feed stopped');
    }
});

elements.btnStopSprinkler.addEventListener('click', async () => {
    if (confirm('Emergency stop sprinkler?')) {
        addLogEntry('emergency', 'Emergency stop triggered');
        const result = await apiCall('/sprinkler/off', 'POST');
        if (!result.success) {
            addLogEntry('error', 'Failed to stop sprinkler');
        }
    }
});

elements.btnTestSprinkler.addEventListener('click', async () => {
    if (confirm('Test sprinkler for 10 seconds?')) {
        addLogEntry('manual', 'Testing sprinkler (10s)');
        const result = await apiCall('/sprinkler/on', 'POST', { duration: 10 });
        if (!result.success) {
            addLogEntry('error', 'Failed to activate sprinkler');
        }
    }
});

elements.btnTriggerMotion.addEventListener('click', async () => {
    addLogEntry('manual', 'Manual motion trigger');
    const result = await apiCall('/trigger', 'POST');
    if (!result.success) {
        addLogEntry('warning', result.message || 'Trigger ignored');
    }
});

// Poll status periodically
async function pollStatus() {
    if (isConnected) {
        const status = await apiCall('/status');
        if (status && !status.error) {
            updateStatus(status);
        }
    }
}

// Check video feed
function checkVideoFeed() {
    elements.videoFeed.onerror = () => {
        elements.noFeedMessage.style.display = 'flex';
    };

    elements.videoFeed.onload = () => {
        elements.noFeedMessage.style.display = 'none';
    };
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    console.log('Deer Detection System UI initializing...');

    connectWebSocket();
    checkVideoFeed();

    // Hide overlay since we're using direct stream URL
    // Use multiple methods to ensure it's hidden
    if (elements.noFeedMessage) {
        elements.noFeedMessage.style.display = 'none';
        elements.noFeedMessage.style.visibility = 'hidden';
        elements.noFeedMessage.style.opacity = '0';
        elements.noFeedMessage.classList.add('hidden');
    }

    // Poll status every 5 seconds as backup
    setInterval(pollStatus, 5000);

    addLogEntry('system', 'UI loaded successfully');
});

// Handle page visibility
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        console.log('Page hidden');
    } else {
        console.log('Page visible - refreshing status');
        pollStatus();
    }
});
