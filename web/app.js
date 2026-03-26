// Deer Detection System - Frontend JavaScript

// --- REMOTE LOGGING ---
function remoteLog(level, message) {
    console[level](message);
    fetch('/api/client_log', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ level: level, message: message })
    }).catch(e => console.error('Remote log failed:', e));
}

// Global error handler
window.onerror = function(message, source, lineno, colno, error) {
    remoteLog('error', `JS Error: ${message} at ${source}:${lineno}:${colno}`);
    return false;
};

// Start logging early
remoteLog('info', 'app.js script execution started (Remote Logging Active)');
// -----------------------

// --- HEARTBEAT TEST ---
document.addEventListener('DOMContentLoaded', () => {
    const statusEl = document.getElementById('system-status');
    if (statusEl) {
        statusEl.textContent = 'Script Loaded (Remote Active)...';
        statusEl.style.backgroundColor = '#9C27B0'; // Purple for remote logging
    }
});
// -----------------------

// WebSocket connection
let socket;
let isConnected = false;

// UI Elements (Initialized safely)
let elements = {};

function initElements() {
    elements = {
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
        pirStatus: document.getElementById('pir-status'),

        // Buttons
        btnEnable: document.getElementById('btn-enable'),
        btnDisable: document.getElementById('btn-disable'),
        btnToggleCamera: document.getElementById('btn-toggle-camera'),
        btnStopSprinkler: document.getElementById('btn-stop-sprinkler'),
        btnTestSprinkler: document.getElementById('btn-test-sprinkler'),
        btnTriggerMotion: document.getElementById('btn-trigger-motion'),
        btnCloudSync: document.getElementById('btn-cloud-sync')
    };
    console.log('[DEBUG] UI Elements initialized');
}

// Camera state
let cameraActive = false;
let cameraKeepAliveInterval = null;

