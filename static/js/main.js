// static/js/main.js

// --- STATE MANAGEMENT ---
let controllerState = [];
let isDashboardInitialized = false;
let telemetryChartInstance = null;
let radarChartInstance = null;
let logSeverityChartInstance = null;

document.addEventListener('DOMContentLoaded', function() {
    initializeEmergencyModal(); 
    const pagePath = window.location.pathname;

    if (pagePath === '/') {
        initializeDashboard();
    } else if (pagePath === '/gps-console') {
        initializeGpsConsole();
    } else if (pagePath === '/surveillance') {
        initializeSurveillance();
        setInterval(updateSurveillanceFlightStatus, 2000);
    } else if (pagePath === '/manual-control') {
        initializeFlightControl();
        updateManualControlFlightParams();
        setInterval(updateManualControlFlightParams, 2000);
    }
    
    updateHeaderStatus();
    setInterval(updateHeaderStatus, 5000);
});

// --- Main Dashboard Logic ---
function renderControllers() {
    const controllersGrid = document.getElementById('controllers-grid');
    if (!controllersGrid) return;
    controllersGrid.innerHTML = '';
    let activeCount = 0;
    
    controllerState.forEach(ctrl => {
        if (ctrl.status === 'ACTIVE') activeCount++;
        
        let statusClass = `status-${ctrl.status}`;
        let cardClass = ctrl.status === 'FAILED' ? 'card controller-card failed-card' : 'card controller-card';
        
        // Context-dependent action buttons
        let footerHtml = '';
        if (ctrl.status === 'ACTIVE') {
            footerHtml = `
                <div style="display: flex; gap: 8px; width: 100%;">
                    <button class="btn btn-warning pause-btn" data-action="pause" style="flex: 1; padding: 6px 8px; font-size: 11px;">Pause</button>
                    <button class="btn btn-danger fail-btn" data-action="fail" style="flex: 1; padding: 6px 8px; font-size: 11px;">Simulate Fail</button>
                </div>
            `;
        } else if (ctrl.status === 'STANDBY') {
            footerHtml = `
                <button class="btn btn-primary activate-btn" data-action="activate" style="width: 100%; padding: 6px 12px; font-size: 12px;">Activate</button>
            `;
        } else if (ctrl.status === 'FAILED') {
            footerHtml = `
                <button class="btn btn-success recover-btn" data-action="recover" style="width: 100%; padding: 6px 12px; font-size: 12px;">Recover & Reset</button>
            `;
        }
        
        const cardHtml = `
            <div class="${cardClass}" data-name="${ctrl.name}">
                <div class="card-header">
                    <h3 style="font-size: 14px;">${ctrl.name}</h3>
                    <span class="status ${statusClass}">${ctrl.status}</span>
                </div>
                <div class="card-body" style="padding: 12px 16px;">
                    <p class="sub-header" style="margin: 0 0 12px 0; font-size: 12px;">${ctrl.type}</p>
                    <div class="metric"><span>Response Time</span><strong>${ctrl.response_time}</strong></div>
                    <div class="metric"><span>Last Update</span><strong>${ctrl.last_update}</strong></div>
                    <div class="agent-log-container" style="margin-top: 12px;">
                        <span style="font-size: 10px; color: var(--text-secondary); display: block; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.5px;">Live Log Feed</span>
                        <div class="agent-live-log" style="font-family: monospace; font-size: 11px; padding: 6px 8px; background: var(--bg-dark); border-radius: 4px; border: 1px solid var(--border-color); color: var(--text-primary); min-height: 32px; max-height: 48px; overflow-y: auto; line-height: 1.2; word-break: break-all;">
                            ${ctrl.message}
                        </div>
                    </div>
                </div>
                <div class="card-footer" style="padding: 10px 16px;">
                    ${footerHtml}
                </div>
            </div>
        `;
        controllersGrid.innerHTML += cardHtml;
    });
    
    const subHeader = document.getElementById('dashboard-sub-header');
    if (subHeader) {
        subHeader.textContent = `${activeCount} of 5 Backup Agents Active • Auto-Failover Protocol Engaged`;
    }
}

