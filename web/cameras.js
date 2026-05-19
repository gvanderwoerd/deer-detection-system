// Camera Management UI
class CameraManager {
    constructor() {
        this.cameras = [];
        this.devices = [];
        this.editingCameraId = null;
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.loadDevices();  // Load devices first
        this.loadCameras();
    }

    setupEventListeners() {
        // Add Camera modal
        document.getElementById('btnAddCamera').addEventListener('click', () => this.showAddCameraModal());
        document.getElementById('modalClose').addEventListener('click', () => this.hideAddCameraModal());
        document.getElementById('btnCancel').addEventListener('click', () => this.hideAddCameraModal());
        document.getElementById('cameraForm').addEventListener('submit', (e) => this.handleAddCamera(e));
        document.getElementById('btnTestConnection').addEventListener('click', () => this.testConnection());

        // Edit Camera modal
        document.getElementById('editModalClose').addEventListener('click', () => this.hideEditCameraModal());
        document.getElementById('btnCancelEdit').addEventListener('click', () => this.hideEditCameraModal());
        document.getElementById('editCameraForm').addEventListener('submit', (e) => this.handleEditCamera(e));

        // Close modal when clicking outside
        document.getElementById('cameraModal').addEventListener('click', (e) => {
            if (e.target.id === 'cameraModal') {
                this.hideAddCameraModal();
            }
        });

        document.getElementById('editCameraModal').addEventListener('click', (e) => {
            if (e.target.id === 'editCameraModal') {
                this.hideEditCameraModal();
            }
        });
    }

    async loadCameras() {
        try {
            const response = await fetch('/api/cameras');
            const data = await response.json();

            if (data.success) {
                this.cameras = data.cameras;
                this.renderCameras();
            } else {
                this.showError('Failed to load cameras: ' + data.error);
            }
        } catch (error) {
            this.showError('Error loading cameras: ' + error.message);
        }
    }

    async loadDevices() {
        try {
            const response = await fetch('/api/devices');
            const data = await response.json();

            if (data.success) {
                this.devices = data.devices || [];
            } else {
                console.warn('Failed to load devices:', data.error);
                this.devices = [];
            }
        } catch (error) {
            console.warn('Error loading devices:', error.message);
            this.devices = [];
        }
    }

    renderCameras() {
        const grid = document.getElementById('camerasGrid');

        if (this.cameras.length === 0) {
            grid.innerHTML = `
                <div style="grid-column: 1 / -1;">
                    <div class="empty-state">
                        <h3>📷 No Cameras Registered</h3>
                        <p>Add your first camera to get started!</p>
                    </div>
                </div>
            `;
            return;
        }

        grid.innerHTML = this.cameras.map(camera => this.createCameraCard(camera)).join('');

        // Add event listeners to action buttons
        document.querySelectorAll('.btn-test').forEach(btn => {
            btn.addEventListener('click', (e) => this.quickTestCamera(e.target.dataset.cameraId));
        });

        document.querySelectorAll('.btn-edit').forEach(btn => {
            btn.addEventListener('click', (e) => this.showEditCameraModal(e.target.dataset.cameraId));
        });

        document.querySelectorAll('.btn-delete').forEach(btn => {
            btn.addEventListener('click', (e) => this.deleteCamera(e.target.dataset.cameraId));
        });
    }

    createCameraCard(camera) {
        const statusClass = camera.state.online ? 'status-online' : 'status-offline';
        const statusText = camera.state.online ? 'ONLINE' : 'OFFLINE';
        const statusDot = camera.state.online ? '🟢' : '🔴';

        const lastDetection = camera.state.last_detection
            ? new Date(camera.state.last_detection).toLocaleString()
            : 'Never';

        const enabledObjects = Object.entries(camera.detection_config.enabled_objects)
            .filter(([_, enabled]) => enabled)
            .map(([name, _]) => name)
            .join(', ');

        return `
            <div class="camera-card">
                <div class="camera-status">
                    <h3 class="camera-name">${this.escapeHtml(camera.name)}</h3>
                    <span class="status-badge ${statusClass}">
                        <span class="status-dot"></span>
                        ${statusText}
                    </span>
                </div>

                <div class="camera-details">
                    <div class="camera-detail-item">
                        <span class="detail-label">Hostname:</span>
                        <span class="detail-value">${this.escapeHtml(camera.hostname)}</span>
                    </div>
                    <div class="camera-detail-item">
                        <span class="detail-label">Enabled:</span>
                        <span class="detail-value">${camera.enabled ? '✓ Yes' : '✗ No'}</span>
                    </div>
                    <div class="camera-detail-item">
                        <span class="detail-label">Detects:</span>
                        <span class="detail-value">${enabledObjects || 'None'}</span>
                    </div>
                    <div class="camera-detail-item">
                        <span class="detail-label">Last Detection:</span>
                        <span class="detail-value">${lastDetection}</span>
                    </div>
                </div>

                <div class="camera-actions">
                    <button class="btn-sm btn-test" data-camera-id="${camera.id}">Test</button>
                    <button class="btn-sm btn-edit" data-camera-id="${camera.id}">Edit</button>
                    <button class="btn-sm btn-delete" data-camera-id="${camera.id}">Delete</button>
                </div>
            </div>
        `;
    }

