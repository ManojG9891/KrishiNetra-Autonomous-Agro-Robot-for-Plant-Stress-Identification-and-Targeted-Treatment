// web_interface/static/js/main.js

document.addEventListener('DOMContentLoaded', () => {
    // --- STATE & CONFIG ---
    let appState = {
        robotStatus: 'OFF',
        missionPlan: {},
        chartInstances: {},
        allDiseaseClasses: [
            "Fungal_Blight", "Rust_Mildew", "Bacterial_Blight_Spot", "Viral_Curl_Mosaic",
            "Pest_Damage", "Wilt_Rot", "Nutrient_Deficiency", "Discoloration_Stress",
            "Leaf_Spot", "Physiological_Stress", "Rust_Scab_Rot", "Healthy"
        ]
    };

    const diseaseColorMap = {
        "Healthy": "#4CAF50", "Fungal_Blight": "#E53935", "Rust_Mildew": "#EF5350",
        "Leaf_Spot": "#F44336", "Rust_Scab_Rot": "#D32F2F", "Pest_Damage": "#FDD835",
        "Bacterial_Blight_Spot": "#FFC107", "Viral_Curl_Mosaic": "#8E24AA",
        "Wilt_Rot": "#9C27B0", "Nutrient_Deficiency": "#1E88E5",
        "Discoloration_Stress": "#2196F3", "Physiological_Stress": "#42A5F5", "Default": "#9E9E9E"
    };

    // --- DOM REFERENCES ---
    const DOM = {
        dashboardContainer: document.querySelector('.dashboard-container'),
        wizardView: document.getElementById('wizard-view'),
        missionView: document.getElementById('mission-view'),
        serverStatus: document.getElementById('server-status'),
        robotStatus: document.getElementById('robot-status'),
        liveDataStrip: document.getElementById('live-data-strip'),
        sensors: {
            frontUs: document.getElementById('front-us-data'),
            sideUs: document.getElementById('side-us-data'),
            temp: document.getElementById('temp-data'),
            humidity: document.getElementById('humidity-data'),
            hall: document.getElementById('hall-data'),
        },
        wizardStep3: document.getElementById('wizard-step-3'),
        wizardParamsContainer: document.getElementById('wizard-params-container'),
        multiRowTableContainer: document.getElementById('multi-row-table-container'),
        snapshotImage: document.getElementById('snapshot-image'),
        liveTallyContent: document.getElementById('live-tally-content'),
        liveStatusMessage: document.getElementById('live-status-message'),
        liveSummaryPanel: document.getElementById('live-session-summary-panel'),
        plantLogContent: document.getElementById('plant-log-content'),
        missionControlsWrapper: document.getElementById('mission-controls-wrapper'),
        // ✅ 1D: Reference to post-mission summary box is no longer needed
        mainTabs: document.getElementById('main-tabs'),
        manualControls: document.getElementById('manual-controls'),
        summaryAnalytics: document.getElementById('summary-analytics'),
        modal: {
            element: document.getElementById('image-modal'),
            title: document.getElementById('modal-title'),
            image: document.getElementById('modal-image'),
            closeBtn: document.querySelector('.modal-close-btn'),
        },
        summary: {
            prevHeader: document.getElementById('prev-session-header'),
            prevTable: document.getElementById('prev-session-summary-table'),
            overallHeader: document.getElementById('overall-session-header'),
            overallTable: document.getElementById('overall-summary-table'),
        },
    };

    // =========================================================================
    // --- API & UI HELPERS ---
    // =========================================================================
    async function sendCommand(command, payload = {}) {
        try {
            const response = await fetch('/api/command', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ command, payload }),
            });
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ message: 'Command failed with no details' }));
                showToast(`Command '${command}' failed: ${errorData.message || ''}`, 'error');
            }
            return response;
        } catch (error) {
            console.error(`Error sending command ${command}:`, error);
            showToast('API command failed. Check backend connection.', 'error');
            return null;
        }
    }

    async function sendManualControl(commandObj) {
        try {
            await fetch('/api/manual_control', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(commandObj),
            });
        } catch (err) {
            console.error('Manual control error:', err);
        }
    }

    async function fetchJson(endpoint) {
        try {
            const response = await fetch(`/api/${endpoint}`);
            if (response.status === 404) return { error: 'Not Found' };
            if (!response.ok) return null;
            return await response.json();
        } catch (error) {
            console.error(`Error fetching from ${endpoint}:`, error);
            return null;
        }
    }

    function showToast(message, type = 'info') {
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;
        container.appendChild(toast);
        setTimeout(() => toast.remove(), 4000);
    }

    function isMissionActiveState(state) {
        return ['EXECUTING_ROW', 'ANALYZING', 'TREATING', 'PAUSED'].includes(state);
    }

    // =========================================================================
    // --- UI STATE & RENDERING ---
    // =========================================================================
    function setViewState(view) {
        DOM.missionView.style.display = view === 'mission' ? 'grid' : 'none';
        DOM.wizardView.style.display = view === 'wizard' ? 'block' : 'none';
    }

    function updateHeaderAndSensors(data) {
        const serverDot = DOM.serverStatus.querySelector('.status-dot');
        const serverText = DOM.serverStatus.querySelector('.status-text');
        const robotDot = DOM.robotStatus.querySelector('.status-dot');
        const robotText = DOM.robotStatus.querySelector('.status-text');

        const serverOk = data && data.server_status === 'connected';
        DOM.serverStatus.className = `status-indicator ${serverOk ? 'connected' : 'disconnected'}`;
        serverText.textContent = serverOk ? 'Connected' : 'Disconnected';

        const robotState = data?.robot_status || "DISCONNECTED";
        let robotLabel = robotState.replace(/_/g, ' ');
        robotText.textContent = robotLabel;

        let statusClass = 'disconnected';
        if (['EXECUTING_ROW', 'ANALYZING', 'TREATING'].includes(robotState)) statusClass = 'running';
        else if (robotState === 'PAUSED') statusClass = 'paused';
        else if (['IDLE', 'MISSION_SETUP', 'MISSION_AWAITING_START', 'STARTUP'].includes(robotState)) statusClass = 'idle';
        DOM.robotStatus.className = `status-indicator ${statusClass}`;

        DOM.liveDataStrip.style.display = 'flex';
        const sensorData = data?.last_sensor_data || {};
        DOM.sensors.frontUs.textContent = sensorData.F != null ? sensorData.F.toFixed(0) : '--';
        DOM.sensors.sideUs.textContent = sensorData.S != null ? sensorData.S.toFixed(0) : '--';
        DOM.sensors.temp.textContent = sensorData.T != null ? sensorData.T.toFixed(1) : '--';
        DOM.sensors.humidity.textContent = sensorData.H != null ? sensorData.H.toFixed(1) : '--';
        DOM.sensors.hall.textContent = sensorData.E != null ? sensorData.E : '--';
    }

    function renderMissionUI(data) {
        if (!data) return;
        

        DOM.liveStatusMessage.textContent = data.mission_message || 'Waiting for mission...';
        
        const isMissionActive = isMissionActiveState(data.robot_status);
        if (isMissionActive) {
            // --- MISSION IS ACTIVE: TRY TO SHOW LIVE FEED ---
            const message = data.mission_message || '';
            let currentAngle = 'middle'; // Default to middle for general movement
            if (message.toLowerCase().includes('capturing top') || message.toLowerCase().includes('processing top')) {
                currentAngle = 'top';
            } else if (message.toLowerCase().includes('capturing bottom') || message.toLowerCase().includes('processing bottom')) {
                currentAngle = 'bottom';
        }

     const imageUrl = `/api/scan_image/${currentAngle}?t=${new Date().getTime()}`;

    // Fetch the image and only update the src if the image actually exists.
    // This prevents the "Awaiting Scan" flicker.
    fetch(imageUrl)
        .then(response => {
            if (response.ok) {
                DOM.snapshotImage.src = imageUrl;
                DOM.snapshotImage.classList.remove('startup-logo');
            }
            // If response is not ok (e.g., 404), do nothing. The old image (or logo) remains.
        });

} else {
    // --- MISSION IS IDLE: SHOW THE LOGO ---
    // Force the image source back to the logo.
    DOM.snapshotImage.src = "/static/images/logo.png";
    DOM.snapshotImage.classList.add('startup-logo');
}



        // ✅ 1B: Tighter table design for tally
        let tallyHTML = '<table class="tight-table"><thead><tr><th>Disease Class</th><th>Count</th></tr></thead><tbody>';
        let total = 0;
        appState.allDiseaseClasses.forEach(cls => {
            const count = data.session_tally?.[cls] || 0;
            total += count;
            tallyHTML += `<tr><td>${cls.replace(/_/g, ' ')}</td><td>${count}</td></tr>`;
        });
        tallyHTML += `</tbody><tfoot><tr><th>Total</th><th>${total}</th></tr></tfoot></table>`;
        DOM.liveTallyContent.innerHTML = tallyHTML;

        const plan = data.mission_plan || {};
        const progress = data.mission_progress || {};

        // ✅ 1E: New 3-row x 2-column mission summary layout
        let rowsCovered = (progress.current_row_index || 0) + 1;
        let rowsEntered = plan.map?.length || 0;
        if (plan.layoutMode === 'single_row') {
            rowsEntered = 1;
        }

        DOM.liveSummaryPanel.innerHTML = `
            <div class="mission-summary-grid">
                <span class="summary-field">Mission ID</span>
                <span class="summary-value">${data.mission_id || 'N/A'}</span>
                
                <span class="summary-field">Rows Covered/Entered</span>
                <span class="summary-value">${rowsCovered} / ${rowsEntered}</span>

                <span class="summary-field">Operation Mode</span>
                <span class="summary-value">
                    ${(plan.layoutMode || 'N/A').replace('_','-')} / ${plan.operationMode || 'N/A'}
                </span>

                <span class="summary-field">Distance Covered</span>
                <span class="summary-value">${(progress.total_distance_in_row_cm || 0).toFixed(0)} cm</span>
                
                <span class="summary-field">Plants Scanned</span>
                <span class="summary-value">${(data.plant_log || []).length}</span>

                <span class="summary-field">Plants Treated</span>
                <span class="summary-value">${progress.plants_treated || 0}</span>
            </div>
        `;

        // ✅ 1C: Show only latest 3 plants
        let logHTML = `<table class="summary-table"><thead><tr>
            <th>#</th><th>Diseases</th><th>Treatment</th><th>T</th><th>M</th><th>B</th>
        </tr></thead><tbody>`;

        const latestLogs = (data.plant_log || []).slice(0, 3);

        latestLogs.forEach(entry => {
            const diseases = (entry.detected_diseases || []).join(', ').replace(/_/g, ' ');
            const images = ['top', 'middle', 'bottom'].map(angle =>
                entry.images && entry.images[angle]
                    ? `<button class="view-img-btn" data-img-path="${entry.images[angle]}" data-angle="${angle}">
                           <i class="fas fa-camera"></i>
                       </button>`
                    : '–'
            );

            logHTML += `
                <tr>
                    <td>${entry.plant_number}</td>
                    <td>${diseases || 'Healthy'}</td>
                    <td>${(entry.treatment_applied || 'None').replace(/_/g, ' ')}</td>
                    <td>${images[0]}</td>
                    <td>${images[1]}</td>
                    <td>${images[2]}</td>
                </tr>
            `;
        });
        logHTML += '</tbody></table>';

        DOM.plantLogContent.innerHTML = (latestLogs.length > 0) ? logHTML : `<p>Waiting for mission to start...</p>`;
    }

    function renderManualControls(status) {
        // This function generates the HTML; styling is handled by CSS.
        let html = `
            <div class="manual-activation">
                <span>Manual Mode</span>
                <label class="switch">
                    <input type="checkbox" id="manual-mode-toggle" ${status === 'MANUAL_CONTROL' ? 'checked' : ''}>
                    <span class="slider"></span>
                </label>
            </div>
        `;

        if (status === 'MANUAL_CONTROL') {
            html += `
                <div id="manual-controls-panel">
                    <h3>Movement</h3>
                    <div class="manual-joystick">
                        <button data-dir="forward" class="joy-btn"><i class="fas fa-arrow-up"></i></button>
                        <button data-dir="left" class="joy-btn"><i class="fas fa-arrow-left"></i></button>
                        <button data-dir="stop" class="joy-btn"><i class="far fa-circle"></i></button>
                        <button data-dir="right" class="joy-btn"><i class="fas fa-arrow-right"></i></button>
                        <button data-dir="backward" class="joy-btn"><i class="fas fa-arrow-down"></i></button>
                    </div>

                    <div class="speed-control">
                        <label>Speed:</label>
                        <input type="range" id="manual-speed" min="100" max="255" value="200">
                    </div>

                    <hr>
                    <h3>Servos</h3>
                    <div class="servo-control">
                        <label>Pan:</label>
                        <input type="range" class="servo-slider" data-servo="pan" min="0" max="180" value="90">
                    </div>
                    <div class="servo-control">
                        <label>Tilt:</label>
                        <input type="range" class="servo-slider" data-servo="tilt" min="0" max="180" value="90">
                    </div>
                    <div class="servo-control">
                        <label>Pipe:</label>
                        <input type="range" class="servo-slider" data-servo="pipe" min="0" max="180" value="90">
                    </div>

                    <hr>
                    <h3>Pumps</h3>
                    <div class="pump-grid">
                        <div class="pump-toggle">
                            <label>Tank 1</label>
                            <label class="switch">
                                <input type="checkbox" class="pump-toggle-cb" data-tank="1">
                                <span class="slider"></span>
                            </label>
                        </div>
                        <div class="pump-toggle">
                            <label>Tank 2</label>
                            <label class="switch">
                                <input type="checkbox" class="pump-toggle-cb" data-tank="2">
                                <span class="slider"></span>
                            </label>
                        </div>
                        <div class="pump-toggle">
                            <label>Water</label>
                            <label class="switch">
                                <input type="checkbox" class="pump-toggle-cb" data-tank="3">
                                <span class="slider"></span>
                            </label>
                        </div>
                    </div>
                </div>
            `;
        }
        DOM.manualControls.innerHTML = html;
    }

    // =========================================================================
    // --- WIZARD LOGIC (UNCHANGED) ---
    // =========================================================================
    function updateWizardStep3() {
        const layout = appState.missionPlan.layoutMode;
        const opMode = appState.missionPlan.operationMode;
        if (!layout || !opMode) {
            DOM.wizardStep3.style.display = 'none';
            return;
        }
        let html = '';
        if (layout === 'single_row' && opMode === 'continuous') {
            html = `<div class="param-group"><label>Total Row Length (cm)</label><input type="number" id="sr-cont-length" placeholder="Optional"></div><div class="param-group"><label>Scan Step Distance (cm) *</label><input type="number" id="sr-cont-step" required></div>`;
        } else if (layout === 'single_row' && opMode === 'individual') {
            html = `<div class="param-group"><label>Distance Between Plants (cm) *</label><input type="number" id="sr-ind-spacing" required></div><div class="param-group"><label>Total Number of Plants *</label><input type="number" id="sr-ind-count" required></div>`;
        } else if (layout === 'multi_row') {
            html = `<div class="param-group"><label>Number of Rows *</label><input type="number" id="mr-row-count" required min="1"></div><div class="param-group button-group"><button id="build-rows-btn" class="wizard-action-btn">Build Rows</button><button id="apply-all-btn" class="wizard-action-btn apply">Apply To All</button></div>`;
            if (opMode === 'continuous') {
                html += `<div class="param-group"><label>Scan Step Distance (cm) *</label><input type="number" id="mr-cont-step" required></div>`;
            }
            html += `<div class="param-group"><label>Distance Between Rows (cm) *</label><input type="number" id="mr-spacing" required></div>`;
        }
        DOM.wizardParamsContainer.innerHTML = html;
        DOM.wizardStep3.style.display = 'block';
        DOM.multiRowTableContainer.innerHTML = '';
    }

    function buildMultiRowTable() {
        const rowCount = parseInt(document.getElementById('mr-row-count')?.value);
        const opMode = appState.missionPlan.operationMode;
        if (!rowCount || rowCount <= 0) {
            showToast('Please enter a valid number of rows (> 0).', 'error');
            return;
        }
        let head = '', body = '';
        if (opMode === 'continuous') {
            head = '<tr><th>Row #</th><th>Row-wise Length (cm)</th></tr>';
            for (let i = 1; i <= rowCount; i++) {
                body += `<tr><td>${i}</td><td><input type="number" class="table-input" name="length" placeholder="Optional"></td></tr>`;
            }
        } else {
            head = '<tr><th>Row #</th><th># of Plants *</th><th>Spacing (cm) *</th></tr>';
            for (let i = 1; i <= rowCount; i++) {
                body += `<tr><td>${i}</td><td><input type="number" class="table-input" name="plants" required></td><td><input type="number" class="table-input" name="spacing" required></td></tr>`;
            }
        }
        DOM.multiRowTableContainer.innerHTML = `<table class="wizard-table"><thead>${head}</thead><tbody>${body}</tbody></table>`;
    }

    function applyAllMultiRow() {
        const table = DOM.multiRowTableContainer.querySelector('table');
        if (!table) {
            showToast('Build the rows table first.', 'error');
            return;
        }
        const firstRowInputs = table.querySelectorAll('tbody tr:first-child input');
        if (firstRowInputs.length === 0) return;
        table.querySelectorAll('tbody tr:not(:first-child)').forEach(row => {
            row.querySelectorAll('input').forEach((input, index) => {
                input.value = firstRowInputs[index].value;
            });
        });
    }

    function validateAndSaveMissionPlan() {
        const plan = { ...appState.missionPlan, map: [] };
        try {
            const isValidPositive = (value, name) => {
                const num = parseFloat(value);
                if (isNaN(num) || num <= 0) throw new Error(`${name} must be a number greater than 0.`);
                return num;
            };
            if (!plan.layoutMode || !plan.operationMode) throw new Error('Please select both layout and operation mode.');
            if (plan.layoutMode === 'single_row') {
                if (plan.operationMode === 'continuous') {
                    plan.scan_step_cm = isValidPositive(document.getElementById('sr-cont-step').value, 'Scan Step Distance');
                    const lengthVal = document.getElementById('sr-cont-length').value;
                    plan.map.push({ total_length_cm: lengthVal ? parseFloat(lengthVal) : null });
                } else {
                    const spacing = isValidPositive(document.getElementById('sr-ind-spacing').value, 'Distance Between Plants');
                    const count = isValidPositive(document.getElementById('sr-ind-count').value, 'Total Number of Plants');
                    plan.map.push({ num_plants: parseInt(count), spacing_cm: spacing });
                }
            } else {
                const table = DOM.multiRowTableContainer.querySelector('table');
                if (!table) throw new Error('Please click "Build Rows" to generate the table.');
                plan.distance_between_rows = isValidPositive(document.getElementById('mr-spacing').value, 'Distance Between Rows');
                const rows = [...table.querySelectorAll('tbody tr')];
                for (const [i, row] of rows.entries()) {
                    if (plan.operationMode === 'continuous') {
                        plan.scan_step_cm = isValidPositive(document.getElementById('mr-cont-step').value, 'Scan Step Distance');
                        const length = row.querySelector('input[name="length"]').value;
                        plan.map.push({ total_length_cm: length ? parseFloat(length) : null });
                    } else {
                        const plants = isValidPositive(row.querySelector('input[name="plants"]').value, `Row ${i + 1} # of Plants`);
                        const spacing = isValidPositive(row.querySelector('input[name="spacing"]').value, `Row ${i + 1} Spacing`);
                        plan.map.push({ num_plants: parseInt(plants), spacing_cm: spacing });
                    }
                }
            }
            sendCommand('save_mission', plan).then(r => {
                if (r && r.ok) {
                    setViewState('mission');
                    DOM.missionControlsWrapper.innerHTML = `<button id="start-mission-btn" class="control-btn btn-start">Start Mission</button>`;
                    showToast('Mission plan saved. Ready to start.', 'success');
                }
            });
        } catch (error) {
            showToast(error.message, 'error');
        }
    }

    // =========================================================================
    // --- ANALYTICS & CHARTING LOGIC (UNCHANGED) ---
    // =========================================================================
    function renderChart(canvasId, type, data, options) {
        if (appState.chartInstances[canvasId]) {
            appState.chartInstances[canvasId].destroy();
        }
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        appState.chartInstances[canvasId] = new Chart(ctx, { type, data, options });
    }
    function getHealthIndexClass(index) {
        if (index > 80) return 'health-excellent';
        if (index >= 60) return 'health-moderate';
        return 'health-poor';
    }
    function formatDuration(start, end) {
        if (!start || !end) return 'N/A';
        const durationMs = new Date(end) - new Date(start);
        const minutes = Math.floor(durationMs / 60000);
        return `${minutes} minutes`;
    }
    function renderPreviousSession(data) {
        // ✅ 2C: Robustness against backend data issues
        if (!data || data.error) {
            DOM.summary.prevHeader.innerHTML = `<p>No previous session data found.</p>`;
            DOM.summary.prevTable.innerHTML = '';
            renderChart('previous-pie-chart', 'pie', { labels: [], datasets: [] }, {});
            renderChart('previous-bar-chart', 'bar', { labels: [], datasets: [] }, {});
            return;
        }
        const stats = data.header_stats || {};
        const detectionSummary = data.detection_summary || [];
        const plantDiseaseData = data.plant_disease_data || [];
        const totalDetections = detectionSummary.reduce((sum, item) => sum + item.count, 0);
        const diseasedPlants = new Set(plantDiseaseData.map(p => p.plant_number)).size;
        DOM.summary.prevHeader.innerHTML = `<div class="live-summary-grid"><span class="summary-field">Mission ID:</span><span class="summary-value">${data.mission_id}</span><span class="summary-field">Health Index:</span><span class="summary-value ${getHealthIndexClass(data.health_index)}">${data.health_index}%</span><span class="summary-field">Start Time:</span><span class="summary-value">${new Date(stats.start_time).toLocaleTimeString()}</span><span class="summary-field">End Time:</span><span class="summary-value">${new Date(stats.end_time).toLocaleTimeString()}</span><span class="summary-field">Duration:</span><span class="summary-value">${formatDuration(stats.start_time, stats.end_time)}</span><span class="summary-field">Plants Scanned:</span><span class="summary-value">${stats.total_plants_scanned}</span><span class="summary-field">Diseased Plants Found:</span><span class="summary-value">${diseasedPlants}</span><span class="summary-field">Total Detections:</span><span class="summary-value">${totalDetections}</span></div>`;
        let tableHtml = `<table class="summary-table"><thead><tr><th>Disease Class</th><th>Times Detected</th></tr></thead><tbody>`;
        detectionSummary.forEach(item => { tableHtml += `<tr><td>${item.stress_detected.replace(/_/g, ' ')}</td><td>${item.count}</td></tr>`; });
        tableHtml += `</tbody><tfoot><tr><th>Total</th><th>${totalDetections}</th></tr></tfoot></table>`;
        DOM.summary.prevTable.innerHTML = tableHtml;
        renderChart('previous-pie-chart', 'pie', { labels: detectionSummary.map(d => d.stress_detected.replace(/_/g, ' ')), datasets: [{ data: detectionSummary.map(d => d.count), backgroundColor: detectionSummary.map(d => diseaseColorMap[d.stress_detected] || diseaseColorMap.Default), }] }, { responsive: true, plugins: { title: { display: true, text: 'Disease Class Distribution' } } });
        const plantNumbers = [...new Set(plantDiseaseData.map(d => d.plant_number))].sort((a, b) => a - b);
        const diseases = [...new Set(plantDiseaseData.map(d => d.stress_detected))];
        const barDatasets = diseases.map(disease => ({ label: disease.replace(/_/g, ' '), data: plantNumbers.map(pn => plantDiseaseData.find(d => d.plant_number === pn && d.stress_detected === disease)?.count || 0), backgroundColor: diseaseColorMap[disease] || diseaseColorMap.Default, }));
        
        if (plantDiseaseData && plantDiseaseData.length > 0) {
			document.getElementById('previous-bar-chart').style.display = 'block';
			renderChart(
                'previous-bar-chart',
                'bar',
                { labels: plantNumbers.map(pn => `Plant ${pn}`), datasets: barDatasets },
                {
                    responsive: true,
                    scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true }, },
                    plugins: { title: { display: true, text: 'Detections per Plant' } },
                }
             );
         } else {
			 document.getElementById('previous-bar-chart').style.display = 'none';
		 }    
    }
    
    function renderOverallHistory(data) {
        if (!data || data.error) {
            DOM.summary.overallHeader.innerHTML = `<p>No overall analytics data found.</p>`;
            DOM.summary.overallTable.innerHTML = '';
            return;
        }
        const stats = data.aggregated_stats || {};
        const overallDetectionSummary = data.overall_detection_summary || [];
        
        DOM.summary.overallHeader.innerHTML = `
        <div class="live-summary-grid">
        <span class="summary-field">Total Missions Run:</span>
        <span class="summary-value">${stats.total_missions || 0}</span>
        <span class="summary-field">Overall Health Index:</span>
        <span class="summary-value ${getHealthIndexClass(stats.health_index)}">
            ${stats.health_index || 0}%
        </span>
        <span class="summary-field">Total Plants Scanned:</span>
        <span class="summary-value">${stats.total_plants_scanned || 0}</span>
        <!-- ? FIXED: Added Total Detections field -->
        <span class="summary-field">Total Detections:</span>
        <span class="summary-value">${stats.total_detections || 0}</span>
        <span class="summary-field">Most Frequent Disease:</span>
        <span class="summary-value">${stats.most_frequent_disease || 'N/A'}</span>
        </div
        `;
        
        const totalDetections = overallDetectionSummary.reduce((sum, item) => sum + item.count, 0);
        let tableHtml = `<table class="summary-table"><thead><tr><th>Disease Class</th><th>Total Detections</th></tr></thead><tbody>`;
        overallDetectionSummary.forEach(item => { tableHtml += `<tr><td>${item.stress_detected.replace(/_/g, ' ')}</td><td>${item.count}</td></tr>`; });
        tableHtml += `</tbody><tfoot><tr><th>Total</th><th>${totalDetections}</th></tr></tfoot></table>`;
        DOM.summary.overallTable.innerHTML = tableHtml;
        renderChart('overall-pie-chart', 'pie', { labels: overallDetectionSummary.map(d => d.stress_detected.replace(/_/g, ' ')), datasets: [{ data: overallDetectionSummary.map(d => d.count), backgroundColor: overallDetectionSummary.map(d => diseaseColorMap[d.stress_detected] || diseaseColorMap.Default), }] }, { responsive: true, plugins: { title: { display: true, text: 'Overall Disease Distribution' } } });
        const sessionHealthData = data.session_health_data || [];
        renderChart('overall-session-bar-chart', 'bar', { labels: sessionHealthData.map(s => s.mission_id.slice(-10)), datasets: [{ label: 'Healthy Plants', data: sessionHealthData.map(s => s.healthy_count), backgroundColor: diseaseColorMap.Healthy, }, { label: 'Diseased Plants', data: sessionHealthData.map(s => s.diseased_count), backgroundColor: diseaseColorMap.Fungal_Blight, },] }, { responsive: true, scales: { x: { stacked: true }, y: { stacked: true }, }, plugins: { title: { display: true, text: 'Field Health Across Missions' } } });
        const diseaseTrendData = data.disease_trend_data || [];
        const trendDates = [...new Set(diseaseTrendData.map(d => d.date))].sort();
        const trendDiseases = [...new Set(diseaseTrendData.map(d => d.stress_detected))];
        const lineDatasets = trendDiseases.map(disease => ({ label: disease.replace(/_/g, ' '), data: trendDates.map(date => diseaseTrendData.find(d => d.date === date && d.stress_detected === disease)?.count || 0), borderColor: diseaseColorMap[disease] || diseaseColorMap.Default, tension: 0.1, }));
        
        
        if (diseaseTrendData && diseaseTrendData.length > 0) {
			document.getElementById('overall-trend-line-chart').style.display = 'block';
			const trendDates = [...new Set(diseaseTrendData.map(d => d.date))].sort();
			const trendDiseases = [...new Set(diseaseTrendData.map(d => d.stress_detected))];
			const lineDatasets = trendDiseases.map(disease => ({
				label: disease.replace(/_/g, ' '),
				data: trendDates.map(date => diseaseTrendData.find(d => d.date === date && d.stress_detected === disease)?.count || 0),
				borderColor: diseaseColorMap[disease] || diseaseColorMap.Default,
				tension: 0.1,
			}));
			renderChart(
			    'overall-trend-line-chart',
                'line',
                { labels: trendDates, datasets: lineDatasets, },
                { responsive: true, plugins: { title: { display: true, text: 'Disease Trend Over Time' } } }
            );
        } else {
			document.getElementById('overall-trend-line-chart').style.display = 'none';
		}
    }

    async function updateSummaryTab() {
        const [prevData, overallData] = await Promise.all([
            fetchJson('previous_session_analytics'),
            fetchJson('overall_analytics'),
        ]);
        renderPreviousSession(prevData);
        renderOverallHistory(overallData);
    }

    // =========================================================================
    // --- POLLING & STATE MACHINE ---
    // =========================================================================
    async function pollStatus() {
        const data = await fetchJson('status');
        if (!data) {
            updateHeaderAndSensors({ server_status: 'disconnected', robot_status: 'DISCONNECTED', last_sensor_data: {} });
            return;
        }

        appState.robotStatus = data.robot_status;
        updateHeaderAndSensors(data);
        if (DOM.wizardView.style.display === 'block') return;

        const isMissionActive = isMissionActiveState(appState.robotStatus);
        let controlsHtml = '';

        if (isMissionActive) {
            controlsHtml = `
                <div class="mission-buttons">
                    <button id="stop-mission-btn" class="control-btn btn-stop">Stop</button>
                    <button id="pause-mission-btn" class="control-btn btn-pause" ${appState.robotStatus === 'PAUSED' ? 'disabled' : ''}>Pause</button>
                    <button id="resume-mission-btn" class="control-btn btn-resume" ${appState.robotStatus !== 'PAUSED' ? 'disabled' : ''}>Resume</button>
                </div>
            `;
        } else if (appState.robotStatus === 'MISSION_AWAITING_START') {
            controlsHtml = `<button id="start-mission-btn" class="control-btn btn-start">Start Mission</button>`;
        } else {
            controlsHtml = `<button id="start-new-mission-btn" class="control-btn btn-start-new">Start New Mission</button>`;
        }
        // ✅ 1D: Logic for post-mission summary box is completely removed.

        if (DOM.missionControlsWrapper.innerHTML.trim() !== controlsHtml.trim()) {
            DOM.missionControlsWrapper.innerHTML = controlsHtml;
        }

        renderMissionUI(data);
        renderManualControls(appState.robotStatus);
    }

    // =========================================================================
    // --- EVENT LISTENERS & INITIALIZATION ---
    // =========================================================================
    function setupEventListeners() {
        DOM.dashboardContainer.addEventListener('click', e => {
            if (e.target.matches('.tab-link')) {
                DOM.mainTabs.querySelectorAll('.tab-link').forEach(t => t.classList.remove('active'));
                e.target.classList.add('active');
                document.querySelectorAll('#mission-view .tab-content').forEach(c => (c.style.display = 'none'));
                const contentId = { mission: 'mission-tab-content', manual: 'manual-controls', summary: 'summary-analytics' }[e.target.dataset.tab];
                if (contentId) document.getElementById(contentId).style.display = 'block';
                if (e.target.dataset.tab === 'summary') updateSummaryTab();
            }
            if (e.target.matches('.summary-tab-link')) {
                document.querySelectorAll('.summary-tab-link').forEach(t => t.classList.remove('active'));
                e.target.classList.add('active');
                document.querySelectorAll('#summary-analytics .summary-tab-content').forEach(c => (c.style.display = 'none'));
                const contentId = `${e.target.dataset.summaryTab}-content`;
                document.getElementById(contentId).style.display = 'block';
            }
        });

        DOM.wizardView.addEventListener('click', e => {
            if (e.target.matches('.layout-btn')) {
                appState.missionPlan.layoutMode = e.target.dataset.value;
                document.querySelectorAll('.layout-btn').forEach(b => b.classList.remove('active'));
                e.target.classList.add('active');
                updateWizardStep3();
            }
            if (e.target.matches('.opmode-btn')) {
                appState.missionPlan.operationMode = e.target.dataset.value;
                document.querySelectorAll('.opmode-btn').forEach(b => b.classList.remove('active'));
                e.target.classList.add('active');
                updateWizardStep3();
            }
            if (e.target.id === 'build-rows-btn') buildMultiRowTable();
            if (e.target.id === 'apply-all-btn') applyAllMultiRow();
            if (e.target.id === 'save-mission-plan-btn') validateAndSaveMissionPlan();
            if (e.target.id === 'back-to-dashboard-btn') setViewState('mission');
        });

        DOM.missionView.addEventListener('click', e => {
            const targetId = e.target.id;
            if (targetId === 'start-new-mission-btn') {
                setViewState('wizard');
                sendCommand('go_to_wizard');
                appState.missionPlan = {};
                DOM.wizardParamsContainer.innerHTML = '';
                DOM.multiRowTableContainer.innerHTML = '';
                DOM.wizardStep3.style.display = 'none';
                document.querySelectorAll('.layout-btn, .opmode-btn').forEach(b => b.classList.remove('active'));
            } else if (targetId === 'start-mission-btn') {
                sendCommand('start_mission');
            }
            // ✅ 2A: Sync JS buttons with backend commands
            else if (targetId === 'stop-mission-btn') {
                sendCommand('stop_mission');
            } else if (targetId === 'pause-mission-btn') {
                sendCommand('pause'); // Backend controller handles 'pause'
            } else if (targetId === 'resume-mission-btn') {
                sendCommand('resume'); // Backend controller handles 'resume'
            } else if (targetId === 'btn-emergency') {
                if (confirm('Are you sure you want to perform an Emergency Stop?')) {
                    sendCommand('emergency_stop');
                }
            }
            // ✅ 1A: Image tab buttons and their listener are removed
            else if (e.target.closest('.view-img-btn')) {
                const btn = e.target.closest('.view-img-btn');
                DOM.modal.image.src = `/captured_images/${btn.dataset.imgPath}`;
                DOM.modal.title.textContent = `Scan: ${btn.dataset.angle.charAt(0).toUpperCase() + btn.dataset.angle.slice(1)} View`;
                DOM.modal.element.style.display = 'block';
            }
        });

        // Manual Controls Event Delegation
        DOM.manualControls.addEventListener('mousedown', e => {
            const joyBtn = e.target.closest('.joy-btn');
            if (joyBtn) {
                const speed = document.getElementById('manual-speed')?.value || 200;
                sendManualControl({ type: 'move', direction: joyBtn.dataset.dir, speed: speed });
            }
        });
        DOM.manualControls.addEventListener('mouseup', e => {
            const joyBtn = e.target.closest('.joy-btn');
            if (joyBtn && joyBtn.dataset.dir !== 'stop') {
                sendManualControl({ type: 'move', direction: 'stop' });
            }
        });
        DOM.manualControls.addEventListener('change', e => {
            if (e.target.id === 'manual-mode-toggle') {
                if (isMissionActiveState(appState.robotStatus) && !confirm('A mission is active. Switching to manual mode will stop it. Continue?')) {
                    e.target.checked = false;
                    return;
                }
                sendCommand('set_manual_mode').then(() => {
                    // ✅ 2B: Force a status poll to update UI immediately after command
                    setTimeout(pollStatus, 500);
                });
            }
            if (e.target.matches('.pump-toggle-cb')) {
                sendManualControl({ type: 'pump', tank: e.target.dataset.tank, state: e.target.checked });
            }
        });
        DOM.manualControls.addEventListener('input', e => {
            if (e.target.matches('.servo-slider')) {
                sendManualControl({ type: 'servo', servo: e.target.dataset.servo, angle: e.target.value });
            }
        });

        DOM.modal.closeBtn.onclick = () => (DOM.modal.element.style.display = 'none');
        window.onclick = e => { if (e.target === DOM.modal.element) { DOM.modal.element.style.display = 'none'; } };
    }

    function init() {
        setViewState('mission');
        DOM.missionControlsWrapper.innerHTML = `<button id="start-new-mission-btn" class="control-btn btn-start-new">Start New Mission</button>`;
        setupEventListeners();
        pollStatus();
        setInterval(pollStatus, 2000);
    }

    init();
});