async function initializeDashboard() {
    const response = await fetch('/api/dashboard_data');
    const data = await response.json();
    controllerState = data.controllers;
    renderControllers();
    updateOtherDashboardPanels(data);
    
    // Initial fetch and build of data charts
    await refreshDashboardCharts();
    
    if (!isDashboardInitialized) {
        document.getElementById('controllers-grid').addEventListener('click', async (e) => {
            if (e.target.tagName === 'BUTTON' && e.target.closest('.controller-card')) {
                const controllerCard = e.target.closest('.controller-card');
                const controllerName = controllerCard.dataset.name;
                const action = e.target.dataset.action;
                
                if (controllerName && action) {
                    try {
                        const responseAction = await fetch('/api/agent/action', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ agent_name: controllerName, action: action })
                        });
                        const dataAction = await responseAction.json();
                        if (dataAction.status === 'success') {
                            const responseFresh = await fetch('/api/dashboard_data');
                            const dataFresh = await responseFresh.json();
                            controllerState = dataFresh.controllers;
                            renderControllers();
                            updateOtherDashboardPanels(dataFresh);
                            await refreshDashboardCharts();
                        } else {
                            console.error("Agent action failed:", dataAction.error);
                        }
                    } catch (err) {
                        console.error("Failed to run agent action API:", err);
                    }
                }
            }
        });
        isDashboardInitialized = true;
    }
    setInterval(updateDashboardMetrics, 3000);
}

async function updateDashboardMetrics() {
    try {
        const response = await fetch('/api/dashboard_data');
        const newData = await response.json();
        controllerState = newData.controllers;
        renderControllers();
        updateOtherDashboardPanels(newData);
        
        // Refresh visuals
        await refreshDashboardCharts();
    } catch (error) { 
        console.error("Failed to fetch dashboard metrics:", error); 
    }
}

async function refreshDashboardCharts() {
    try {
        const response = await fetch('/api/analytics_data');
        const data = await response.json();
        buildDashboardCharts(data);
    } catch (e) {
        console.error("Failed to refresh analytics data:", e);
    }
}

function renderFallbackVisuals(analyticsData) {
    const telemetryCanvas = document.getElementById('telemetry-chart');
    const radarCanvas = document.getElementById('radar-chart');
    const doughnutCanvas = document.getElementById('log-doughnut-chart');
    
    const telemetryHistory = analyticsData.telemetry || [];
    const latestTelemetry = telemetryHistory.length > 0 ? telemetryHistory[telemetryHistory.length - 1] : { speed: 0.0, altitude: 150.0, battery: 100.0, heading: 180.0 };
    
    if (telemetryCanvas) {
        const parent = telemetryCanvas.parentElement;
        parent.innerHTML = `
            <div style="display: flex; flex-direction: column; justify-content: center; height: 100%; text-align: center; gap: 8px;">
                <div style="font-size: 28px; font-weight: 600; color: var(--accent-cyan);">${parseFloat(latestTelemetry.speed).toFixed(1)} <span style="font-size: 14px; font-weight: 400; color: var(--text-secondary);">m/s Speed</span></div>
                <div style="font-size: 28px; font-weight: 600; color: #8CA69E;">${parseFloat(latestTelemetry.altitude).toFixed(1)} <span style="font-size: 14px; font-weight: 400; color: var(--text-secondary);">m Altitude</span></div>
                <div style="font-size: 12px; color: var(--text-secondary); margin-top: 4px;">Status: Telemetry Stream Active</div>
            </div>
        `;
    }
    
    if (radarCanvas) {
        const parent = radarCanvas.parentElement;
        const lidarData = analyticsData.lidar || [];
        const avgLidar = lidarData.length > 0 ? (lidarData.reduce((a,b) => a+b, 0) / lidarData.length).toFixed(1) : "0.0";
        const minLidar = lidarData.length > 0 ? Math.min(...lidarData).toFixed(1) : "0.0";
        parent.innerHTML = `
            <div style="display: flex; flex-direction: column; justify-content: center; height: 100%; text-align: center; gap: 8px;">
                <div style="font-size: 28px; font-weight: 600; color: var(--accent-red);">${minLidar}m <span style="font-size: 14px; font-weight: 400; color: var(--text-secondary);">Min LiDAR Range</span></div>
                <div style="font-size: 14px; color: var(--text-secondary);">Avg Proximity: <strong>${avgLidar}m</strong></div>
                <div style="font-size: 12px; color: var(--text-secondary); margin-top: 4px;">Status: 360° LiDAR Sweep Active</div>
            </div>
        `;
    }
    
    if (doughnutCanvas) {
        const parent = doughnutCanvas.parentElement;
        const logsDist = analyticsData.log_distribution || { INFO: 0, WARNING: 0, CRITICAL: 0 };
        parent.innerHTML = `
            <div style="display: flex; flex-direction: column; justify-content: center; height: 100%; text-align: center; gap: 6px;">
                <div style="display: flex; justify-content: space-between; font-size: 12px; padding: 4px 8px; border-bottom: 1px solid var(--border-color); color: var(--text-primary);">
                    <span>INFO Logs</span><strong style="color: #8CA69E;">${logsDist.INFO}</strong>
                </div>
                <div style="display: flex; justify-content: space-between; font-size: 12px; padding: 4px 8px; border-bottom: 1px solid var(--border-color); color: var(--text-primary);">
                    <span>WARNING Logs</span><strong style="color: #E6A23C;">${logsDist.WARNING}</strong>
                </div>
                <div style="display: flex; justify-content: space-between; font-size: 12px; padding: 4px 8px; color: var(--text-primary);">
                    <span>CRITICAL Logs</span><strong style="color: var(--accent-red);">${logsDist.CRITICAL}</strong>
                </div>
            </div>
        `;
    }
}

