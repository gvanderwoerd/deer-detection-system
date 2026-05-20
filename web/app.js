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
        btnTriggerMotion: document.getElementById('btn-trigger-motion'),
        btnCloudSync: document.getElementById('btn-cloud-sync'),

        // Per-camera controls
        cameraSelector: document.getElementById('camera-selector'),
        cameraStatusPanel: document.getElementById('camera-status-panel'),
        cameraStatusContent: document.getElementById('camera-status-content')
    };
    console.log('[DEBUG] UI Elements initialized');
}

// Camera state
let cameraActive = false;
let cameraKeepAliveInterval = null;
let previousMotionActive = false;  // Track previous motion state for auto-start
let selectedCameraId = null;  // Track selected camera for per-camera control
let availableCameras = [];  // List of available cameras
let cameraStatusInterval = null;  // Interval for polling camera status
let cameraStatusData = {};  // Store status data for each camera
let cameraCountdownIntervals = {};  // Store countdown intervals for each camera
let cameraDeviceDurations = {};  // Track device duration countdown for each camera

// Camera control functions
async function startCamera() {
    try {
        console.log('[CAMERA] startCamera() called');

        if (cameraActive) {
            console.log('[CAMERA] Already active, returning');
            return;  // Already active
        }

        // Use selected camera if available, otherwise use first camera
        const targetCameraId = selectedCameraId || (availableCameras.length > 0 ? availableCameras[0].id : null);

        console.log(`[CAMERA] Target camera ID: ${targetCameraId}, selectedCameraId: ${selectedCameraId}, availableCameras: ${availableCameras.length}`);

        if (!targetCameraId) {
            console.log('[CAMERA] No target camera ID');
            addLogEntry('error', 'No camera selected or available');
            return;
        }

        addLogEntry('camera', `Activating live camera feed (${selectedCameraId ? 'selected' : 'default'})...`);

        // Trigger detection on selected camera
        console.log(`[CAMERA] Calling /cameras/${targetCameraId}/trigger`);
        const result = await apiCall(`/cameras/${targetCameraId}/trigger`, 'POST');
        console.log(`[CAMERA] API response:`, JSON.stringify(result));

        // Start status polling and intervals regardless of trigger result
        // (session might already be active from server auto-trigger)
        const shouldStartPolling = result.success !== false ||
                                  (result.message && result.message.includes('already active'));

        if (shouldStartPolling) {
            cameraActive = true;
            console.log(`[CAMERA] Detection session active for camera: ${targetCameraId}`);

            if (elements.btnToggleCamera) {
                elements.btnToggleCamera.textContent = '⏹️ Stop Camera';
                elements.btnToggleCamera.classList.remove('btn-secondary');
                elements.btnToggleCamera.classList.add('btn-warning');
            }
            if (elements.noFeedMessage) {
                elements.noFeedMessage.style.display = 'none';
            }

            // Start fetching per-camera status
            if (cameraStatusInterval) {
                clearInterval(cameraStatusInterval);
            }
            cameraStatusInterval = setInterval(() => {
                if (cameraActive && targetCameraId) {
                    fetchCameraStatus(targetCameraId);
                }
            }, 1000);  // Update every second for live timers
            console.log(`[CAMERA] Status polling started for camera: ${targetCameraId}`);

            // Keep camera alive by polling status
            cameraKeepAliveInterval = setInterval(() => {
                if (cameraActive) {
                    pollStatus();
                }
            }, 3000);

            addLogEntry('camera', 'Camera feed active');

            if (result.success === false) {
                console.log(`[CAMERA] Note: ${result.message}`);
            }
        } else {
            console.log(`[CAMERA] API call failed:`, JSON.stringify(result));
            const errorMsg = result.error || result.message || 'Failed to trigger camera';
            console.log(`[CAMERA] Error: ${errorMsg}`);
            addLogEntry('error', errorMsg);
        }
    } catch (error) {
        console.error('[CAMERA] Exception in startCamera:', error);
        addLogEntry('error', `Camera error: ${error.message}`);
    }
}