// Initialize WebSocket connection
function connectWebSocket() {
    console.log('[DEBUG] Connecting to WebSocket...');

    try {
        socket = io({
            transports: ['polling', 'websocket'],
            reconnection: true,
            reconnectionDelay: 1000,
            reconnectionAttempts: 10
        });

        socket.on('connect', () => {
            console.log('[DEBUG] ✅ WebSocket connected! Socket ID:', socket.id);
            isConnected = true;
            updateConnectionStatus(true);
            addLogEntry('system', 'Connected to server');
        });

        socket.on('disconnect', () => {
            console.log('[DEBUG] ❌ WebSocket disconnected');
            isConnected = false;
            updateConnectionStatus(false);
            addLogEntry('error', 'Disconnected from server');
        });

        socket.on('connect_error', (error) => {
            console.error('[DEBUG] ❌ WebSocket connection error:', error);
            addLogEntry('error', 'Connection error: ' + error.message);
        });

        socket.on('connect_timeout', () => {
            console.error('[DEBUG] ⏱️ WebSocket connection timeout');
            addLogEntry('error', 'Connection timeout');
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

        socket.on('camera_status', (data) => {
            handleCameraStatus(data);
        });

        socket.on('motion_status', (data) => {
            handleMotionStatus(data);
        });
    } catch (error) {
        console.error('[DEBUG] ❌ WebSocket initialization error:', error);
        addLogEntry('error', 'WebSocket initialization error: ' + error.message);
    }
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
    if (status.valve_api_error) {
        elements.valveStatus.textContent = 'API Error';
        elements.valveStatus.className = 'status-badge disabled';
        elements.valveStatus.title = status.valve_api_error;
    } else if (status.valve_on) {
        elements.valveStatus.textContent = 'ON';
        elements.valveStatus.className = 'status-badge enabled';
        elements.valveStatus.title = '';
    } else {
        elements.valveStatus.textContent = 'OFF';
        elements.valveStatus.className = 'status-badge disabled';
        elements.valveStatus.title = '';
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

    // Initial motion status
    handleMotionStatus({ active: status.motion_active });
}

// Handle motion status updates
function handleMotionStatus(data) {
    if (!elements.pirStatus) return;

    if (data.active) {
        elements.pirStatus.textContent = 'MOTION DETECTED';
        elements.pirStatus.className = 'status-badge enabled';
    } else {
        elements.pirStatus.textContent = 'NO MOTION';
        elements.pirStatus.className = 'status-badge disabled';
    }
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

// Handle camera status updates
function handleCameraStatus(data) {
    console.log('Camera status:', data);

    if (data.active) {
        // Camera is streaming - hide overlay
        if (elements.noFeedMessage) {
            elements.noFeedMessage.style.display = 'none';
        }
        addLogEntry('camera', '📷 ESP32-CAM active - streaming');
    } else {
        // Camera went to sleep - show overlay
        if (elements.noFeedMessage) {
            elements.noFeedMessage.style.display = 'flex';
        }
        addLogEntry('camera', '💤 ESP32-CAM sleeping');
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
function setupEventListeners() {
    if (!elements.btnEnable) {
        console.error('btnEnable missing from elements');
        return;
    }

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

    if (elements.btnStopSprinkler) {
        elements.btnStopSprinkler.addEventListener('click', async () => {
            if (confirm('Emergency stop sprinkler?')) {
                addLogEntry('emergency', 'Emergency stop triggered');
                const result = await apiCall('/sprinkler/off', 'POST');
                if (!result.success) {
                    addLogEntry('error', 'Failed to stop sprinkler');
                }
            }
        });
    }

    if (elements.btnTestSprinkler) {
        elements.btnTestSprinkler.addEventListener('click', async () => {
            if (confirm('Test sprinkler for 10 seconds?')) {
                addLogEntry('manual', 'Testing sprinkler (10s)');
                const result = await apiCall('/sprinkler/on', 'POST', { duration: 10 });
                if (!result.success) {
                    addLogEntry('error', 'Failed to activate sprinkler');
                }
            }
        });
    }

    if (elements.btnTriggerMotion) {
        elements.btnTriggerMotion.addEventListener('click', async () => {
            addLogEntry('manual', 'Manual motion trigger');
            const result = await apiCall('/trigger', 'POST');
            if (!result.success) {
                addLogEntry('warning', result.message || 'Trigger ignored');
            }
        });
    }

    if (elements.btnCloudSync) {
        elements.btnCloudSync.addEventListener('click', async () => {
            addLogEntry('system', '☁️ Requesting Cloud API Status Sync...');
            elements.btnCloudSync.disabled = true;
            elements.btnCloudSync.textContent = '⏳ Syncing...';
            
            try {
                const result = await apiCall('/api/devices/refresh', 'POST');
                if (result.success) {
                    addLogEntry('success', '✅ Cloud Status Synced Successfully');
                    if (result.api_error) {
                        addLogEntry('error', `Cloud Error: ${result.api_error}`);
                    }
                } else {
                    addLogEntry('error', `Cloud Sync Failed: ${result.error || 'Unknown error'}`);
                }
            } catch (e) {
                addLogEntry('error', `Cloud Sync Error: ${e.message}`);
            } finally {
                elements.btnCloudSync.disabled = false;
                elements.btnCloudSync.textContent = '🔄 Sync Valve Status (Cloud)';
                pollStatus(); // Immediate refresh of UI
            }
        });
    }
    
    console.log('[DEBUG] Event listeners setup complete');
}

// Poll status periodically
async function pollStatus() {
    // We want to poll even if WebSocket is not connected (as a fallback)
    const status = await apiCall('/status');
    if (status && !status.error) {
        // If we got status successfully, we can consider it "connected" for UI purposes
        // although we don't want to set isConnected to true as that's for the socket
        updateStatus(status);
    }
}

// Check video feed
function checkVideoFeed() {
    // Monitor when video feed starts/stops loading
    let frameReceived = false;

    elements.videoFeed.addEventListener('load', () => {
        if (!frameReceived) {
            frameReceived = true;
            console.log('Video feed: First frame received');
            if (elements.noFeedMessage) {
                elements.noFeedMessage.style.display = 'none';
            }
        }
    });

    elements.videoFeed.addEventListener('error', () => {
        console.log('Video feed: Error loading');
        if (elements.noFeedMessage) {
            elements.noFeedMessage.style.display = 'flex';
        }
    });

    // Check if video is actually playing (receiving frames)
    setInterval(() => {
        // If we have a video feed src and it's not showing error
        if (elements.videoFeed.complete && elements.videoFeed.naturalHeight !== 0) {
            if (elements.noFeedMessage && elements.noFeedMessage.style.display !== 'none') {
                elements.noFeedMessage.style.display = 'none';
            }
        }
    }, 2000);
}

// Load recent logs from server
async function loadRecentLogs() {
    console.log('[DEBUG] Loading recent logs...');
    try {
        const response = await fetch('/api/logs');
        console.log('[DEBUG] Logs response status:', response.status);

        const logs = await response.json();
        console.log('[DEBUG] Loaded logs:', logs.length, 'entries');

        // Clear placeholder
        if (elements.eventLog) {
            elements.eventLog.innerHTML = '';
        } else {
            console.error('[DEBUG] eventLog element not found!');
            return;
        }

        // Add logs (they come in chronological order, but we want newest first)
        if (logs && logs.length > 0) {
            // Reverse to show newest first
            logs.reverse().forEach(log => {
                const timestamp = new Date(log.timestamp).toLocaleTimeString();
                const entry = document.createElement('div');
                entry.className = `log-entry ${log.type}`;
                entry.innerHTML = `
                    <span class="log-time">${timestamp}</span>
                    <span class="log-message">${log.message}</span>
                `;
                elements.eventLog.appendChild(entry);
            });
            console.log('[DEBUG] Added', logs.length, 'log entries to display');
        } else {
            // No logs yet
            console.log('[DEBUG] No logs available, adding placeholder');
            addLogEntry('system', 'System initialized - waiting for events...');
        }
    } catch (error) {
        console.error('[DEBUG] Failed to load logs:', error);
        addLogEntry('error', 'Failed to load event history');
        addLogEntry('system', 'Connected - ready for monitoring');
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    console.log('[DEBUG] ========================================');
    console.log('[DEBUG] Deer Detection System UI initializing...');
    console.log('[DEBUG] ========================================');
    
    // Initialize elements first!
    initElements();
    
    // Setup listeners!
    setupEventListeners();
    
    console.log('[DEBUG] Elements check:');
    console.log('[DEBUG] - eventLog:', elements.eventLog ? 'FOUND' : 'MISSING');
    console.log('[DEBUG] - systemStatus:', elements.systemStatus ? 'FOUND' : 'MISSING');
    console.log('[DEBUG] - connectionIndicator:', elements.connectionIndicator ? 'FOUND' : 'MISSING');

    // Load recent logs first
    try {
        console.log('[DEBUG] Step 1: Loading recent logs...');
        loadRecentLogs();
    } catch (e) { console.error('Step 1 failed:', e); }

    // Connect WebSocket
    try {
        console.log('[DEBUG] Step 2: Connecting WebSocket...');
        if (typeof io !== 'undefined') {
            connectWebSocket();
        } else {
            console.error('[DEBUG] ❌ Socket.IO library not found!');
            addLogEntry('error', 'Socket.IO library failed to load');
        }
    } catch (e) { console.error('Step 2 failed:', e); }

    // Set up video feed
    try {
        console.log('[DEBUG] Step 3: Setting up video feed...');
        checkVideoFeed();
    } catch (e) { console.error('Step 3 failed:', e); }

    // Hide overlay
    if (elements.noFeedMessage) {
        elements.noFeedMessage.style.display = 'none';
        elements.noFeedMessage.style.visibility = 'hidden';
    }

    // Start status polling
    try {
        console.log('[DEBUG] Step 4: Starting status polling...');
        // Poll status every 5 seconds as backup
        setInterval(pollStatus, 5000);
        
        // Initial status poll
        console.log('[DEBUG] Step 5: Initial status poll...');
        pollStatus();
    } catch (e) { console.error('Step 4/5 failed:', e); }

    console.log('[DEBUG] ========================================');
    console.log('[DEBUG] Initialization complete!');
    console.log('[DEBUG] ========================================');
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
