// static/js/surveillance.js

function initializeSurveillance() {
    const totalObjectsCount = document.getElementById('total-objects-count');
    const highThreatsCount = document.getElementById('high-threats-count');
    const autoControlStatus = document.getElementById('auto-control-status');
    const survAltitude = document.getElementById('surv-altitude');
    const survSpeed = document.getElementById('surv-speed');
    const survHeading = document.getElementById('surv-heading');
    const survBattery = document.getElementById('surv-battery');
    const detectionLog = document.getElementById('detection-log');
    const detectionStatus = document.getElementById('detection-status');
    const videoEl = document.getElementById('live-video-feed');
    const canvasEl = document.getElementById('detection-overlay');
    const ctx = canvasEl ? canvasEl.getContext('2d') : null;

    // Hidden canvas for capturing frames to send to backend
    const captureCanvas = document.createElement('canvas');
    const captureCtx = captureCanvas.getContext('2d');

    const correctionActions = ["ADJUST RIGHT", "CLIMB", "ADJUST LEFT", "HALT"];
    let currentActionIndex = 0;
    let actionInterval;
    let lastDetections = [];
    let detecting = false;

    function logMessage(message, className = '') {
        if (!detectionLog) return;
        const p = document.createElement('p');
        p.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
        if (className) p.classList.add(className);
        detectionLog.insertBefore(p, detectionLog.firstChild);
        while (detectionLog.children.length > 30) {
            detectionLog.removeChild(detectionLog.lastChild);
        }
    }

    // --- Browser Camera ---
    async function startBrowserCamera() {
        logMessage('Opening optical feed connection...');
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } },
                audio: false
            });
            videoEl.srcObject = stream;
            if (detectionStatus) {
                detectionStatus.textContent = 'OPTICAL FEED ONLINE';
                detectionStatus.style.color = '#4CAF50';
            }
            logMessage('Connected. Browser camera feed active.');

            // Start the detection loop once the video is playing
            videoEl.addEventListener('playing', () => {
                logMessage('Detection engine active. Scanning for targets...');
                setInterval(captureAndDetect, 500); // Send a frame every 500ms
            }, { once: true });

        } catch (err) {
            console.error('Camera access error:', err);
            logMessage('Camera error: ' + err.message, 'danger-text');
            if (detectionStatus) {
                detectionStatus.textContent = 'CAMERA ERROR';
                detectionStatus.style.color = '#e74c3c';
            }
        }
    }

    // --- Capture a frame and send to backend for real face detection ---
    async function captureAndDetect() {
        if (detecting || !videoEl.videoWidth) return;
        detecting = true;

        try {
            // Draw current video frame to hidden canvas
            captureCanvas.width = videoEl.videoWidth;
            captureCanvas.height = videoEl.videoHeight;
            // Mirror the capture to match the mirrored video display
            captureCtx.translate(captureCanvas.width, 0);
            captureCtx.scale(-1, 1);
            captureCtx.drawImage(videoEl, 0, 0);
            captureCtx.setTransform(1, 0, 0, 1, 0, 0); // reset transform

            // Convert to JPEG blob
            const blob = await new Promise(resolve =>
                captureCanvas.toBlob(resolve, 'image/jpeg', 0.7)
            );

            // Send to backend
            const formData = new FormData();
            formData.append('frame', blob, 'frame.jpg');

            const response = await fetch('/api/surveillance/detect', {
                method: 'POST',
                body: formData
            });
            const result = await response.json();
            lastDetections = result.detections || [];

            // Update detection count
            if (totalObjectsCount) totalObjectsCount.textContent = lastDetections.length;
            if (highThreatsCount) highThreatsCount.textContent = lastDetections.length > 0 ? lastDetections.length : 0;

            // Draw boxes
            drawDetections(lastDetections);

            // Update threat status
            updateThreatStatus(lastDetections.length > 0);

        } catch (e) {
            console.error('Detection error:', e);
        }
        detecting = false;
    }

    // --- Draw real detection boxes on the canvas overlay ---
    function drawDetections(detections) {
        if (!ctx || !canvasEl) return;

        const rect = canvasEl.getBoundingClientRect();
        canvasEl.width = rect.width;
        canvasEl.height = rect.height;
        ctx.clearRect(0, 0, canvasEl.width, canvasEl.height);

        detections.forEach(det => {
            // Coordinates are normalized (0-1), scale to canvas size
            const x = det.x * canvasEl.width;
            const y = det.y * canvasEl.height;
            const w = det.w * canvasEl.width;
            const h = det.h * canvasEl.height;

            // Outer glow
            ctx.shadowColor = 'rgba(231, 76, 60, 0.6)';
            ctx.shadowBlur = 12;

            // Box
            ctx.strokeStyle = '#e74c3c';
            ctx.lineWidth = 2;
            ctx.strokeRect(x, y, w, h);

            // Semi-transparent fill
            ctx.shadowBlur = 0;
            ctx.fillStyle = 'rgba(231, 76, 60, 0.08)';
            ctx.fillRect(x, y, w, h);

            // Corner accents (top-left and bottom-right)
            ctx.strokeStyle = '#ff6b6b';
            ctx.lineWidth = 3;
            const corner = 12;
            // Top-left
            ctx.beginPath();
            ctx.moveTo(x, y + corner); ctx.lineTo(x, y); ctx.lineTo(x + corner, y);
            ctx.stroke();
            // Top-right
            ctx.beginPath();
            ctx.moveTo(x + w - corner, y); ctx.lineTo(x + w, y); ctx.lineTo(x + w, y + corner);
            ctx.stroke();
            // Bottom-left
            ctx.beginPath();
            ctx.moveTo(x, y + h - corner); ctx.lineTo(x, y + h); ctx.lineTo(x + corner, y + h);
            ctx.stroke();
            // Bottom-right
            ctx.beginPath();
            ctx.moveTo(x + w - corner, y + h); ctx.lineTo(x + w, y + h); ctx.lineTo(x + w, y + h - corner);
            ctx.stroke();

            // Label
            const label = `${det.label} (${det.confidence}%)`;
            ctx.font = 'bold 11px monospace';
            const textW = ctx.measureText(label).width;
            ctx.fillStyle = 'rgba(231, 76, 60, 0.85)';
            ctx.fillRect(x, y - 18, textW + 8, 18);
            ctx.fillStyle = '#fff';
            ctx.fillText(label, x + 4, y - 5);
        });
    }

    // --- Update the Autonomous Safety Loop panel ---
    let wasDetected = false;
    function updateThreatStatus(hasTarget) {
        if (hasTarget && !wasDetected) {
            wasDetected = true;
            autoControlStatus.classList.remove('status-all-clear');
            autoControlStatus.classList.add('status-human-detected');
            autoControlStatus.querySelector('h4').textContent = 'TARGET DETECTED';
            logMessage('Registered obstruction: Human target warning.', 'danger-text');

            actionInterval = setInterval(() => {
                const actionText = correctionActions[currentActionIndex % correctionActions.length];
                autoControlStatus.querySelector('p').textContent = `CORRECTION PATH: ${actionText}`;
                currentActionIndex++;
            }, 1500);
        } else if (!hasTarget && wasDetected) {
            wasDetected = false;
            clearInterval(actionInterval);
            autoControlStatus.classList.remove('status-human-detected');
            autoControlStatus.classList.add('status-all-clear');
            autoControlStatus.querySelector('h4').textContent = 'ALL CLEAR';
            autoControlStatus.querySelector('p').textContent = 'Monitoring flight corridor...';
            logMessage('Corridor clear. Resuming scheduled plan.');
            currentActionIndex = 0;
        }
    }

    // --- Flight diagnostics polling ---
    async function updateFlightDiagnostics() {
        try {
            const flightResponse = await fetch('/api/flight_parameters');
            const flightData = await flightResponse.json();
            if (survAltitude) survAltitude.textContent = `${parseFloat(flightData.altitude).toFixed(1)}m`;
            if (survSpeed) survSpeed.textContent = `${parseFloat(flightData.speed).toFixed(1)} m/s`;
            if (survHeading) survHeading.textContent = `${flightData.heading}°`;
            if (survBattery) survBattery.textContent = `${parseFloat(flightData.battery).toFixed(1)}%`;
        } catch (e) {
            console.error("Flight diagnostics error:", e);
        }
    }

    // --- Start everything ---
    startBrowserCamera();
    updateFlightDiagnostics();
    setInterval(updateFlightDiagnostics, 2000);
}

if (window.location.pathname.includes('/surveillance')) {
    document.addEventListener('DOMContentLoaded', initializeSurveillance);
}