function buildDashboardCharts(analyticsData) {
    const telemetryCanvas = document.getElementById('telemetry-chart');
    const radarCanvas = document.getElementById('radar-chart');
    const doughnutCanvas = document.getElementById('log-doughnut-chart');
    
    if (!telemetryCanvas || !radarCanvas || !doughnutCanvas) return;
    
    if (typeof Chart === 'undefined') {
        console.warn("Chart.js is not loaded. Displaying simple fallback visualizations.");
        renderFallbackVisuals(analyticsData);
        return;
    }
    
    // 1. Telemetry Chart
    const telemetryHistory = analyticsData.telemetry || [];
    const labels = telemetryHistory.map((_, idx) => `T-${telemetryHistory.length - 1 - idx}`);
    const speeds = telemetryHistory.map(d => d.speed);
    const altitudes = telemetryHistory.map(d => d.altitude);
    
    if (!telemetryChartInstance) {
        telemetryChartInstance = new Chart(telemetryCanvas.getContext('2d'), {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Speed (m/s)',
                        data: speeds,
                        borderColor: '#8B704B',
                        backgroundColor: 'rgba(139, 112, 75, 0.08)',
                        borderWidth: 2,
                        tension: 0.25,
                        yAxisID: 'y'
                    },
                    {
                        label: 'Altitude (m)',
                        data: altitudes,
                        borderColor: '#8CA69E',
                        backgroundColor: 'rgba(140, 166, 158, 0.08)',
                        borderWidth: 2,
                        tension: 0.25,
                        yAxisID: 'y1'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        title: { display: true, text: 'Speed (m/s)', font: { size: 9, family: 'Outfit, sans-serif' } },
                        grid: { color: 'rgba(0,0,0,0.03)' }
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        title: { display: true, text: 'Altitude (m)', font: { size: 9, family: 'Outfit, sans-serif' } },
                        grid: { drawOnChartArea: false }
                    },
                    x: {
                        grid: { display: false }
                    }
                },
                plugins: {
                    legend: { labels: { font: { family: 'Outfit, sans-serif', size: 10 } } }
                }
            }
        });
    } else {
        telemetryChartInstance.data.labels = labels;
        telemetryChartInstance.data.datasets[0].data = speeds;
        telemetryChartInstance.data.datasets[1].data = altitudes;
        telemetryChartInstance.update();
    }
    
    // 2. LiDAR Radar Sweep Chart
    const lidarData = analyticsData.lidar || [];
    const radarLabels = Array.from({length: lidarData.length}, (_, i) => `${i * 30}°`);
    
    if (!radarChartInstance) {
        radarChartInstance = new Chart(radarCanvas.getContext('2d'), {
            type: 'radar',
            data: {
                labels: radarLabels,
                datasets: [{
                    label: 'LiDAR range (m)',
                    data: lidarData,
                    borderColor: '#A63D3D',
                    backgroundColor: 'rgba(166, 61, 61, 0.12)',
                    borderWidth: 1.5,
                    pointRadius: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    r: {
                        angleLines: { color: 'rgba(0,0,0,0.04)' },
                        grid: { color: 'rgba(0,0,0,0.04)' },
                        suggestedMin: 0,
                        suggestedMax: 12,
                        ticks: { display: false }
                    }
                },
                plugins: {
                    legend: { display: false }
                }
            }
        });
    } else {
        radarChartInstance.data.datasets[0].data = lidarData;
        radarChartInstance.update();
    }
    
    // 3. Severity Doughnut Chart
    const logsDist = analyticsData.log_distribution || { INFO: 0, WARNING: 0, CRITICAL: 0 };
    const doughnutLabels = ['INFO', 'WARNING', 'CRITICAL'];
    const doughnutData = [logsDist.INFO, logsDist.WARNING, logsDist.CRITICAL];
    
    if (!logSeverityChartInstance) {
        logSeverityChartInstance = new Chart(doughnutCanvas.getContext('2d'), {
            type: 'doughnut',
            data: {
                labels: doughnutLabels,
                datasets: [{
                    data: doughnutData,
                    backgroundColor: ['#8CA69E', '#E6A23C', '#A63D3D'],
                    borderWidth: 1,
                    borderColor: '#FFFFFF'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'bottom', labels: { boxWidth: 8, font: { family: 'Outfit, sans-serif', size: 9 } } }
                },
                cutout: '70%'
            }
        });
    } else {
        logSeverityChartInstance.data.datasets[0].data = doughnutData;
        logSeverityChartInstance.update();
    }
}