    showAddCameraModal() {
        document.getElementById('cameraForm').reset();
        document.getElementById('testResult').classList.remove('show');
        document.getElementById('modalAlert').classList.remove('show');
        document.getElementById('cameraModal').classList.add('show');
    }

    hideAddCameraModal() {
        document.getElementById('cameraModal').classList.remove('show');
    }

    async handleAddCamera(e) {
        e.preventDefault();

        const data = {
            name: document.getElementById('cameraName').value,
            hostname: document.getElementById('cameraHostname').value,
            stream_url: document.getElementById('cameraStreamUrl').value
        };

        try {
            const response = await fetch('/api/cameras', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            const result = await response.json();

            if (result.success) {
                this.showModalSuccess('Camera registered successfully! Opening configuration...');
                setTimeout(() => {
                    this.hideAddCameraModal();
                    this.loadCameras();
                }, 1000);
            } else {
                this.showModalError('Failed to register camera: ' + result.error);
            }
        } catch (error) {
            this.showModalError('Error: ' + error.message);
        }
    }

    async testConnection() {
        const hostname = document.getElementById('cameraHostname').value;
        const streamUrl = document.getElementById('cameraStreamUrl').value;
        const testResult = document.getElementById('testResult');

        if (!hostname || !streamUrl) {
            this.showTestError('Please fill in hostname and stream URL');
            return;
        }

        testResult.innerHTML = '<div class="spinner"></div> Testing connection...';
        testResult.classList.add('show');

        try {
            // Try to fetch a small image from the stream
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 5000);

            const response = await fetch(streamUrl, {
                signal: controller.signal,
                mode: 'no-cors'
            });

            clearTimeout(timeoutId);

            this.showTestSuccess(`✓ Connection successful! Stream is accessible.`);
        } catch (error) {
            if (error.name === 'AbortError') {
                this.showTestError('Connection timeout (5s). Check if the camera is online and accessible.');
            } else {
                this.showTestError('Connection failed. Error: ' + error.message);
            }
        }
    }

    async quickTestCamera(cameraId) {
        const camera = this.cameras.find(c => c.id === cameraId);
        if (!camera) return;

        const btn = event.target;
        btn.disabled = true;
        btn.textContent = 'Testing...';

        try {
            const response = await fetch(`/api/cameras/${cameraId}/test`, { method: 'POST' });
            const result = await response.json();

            if (result.success) {
                alert(`✓ ${camera.name} is online!\n\nLatency: ${result.result.latency_ms}ms\nFrames: ${result.result.frames_captured}`);
            } else {
                alert(`✗ ${camera.name} is offline.\n\nError: ${result.error}`);
            }
        } catch (error) {
            alert(`Error testing camera: ${error.message}`);
        } finally {
            btn.disabled = false;
            btn.textContent = 'Test';
        }
    }

    showEditCameraModal(cameraId) {
        const camera = this.cameras.find(c => c.id === cameraId);
        if (!camera) return;

        this.editingCameraId = cameraId;

        document.getElementById('editCameraId').value = camera.id;
        document.getElementById('editCameraName').value = camera.name;
        document.getElementById('editConfidenceThreshold').value = camera.detection_config.confidence_threshold;

        // Set checkboxes for enabled objects
        document.querySelectorAll('#editCameraForm input[type="checkbox"]').forEach(checkbox => {
            const objectType = checkbox.name.replace('enabled_', '');
            checkbox.checked = camera.detection_config.enabled_objects[objectType] || false;
        });

        document.getElementById('editActiveDuration').value = camera.timing.active_window_seconds;
        document.getElementById('editCooldown').value = camera.timing.cooldown_period_seconds;

        // Render device assignments
        this.renderDeviceAssignments(camera);

        document.getElementById('editModalAlert').classList.remove('show');
        document.getElementById('editCameraModal').classList.add('show');
    }