function stopCamera() {
    if (!cameraActive) return;  // Already stopped

    cameraActive = false;
    if (elements.btnToggleCamera) {
        elements.btnToggleCamera.textContent = '📹 View Live Camera';
        elements.btnToggleCamera.classList.remove('btn-warning');
        elements.btnToggleCamera.classList.add('btn-secondary');
    }

    if (cameraKeepAliveInterval) {
        clearInterval(cameraKeepAliveInterval);
        cameraKeepAliveInterval = null;
    }

    if (cameraStatusInterval) {
        clearInterval(cameraStatusInterval);
        cameraStatusInterval = null;
    }

    // Clear per-camera status display
    if (elements.cameraStatusPanel) {
        elements.cameraStatusPanel.style.display = 'none';
    }

    addLogEntry('camera', 'Camera feed stopped');
}

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

        socket.on('camera_detection_status', (data) => {
            // Real-time per-camera detection status updates
            if (data.camera_id === selectedCameraId && cameraActive) {
                console.log('[DEBUG] Per-camera detection status update:', data);
                // Update status display immediately without refetch
                if (elements.cameraStatusContent) {
                    const camera = availableCameras.find(c => c.id === data.camera_id);
                    const cameraName = camera ? camera.name : data.camera_id;

                    let statusHtml = `<strong>${cameraName}</strong><br>`;

                    if (data.session_active) {
                        const elapsed = data.session_elapsed_seconds || 0;
                        const remaining = Math.max(0, (data.active_window_seconds || 60) - elapsed);
                        const detections = data.session_detections || 0;

                        statusHtml += `<div style="color: #4CAF50;">
                            <strong>🟢 DETECTION ACTIVE</strong><br>
                            Remaining: <strong>${remaining}s</strong><br>
                            Detections: <strong>${detections}</strong>
                        </div>`;
                    } else if (data.cooldown_remaining > 0) {
                        statusHtml += `<div style="color: #ffa726;">
                            <strong>⏳ COOLDOWN</strong><br>
                            Remaining: <strong>${data.cooldown_remaining}s</strong>
                        </div>`;
                    } else {
                        statusHtml += `<div style="color: #999;">
                            <strong>⚪ IDLE</strong><br>
                            Ready for detection
                        </div>`;
                    }

                    elements.cameraStatusContent.innerHTML = statusHtml;
                }
            }
        });
    } catch (error) {
        console.error('[DEBUG] ❌ WebSocket initialization error:', error);
        addLogEntry('error', 'WebSocket initialization error: ' + error.message);
    }
}

// Update connection status indicator
function updateConnectionStatus(connected) {
    if (!elements.connectionIndicator || !elements.connectionText) {
        console.warn('[DEBUG] Connection status elements not found');
        return;
    }

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

    // Valve and WiFi status moved to per-camera display
    // (No longer shown in header since we have multiple cameras)

    // Last detection
    if (elements.lastDetection) {
        if (status.last_detection) {
            const date = new Date(status.last_detection);
            // Format: March 25 2026 7:37:43 PM
            const options = {
                month: 'long',
                day: 'numeric',
                year: 'numeric',
                hour: 'numeric',
                minute: '2-digit',
                second: '2-digit',
                hour12: true
            };
            const formatted = date.toLocaleString('en-US', options).replace(',', '');
            elements.lastDetection.textContent = formatted;
        } else {
            elements.lastDetection.textContent = 'Never';
        }
    }

    // Session info (legacy - may not exist in current UI)
    if (elements.sessionDetections) {
        elements.sessionDetections.textContent = status.session_detections || 0;
    }

    // Cooldown (legacy - may not exist in current UI)
    if (elements.cooldownStatus) {
        if (status.cooldown_remaining > 0) {
            elements.cooldownStatus.textContent = `${status.cooldown_remaining}s`;
            elements.cooldownStatus.style.color = '#ffa726';
        } else {
            elements.cooldownStatus.textContent = 'None';
            elements.cooldownStatus.style.color = '#00c853';
        }
    }

    // Update button states
    updateButtonStates(status);
}