function updateOtherDashboardPanels(data) {
    const coDriveLogs = document.getElementById('co-drive-logs');
    if (coDriveLogs) {
        coDriveLogs.innerHTML = '';
        data.co_drive_logs.forEach(log => {
            coDriveLogs.innerHTML += `
                <div class="log-item" style="padding: 8px 12px; border-bottom: 1px solid var(--border-color);">
                    <div class="log-item-header" style="display: flex; justify-content: space-between; align-items: center;">
                        <strong style="color: ${log.type === 'CRITICAL' ? 'var(--accent-red)' : log.type === 'WARNING' ? 'var(--accent-yellow)' : 'var(--text-primary)'};">${log.source}</strong>
                        <span class="log-time" style="font-size: 11px; color: var(--text-secondary);">${log.time}</span>
                    </div>
                    <p style="margin: 4px 0; font-size: 12px;">${log.message}</p>
                </div>
            `;
        });
    }
    
    const cyberThreats = document.getElementById('cyber-threats');
    if (cyberThreats) {
        cyberThreats.innerHTML = '';
        const indicator = document.getElementById('threat-indicator');
        if (indicator) {
            indicator.textContent = `${data.cyber_threats.length} LOGGED`;
        }
        data.cyber_threats.forEach(threat => {
            cyberThreats.innerHTML += `
                <div class="threat-item" style="padding: 10px; border-bottom: 1px solid var(--border-color);">
                    <div class="threat-item-header" style="display: flex; justify-content: space-between; align-items: center;">
                        <strong style="color: var(--accent-red);">${threat.type}</strong>
                        <span class="status status-${threat.status}" style="font-size: 10px;">${threat.status}</span>
                    </div>
                    <p style="margin: 4px 0; font-size: 11px; color: var(--text-secondary);">${threat.details}</p>
                    <div class="confidence-bar" style="height: 4px; background: var(--bg-dark); border-radius: 2px; overflow: hidden; margin-top: 6px;">
                        <div class="confidence-fill" style="width: ${threat.confidence}%; height: 100%;"></div>
                    </div>
                </div>
            `;
        });
    }
}

// --- Other Page Initializers ---
async function updateHeaderStatus() {
    try {
        const response = await fetch('/api/dashboard_data');
        const data = await response.json();
        const status = data.system_status;
        
        const connEl = document.getElementById('status-conn');
        const timeEl = document.getElementById('status-time');
        const gpsEl = document.getElementById('status-gps');
        const alertsEl = document.getElementById('status-alerts');
        
        if (connEl) connEl.textContent = `${status.connection}%`;
        if (timeEl) timeEl.textContent = status.system_time;
        if (gpsEl) gpsEl.textContent = status.gps_status;
        if (alertsEl) alertsEl.textContent = status.emergency_alerts;
    } catch (e) {
        console.error("Error updating header status:", e);
    }
}