    renderDeviceAssignments(camera) {
        const container = document.getElementById('deviceAssignments');

        if (this.devices.length === 0) {
            container.innerHTML = '<p style="color: #999; text-align: center; padding: 20px;">No smart devices available</p>';
            return;
        }

        // Build a map of device_id -> duration for quick lookup
        const assignedDevices = {};
        camera.device_assignments.forEach(assignment => {
            assignedDevices[assignment.device_id] = assignment.duration_seconds;
        });

        const html = this.devices.map(device => {
            const isAssigned = device.id in assignedDevices;
            const duration = assignedDevices[device.id] || 120;

            return `
                <div class="device-item">
                    <input
                        type="checkbox"
                        class="device-checkbox"
                        data-device-id="${device.id}"
                        ${isAssigned ? 'checked' : ''}
                    >
                    <label>
                        <div class="device-name">${this.escapeHtml(device.name)}</div>
                        <div class="device-duration">
                            Duration: <input
                                type="number"
                                class="device-duration-input"
                                data-device-id="${device.id}"
                                min="10"
                                max="600"
                                step="10"
                                value="${duration}"
                                ${!isAssigned ? 'disabled' : ''}
                            /> seconds
                            <small style="display: block; margin-top: 3px; color: #999; font-size: 0.85em;">
                                How long to keep this device active when triggered (e.g., sprinkler run time)
                            </small>
                        </div>
                    </label>
                </div>
            `;
        }).join('');

        container.innerHTML = html;

        // Add event listeners to checkboxes
        document.querySelectorAll('.device-checkbox').forEach(checkbox => {
            checkbox.addEventListener('change', (e) => {
                const deviceId = e.target.dataset.deviceId;
                const durationInput = document.querySelector(`.device-duration-input[data-device-id="${deviceId}"]`);
                durationInput.disabled = !e.target.checked;
            });
        });
    }

    hideEditCameraModal() {
        document.getElementById('editCameraModal').classList.remove('show');
        this.editingCameraId = null;
    }

    async handleEditCamera(e) {
        e.preventDefault();

        const cameraId = document.getElementById('editCameraId').value;

        // Collect enabled objects (those with name like "enabled_*")
        const enabledObjects = {};
        document.querySelectorAll('#editCameraForm input[type="checkbox"][name^="enabled_"]').forEach(checkbox => {
            const objectType = checkbox.name.replace('enabled_', '');
            enabledObjects[objectType] = checkbox.checked;
        });

        // Collect device assignments (those with class "device-checkbox")
        const deviceAssignments = [];
        document.querySelectorAll('.device-checkbox:checked').forEach(checkbox => {
            const deviceId = checkbox.dataset.deviceId;
            const durationInput = document.querySelector(`.device-duration-input[data-device-id="${deviceId}"]`);
            const duration = parseInt(durationInput.value) || 120;

            deviceAssignments.push({
                device_id: deviceId,
                duration_seconds: duration
            });
        });

        const data = {
            name: document.getElementById('editCameraName').value,
            detection_config: {
                confidence_threshold: parseFloat(document.getElementById('editConfidenceThreshold').value),
                enabled_objects: enabledObjects,
                save_person_detections: false
            },
            timing: {
                active_window_seconds: parseInt(document.getElementById('editActiveDuration').value),
                cooldown_period_seconds: parseInt(document.getElementById('editCooldown').value),
                max_detections_per_session: 3
            },
            device_assignments: deviceAssignments
        };

        try {
            const response = await fetch(`/api/cameras/${cameraId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            const result = await response.json();

            if (result.success) {
                this.showEditModalSuccess('Camera settings updated successfully!');
                setTimeout(() => {
                    this.hideEditCameraModal();
                    this.loadCameras();
                }, 1000);
            } else {
                this.showEditModalError('Failed to update camera: ' + result.error);
            }
        } catch (error) {
            this.showEditModalError('Error: ' + error.message);
        }
    }

    async deleteCamera(cameraId) {
        const camera = this.cameras.find(c => c.id === cameraId);
        if (!camera) return;

        if (!confirm(`Are you sure you want to delete "${camera.name}"? This action cannot be undone.`)) {
            return;
        }

        try {
            const response = await fetch(`/api/cameras/${cameraId}`, { method: 'DELETE' });
            const result = await response.json();

            if (result.success) {
                alert(`✓ Camera "${camera.name}" deleted successfully`);
                this.loadCameras();
            } else {
                alert(`✗ Failed to delete camera: ${result.error}`);
            }
        } catch (error) {
            alert(`Error deleting camera: ${error.message}`);
        }
    }

    showTestSuccess(message) {
        const testResult = document.getElementById('testResult');
        testResult.className = 'test-result show success';
        testResult.textContent = message;
    }

    showTestError(message) {
        const testResult = document.getElementById('testResult');
        testResult.className = 'test-result show error';
        testResult.textContent = message;
    }

    showModalSuccess(message) {
        const alert = document.getElementById('modalAlert');
        alert.className = 'alert show alert-success';
        alert.textContent = message;
    }

    showModalError(message) {
        const alert = document.getElementById('modalAlert');
        alert.className = 'alert show alert-error';
        alert.textContent = message;
    }

    showEditModalSuccess(message) {
        const alert = document.getElementById('editModalAlert');
        alert.className = 'alert show alert-success';
        alert.textContent = message;
    }

    showEditModalError(message) {
        const alert = document.getElementById('editModalAlert');
        alert.className = 'alert show alert-error';
        alert.textContent = message;
    }

    showError(message) {
        alert('Error: ' + message);
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    new CameraManager();
});