// Handle motion status updates (per-camera)
function handleMotionStatus(data) {
    // Update specific camera's PIR indicator
    if (data.camera_id) {
        const pirElement = document.getElementById(`pir-status-${data.camera_id}`);
        if (pirElement) {
            if (data.active) {
                pirElement.textContent = 'PIR: MOTION';
                pirElement.className = 'status-badge enabled';
                pirElement.title = 'Motion detected';
            } else {
                pirElement.textContent = 'PIR: IDLE';
                pirElement.className = 'status-badge disabled';
                pirElement.title = 'No motion';
            }
        }
    }

    // Legacy: Handle motion without camera_id (for backwards compatibility)
    if (!data.camera_id && data.active) {
        // Auto-start camera when motion detected (if not already active)
        if (!previousMotionActive && !cameraActive) {
            console.log('[AUTO-START] Motion detected, starting camera automatically...');
            startCamera();
        }
        previousMotionActive = true;
    } else if (!data.camera_id && !data.active) {
        previousMotionActive = false;
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
    if (elements.btnEnable && elements.btnDisable) {
        if (status.enabled) {
            elements.btnEnable.disabled = true;
            elements.btnDisable.disabled = false;
        } else {
            elements.btnEnable.disabled = false;
            elements.btnDisable.disabled = true;
        }
    }

    // Sprinkler controls (may not exist on all pages)
    if (elements.btnStopSprinkler) {
        const canControlSprinkler = status.valve_configured && isConnected;
        elements.btnStopSprinkler.disabled = !canControlSprinkler;
    }

    if (elements.btnTestSprinkler) {
        const canControlSprinkler = status.valve_configured && isConnected;
        elements.btnTestSprinkler.disabled = !canControlSprinkler || status.valve_on;
    }

    // Manual trigger (may not exist on all pages)
    if (elements.btnTriggerMotion) {
        elements.btnTriggerMotion.disabled = !status.enabled || !isConnected;
    }
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

// Load available cameras and populate selector
async function loadCameras() {
    try {
        const result = await apiCall('/cameras');
        if (result.success !== false && result.cameras) {
            availableCameras = result.cameras;

            if (elements.cameraSelector) {
                // Clear existing options except first
                elements.cameraSelector.innerHTML = '<option value="">Select a camera...</option>';

                // Add camera options
                availableCameras.forEach(camera => {
                    const option = document.createElement('option');
                    option.value = camera.id;
                    option.textContent = camera.name;
                    elements.cameraSelector.appendChild(option);
                });

                // Auto-select first camera
                if (availableCameras.length > 0) {
                    selectedCameraId = availableCameras[0].id;
                    elements.cameraSelector.value = selectedCameraId;
                    console.log('[DEBUG] Auto-selected camera:', selectedCameraId);
                }
            }
        }
    } catch (error) {
        console.error('Failed to load cameras:', error);
    }
}

// Fetch and display per-camera detection status
async function fetchCameraStatus(cameraId) {
    try {
        const result = await apiCall(`/cameras/${cameraId}/detection/status`);

        if (result.success !== false) {
            console.log(`[STATUS] Camera ${cameraId}:`, {
                session_active: result.session_active,
                session_detections: result.session_detections,
                session_elapsed: result.session_elapsed_seconds,
                active_window: result.active_window_seconds,
                cooldown_remaining: result.cooldown_remaining
            });

            // Store status data for this camera
            cameraStatusData[cameraId] = result;

            // Update camera card footer with countdown
            updateCameraFooter(cameraId, result);

            // Update camera PIR and WiFi indicators
            updateCameraIndicators(cameraId, result);

            // Update right panel if available
            if (elements.cameraStatusPanel) {
                elements.cameraStatusPanel.style.display = 'block';

                if (elements.cameraStatusContent) {
                    // Get camera name
                    const camera = availableCameras.find(c => c.id === cameraId);
                    const cameraName = camera ? camera.name : cameraId;

                    // Calculate remaining time
                    let statusHtml = `<strong>${cameraName}</strong><br>`;

                    if (result.session_active) {
                        const elapsed = result.session_elapsed_seconds || 0;
                        const remaining = Math.max(0, (result.active_window_seconds || 60) - elapsed);
                        const detections = result.session_detections || 0;

                        statusHtml += `<div style="color: #4CAF50;">
                            <strong>🟢 DETECTION ACTIVE</strong><br>
                            Remaining: <strong>${remaining}s</strong><br>
                            Detections: <strong>${detections}</strong>
                        </div>`;
                    } else if (result.cooldown_remaining > 0) {
                        statusHtml += `<div style="color: #ffa726;">
                            <strong>⏳ COOLDOWN</strong><br>
                            Remaining: <strong>${result.cooldown_remaining}s</strong>
                        </div>`;
                    } else {
                        statusHtml += `<div style="color: #999;">
                            <strong>⚪ IDLE</strong><br>
                            Ready for detection
                        </div>`;
                    }

                    elements.cameraStatusContent.innerHTML = statusHtml;
                }
            }
        }
    } catch (error) {
        console.error('Failed to fetch camera status:', error);
    }
}

// Update camera card footer with countdown display
function updateCameraFooter(cameraId, statusData) {
    const footerElement = document.getElementById(`camera-footer-${cameraId}`);
    if (!footerElement) {
        console.warn(`[FOOTER] Footer element not found for camera: ${cameraId}`);
        return;
    }

    console.log(`[FOOTER] Updating footer for camera ${cameraId}, session_active=${statusData.session_active}`);

    let footerHtml = '';

    if (statusData.session_active) {
        const activeRemaining = Math.floor(statusData.session_remaining_seconds || 0);
        const cooldownPeriod = statusData.cooldown_period_seconds || 120;
        const deviceRemaining = Math.floor(statusData.device_remaining || 0);

        footerHtml = `
            <div class="footer-status active">
                <div class="footer-line">🟢 Active: ${activeRemaining}s</div>
                <div class="footer-line">⏳ Cooldown: ${cooldownPeriod}s</div>
                <div class="footer-line">⏱️ Duration: ${deviceRemaining > 0 ? deviceRemaining + 's' : 'N/A'}</div>
            </div>
        `;
    } else if (statusData.cooldown_remaining > 0) {
        const cooldownSecs = Math.floor(statusData.cooldown_remaining);
        footerHtml = `
            <div class="footer-status cooldown">
                <div class="footer-timer">⏳ COOLDOWN: ${cooldownSecs}s</div>
            </div>
        `;
    } else {
        footerHtml = `
            <div class="footer-status idle">
                <div class="footer-timer">⚪ IDLE</div>
            </div>
        `;
    }

    footerElement.innerHTML = footerHtml;

    // Start countdown interval if not already running
    if ((statusData.session_active || statusData.cooldown_remaining > 0) && !cameraCountdownIntervals[cameraId]) {
        startCountdownTimer(cameraId);
    } else if (!statusData.session_active && statusData.cooldown_remaining === 0) {
        // Clear interval if no longer active
        if (cameraCountdownIntervals[cameraId]) {
            clearInterval(cameraCountdownIntervals[cameraId]);
            delete cameraCountdownIntervals[cameraId];
        }
    }
}

// Update per-camera PIR and WiFi indicators
function updateCameraIndicators(cameraId, statusData) {
    const pirElement = document.getElementById(`pir-status-${cameraId}`);
    const wifiElement = document.getElementById(`wifi-status-${cameraId}`);

    // Update PIR status
    if (pirElement) {
        if (statusData.motion_active) {
            pirElement.textContent = 'PIR: MOTION';
            pirElement.className = 'status-badge enabled';
            pirElement.title = 'Motion detected';
        } else {
            pirElement.textContent = 'PIR: IDLE';
            pirElement.className = 'status-badge disabled';
            pirElement.title = 'No motion';
        }
    }

    // Update WiFi status
    if (wifiElement) {
        if (statusData.wifi_signal !== null && statusData.wifi_signal !== undefined) {
            const rssi = statusData.wifi_signal;
            let signalText, signalClass;

            // RSSI ranges: -30 (excellent) to -90 (terrible)
            if (rssi >= -50) {
                signalText = 'Excellent';
                signalClass = 'status-badge enabled';
            } else if (rssi >= -60) {
                signalText = 'Good';
                signalClass = 'status-badge enabled';
            } else if (rssi >= -70) {
                signalText = 'Fair';
                signalClass = 'status-badge active';
            } else {
                signalText = 'Poor';
                signalClass = 'status-badge disabled';
            }

            wifiElement.textContent = `WiFi: ${rssi} dBm`;
            wifiElement.className = signalClass;
            wifiElement.title = `${signalText} signal strength`;
        } else {
            wifiElement.textContent = 'WiFi: --';
            wifiElement.className = 'status-badge disabled';
            wifiElement.title = 'No signal data';
        }
    }
}

// Start countdown timer for a camera
function startCountdownTimer(cameraId) {
    // Clear existing interval if any
    if (cameraCountdownIntervals[cameraId]) {
        clearInterval(cameraCountdownIntervals[cameraId]);
    }

    cameraCountdownIntervals[cameraId] = setInterval(() => {
        const statusData = cameraStatusData[cameraId];
        if (!statusData) {
            clearInterval(cameraCountdownIntervals[cameraId]);
            delete cameraCountdownIntervals[cameraId];
            return;
        }

        const footerElement = document.getElementById(`camera-footer-${cameraId}`);
        if (!footerElement) {
            clearInterval(cameraCountdownIntervals[cameraId]);
            delete cameraCountdownIntervals[cameraId];
            return;
        }

        // Decrement server values locally for smooth display
        if (statusData.session_active) {
            // Decrement remaining times (from server)
            statusData.session_remaining_seconds = Math.max(0, (statusData.session_remaining_seconds || 0) - 1);
            statusData.device_remaining = Math.max(0, (statusData.device_remaining || 0) - 1);

            const activeRemaining = Math.floor(statusData.session_remaining_seconds);
            const cooldownPeriod = statusData.cooldown_period_seconds || 120;
            const deviceRemaining = Math.floor(statusData.device_remaining);

            if (activeRemaining <= 0) {
                // Session ended, will fetch new status next poll
                statusData.session_active = false;
                statusData.cooldown_remaining = statusData.cooldown_period_seconds || 120;
            }

            footerElement.innerHTML = `
                <div class="footer-status active">
                    <div class="footer-line">🟢 Active: ${activeRemaining}s</div>
                    <div class="footer-line">⏳ Cooldown: ${cooldownPeriod}s</div>
                    <div class="footer-line">⏱️ Duration: ${deviceRemaining > 0 ? deviceRemaining + 's' : 'N/A'}</div>
                </div>
            `;
        } else if (statusData.cooldown_remaining > 0) {
            statusData.cooldown_remaining = Math.max(0, statusData.cooldown_remaining - 1);
            const cooldownSecs = Math.floor(statusData.cooldown_remaining);

            if (cooldownSecs <= 0) {
                // Cooldown ended
                clearInterval(cameraCountdownIntervals[cameraId]);
                delete cameraCountdownIntervals[cameraId];
                footerElement.innerHTML = `
                    <div class="footer-status idle">
                        <div class="footer-timer">⚪ IDLE</div>
                    </div>
                `;
                return;
            }

            footerElement.innerHTML = `
                <div class="footer-status cooldown">
                    <div class="footer-timer">⏳ COOLDOWN: ${cooldownSecs}s</div>
                </div>
            `;
        }
    }, 1000);  // Update every second
}

// Button event handlers
function setupEventListeners() {
    if (!elements.btnEnable) {
        console.error('btnEnable missing from elements');
        return;
    }

    // Camera selector change
    if (elements.cameraSelector) {
        elements.cameraSelector.addEventListener('change', (e) => {
            selectedCameraId = e.target.value;
            console.log('[DEBUG] Camera selected:', selectedCameraId);
        });
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
            await startCamera();
        } else {
            stopCamera();
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
    // Skip if video feed element doesn't exist (multi-camera mode)
    if (!elements.videoFeed) {
        console.log('[DEBUG] Video feed element not found (multi-camera mode)');
        return;
    }

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

// Update system health panel
async function updateHealthPanel() {
    try {
        const response = await fetch('/api/health');
        if (!response.ok) return;

        const data = await response.json();
        if (!data.detailed) return;

        const healthPanel = document.getElementById('healthPanel');
        if (!healthPanel) return;

        // Show health panel if we got data
        healthPanel.style.display = 'block';

        // Update health indicators
        const deviceHealth = data.detailed.device_manager;
        const activationHealth = data.detailed.activation_metrics;
        const apiUsage = data.detailed.api_usage;

        // Credentials status
        const credsElem = document.getElementById('healthCreds');
        if (credsElem) {
            credsElem.textContent = deviceHealth.credentials_valid ? '✓ Valid' : '✗ Invalid';
            credsElem.style.color = deviceHealth.credentials_valid ? '#00c853' : '#ff1744';
        }

        // API Quota
        const quotaElem = document.getElementById('healthQuota');
        if (quotaElem && apiUsage) {
            const usage = apiUsage.this_month.quota_usage_pct || 0;
            const resetInfo = apiUsage.reset_info || {};
            const resetDate = resetInfo.reset_date || 'Unknown';
            const burnRate = resetInfo.daily_burn_rate_pct || 0;
            const depletion = resetInfo.projected_depletion_date || 'Not available';

            quotaElem.textContent = `${usage.toFixed(1)}% used`;
            quotaElem.style.color = usage > 90 ? '#ff1744' : (usage > 75 ? '#ffa726' : '#00c853');
            quotaElem.title = `Reset: ${resetDate}\nBurn rate: ${burnRate.toFixed(2)}%/day\nProjected depletion: ${depletion}`;
        }

        // Success rate
        const rateElem = document.getElementById('healthRate');
        if (rateElem && activationHealth) {
            const rate = activationHealth.success_rate_pct || 0;
            rateElem.textContent = `${rate.toFixed(1)}%`;
            rateElem.style.color = rate > 90 ? '#00c853' : (rate > 70 ? '#ffa726' : '#ff1744');
        }

        // Latency
        const latencyElem = document.getElementById('healthLatency');
        if (latencyElem && activationHealth) {
            const latency = activationHealth.avg_latency_ms || 0;
            latencyElem.textContent = `${latency.toFixed(0)}ms`;
            latencyElem.style.color = latency < 500 ? '#00c853' : (latency < 1000 ? '#ffa726' : '#ff1744');
        }

    } catch (error) {
        console.debug('Health panel update failed:', error);
        // Silently fail - health panel is optional
    }
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
// --- MULTI-CAMERA GRID ---
let camerasData = {};

async function initCameraGrid() {
    try {
        const response = await fetch('/api/cameras');
        const data = await response.json();

        if (data.success) {
            camerasData = {};
            data.cameras.forEach(camera => {
                camerasData[camera.id] = camera;
            });
            renderCameraGrid();
            console.log('[DEBUG] Camera grid initialized with', Object.keys(camerasData).length, 'cameras');
        }
    } catch (error) {
        console.error('Failed to load cameras:', error);
    }
}

function renderCameraGrid() {
    const grid = document.getElementById('camerasGrid');
    if (!grid) return;

    if (Object.keys(camerasData).length === 0) {
        grid.innerHTML = '<div style="grid-column: 1/-1; text-align: center; padding: 40px 20px; color: #999;">No cameras configured</div>';
        return;
    }

    grid.innerHTML = Object.values(camerasData).map(camera => createCameraCard(camera)).join('');

    // Update indicators for all cameras after rendering
    Object.values(camerasData).forEach(camera => {
        updateCameraIndicators(camera.id, camera.state);
    });
}

function createCameraCard(camera) {
    const isOnline = camera.state.online;
    const statusClass = isOnline ? 'online' : 'offline';
    const statusText = isOnline ? '🟢 ONLINE' : '🔴 OFFLINE';

    const videoUrl = `/video_feed/${camera.id}`;
    const offlinePlaceholder = isOnline ? '' : `<div class="offline-placeholder"><p>📷 ${camera.name} Offline</p></div>`;

    return `
        <div class="camera-grid-card" id="camera-card-${camera.id}">
            <div class="camera-grid-header">
                <div class="camera-grid-name">${escapeHtml(camera.name)}</div>
                <div class="camera-grid-status ${statusClass}">${statusText}</div>
            </div>
            <div class="camera-grid-video">
                <img src="${videoUrl}" alt="${camera.name}" style="display: ${isOnline ? 'block' : 'none'};">
                ${offlinePlaceholder}
            </div>
            <div class="camera-grid-info">
                <span>Session: ${camera.state.session_detections || 0}</span>
                <span>Enabled: ${camera.enabled ? '✓' : '✗'}</span>
                <span id="pir-status-${camera.id}" class="status-badge disabled">PIR: --</span>
                <span id="wifi-status-${camera.id}" class="status-badge disabled">WiFi: --</span>
            </div>
            <div class="camera-grid-footer" id="camera-footer-${camera.id}">
                <div class="footer-status">⚪ IDLE</div>
            </div>
            <button class="camera-grid-action" onclick="window.location.href='/cameras#${camera.id}'">⚙️ Edit</button>
        </div>
    `;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Update camera status from WebSocket
function updateCameraStatus(cameraId, statusData) {
    if (camerasData[cameraId]) {
        Object.assign(camerasData[cameraId].state, statusData);
        renderCameraGrid();
    }
}
// ------------------------

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

    // Start fallback polling (only when WebSocket disconnected)
    try {
        console.log('[DEBUG] Step 4: Setting up fallback polling...');
        let isSocketConnected = false;

        // Track WebSocket connection status
        socket.on('connect', () => { isSocketConnected = true; });
        socket.on('disconnect', () => { isSocketConnected = false; });

        // Poll only when WebSocket is disconnected (fallback mode)
        let fallbackActive = false;
        setInterval(() => {
            if (!isSocketConnected) {
                if (!fallbackActive) {
                    console.log('[FALLBACK] WebSocket disconnected, using HTTP polling');
                    // Update connection status to show we're connected via polling
                    updateConnectionStatus(true);
                    fallbackActive = true;
                }
                pollStatus();
            } else {
                fallbackActive = false;
            }
        }, 5000);

        // Update health panel periodically (every 10 seconds)
        setInterval(() => {
            updateHealthPanel();
        }, 10000);

        // Initial status poll (WebSocket may not be connected yet)
        console.log('[DEBUG] Step 5: Initial status poll...');
        pollStatus();

        // Initial health panel update
        updateHealthPanel();
    } catch (e) { console.error('Step 4/5 failed:', e); }

    // Load cameras for per-camera controls
    try {
        console.log('[DEBUG] Step 6: Loading cameras...');
        loadCameras();
    } catch (e) { console.error('Step 6 failed:', e); }

    // Initialize multi-camera grid
    try {
        console.log('[DEBUG] Step 7: Initializing camera grid...');
        initCameraGrid();
    } catch (e) { console.error('Step 7 failed:', e); }

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