async function updateSurveillanceFlightStatus() {
    try {
        const response = await fetch('/api/flight_parameters');
        const data = await response.json();
        const altitudeEl = document.getElementById('surv-altitude');
        const speedEl = document.getElementById('surv-speed');
        const headingEl = document.getElementById('surv-heading');
        const batteryEl = document.getElementById('surv-battery');
        
        if (altitudeEl) altitudeEl.textContent = `${parseFloat(data.altitude).toFixed(1)}m`;
        if (speedEl) speedEl.textContent = `${parseFloat(data.speed).toFixed(1)} m/s`;
        if (headingEl) headingEl.textContent = `${parseFloat(data.heading).toFixed(0)}°`;
        if (batteryEl) batteryEl.textContent = `${parseFloat(data.battery).toFixed(1)}%`;
    } catch (e) {
        console.error("Error updating surveillance flight status:", e);
    }
}

async function updateManualControlFlightParams() {
    try {
        const response = await fetch('/api/flight_parameters');
        const data = await response.json();
        
        const speedEl = document.getElementById('param-speed');
        const altitudeEl = document.getElementById('param-altitude');
        const headingEl = document.getElementById('param-heading');
        const batteryEl = document.getElementById('param-battery');
        const gpsEl = document.getElementById('param-gps');
        
        if (speedEl) speedEl.textContent = `${parseFloat(data.speed).toFixed(1)} m/s`;
        if (altitudeEl) altitudeEl.textContent = `${parseFloat(data.altitude).toFixed(1)} m`;
        if (headingEl) headingEl.textContent = `${parseFloat(data.heading).toFixed(0)}°`;
        
        if (batteryEl) {
            batteryEl.textContent = `${parseFloat(data.battery).toFixed(1)}%`;
            const battVal = parseFloat(data.battery);
            if (battVal < 20) {
                batteryEl.className = 'danger-text';
            } else {
                batteryEl.className = 'status-good';
            }
        }
        
        if (gpsEl) {
            gpsEl.textContent = data.connection > 94 ? "Strong" : "Fair";
            gpsEl.className = data.connection > 94 ? 'status-good' : 'status-warning';
        }
        
        // Update Latitude and Longitude if grid items exist
        const paramItems = document.querySelectorAll('.param-item');
        paramItems.forEach(item => {
            const labelText = item.querySelector('span') ? item.querySelector('span').textContent.trim() : "";
            const strongVal = item.querySelector('strong');
            if (strongVal) {
                if (labelText.includes("Latitude")) {
                    strongVal.textContent = `${parseFloat(data.lat).toFixed(6)}`;
                } else if (labelText.includes("Longitude")) {
                    strongVal.textContent = `${parseFloat(data.lon).toFixed(6)}`;
                }
            }
        });
    } catch (e) {
        console.error("Error updating manual control flight parameters:", e);
    }
}

// --- Emergency Modal Logic ---
function initializeEmergencyModal() {
    const headerEmergencyBtn = document.querySelector('.btn-emergency');
    const threatMonitorEmergencyBtn = document.getElementById('threat-monitor-emergency-btn');
    
    const modalOverlay = document.getElementById('emergency-modal-overlay');
    const cancelBtn = document.getElementById('cancel-shutdown-btn');
    const confirmBtn = document.getElementById('confirm-shutdown-btn');
    
    if (!modalOverlay) return;

    const openModal = () => modalOverlay.classList.add('visible');
    const closeModal = () => modalOverlay.classList.remove('visible');

    if (headerEmergencyBtn) {
        headerEmergencyBtn.addEventListener('click', (e) => {
            e.preventDefault();
            openModal();
        });
    }

    if (threatMonitorEmergencyBtn) {
        threatMonitorEmergencyBtn.addEventListener('click', (e) => {
            e.preventDefault();
            openModal();
        });
    }

    if (cancelBtn) cancelBtn.addEventListener('click', closeModal);
    if (confirmBtn) {
        confirmBtn.addEventListener('click', async () => {
            closeModal();
            try {
                const response = await fetch('/api/override/kill_server', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                const data = await response.json();
                alert(data.message || "Emergency shutdown sequence engaged.");
            } catch (e) {
                alert("Shutdown command sent. Connection lost.");
            }
        });
    }
    
    modalOverlay.addEventListener('click', (e) => {
        if (e.target === modalOverlay) closeModal();
    });
}
