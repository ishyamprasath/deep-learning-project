// static/js/flight_control.js

function initializeFlightControl() {
    const canvas = document.getElementById('lidar-radar');
    const cliInput = document.getElementById('cli-input');
    const cliOutputList = document.getElementById('cli-output-list');
    
    const btnHome = document.getElementById('btn-override-home');
    const btnLand = document.getElementById('btn-override-land');
    const btnKill = document.getElementById('btn-override-kill');
    const btnHover = document.getElementById('btn-hover-halt');

    let radarSweepAngle = 0;
    let obstacleData = [];

    // --- 1. KEYBOARD CONTROLS OVERRIDE ---
    let lastKeySentTime = 0;
    const throttleDelay = 300; // ms to avoid spamming server

    document.addEventListener('keydown', function(e) {
        // Skip keys if typing in CLI input field
        if (document.activeElement === cliInput) return;

        let command = "";
        switch (e.code) {
            case 'ArrowUp':
            case 'KeyW':
                command = "forward";
                break;
            case 'ArrowDown':
            case 'KeyS':
                command = "backward";
                break;
            case 'ArrowLeft':
            case 'KeyA':
                command = "left";
                break;
            case 'ArrowRight':
            case 'KeyD':
                command = "right";
                break;
            case 'KeyQ':
                command = "left"; // rotate left
                break;
            case 'KeyE':
                command = "right"; // rotate right
                break;
            case 'Space':
                e.preventDefault();
                command = "up"; // climb
                break;
            case 'ShiftLeft':
            case 'ShiftRight':
                e.preventDefault();
                command = "down"; // descend
                break;
        }

        if (command) {
            const now = Date.now();
            if (now - lastKeySentTime > throttleDelay) {
                lastKeySentTime = now;
                sendFlightCommand(command, true);
            }
        }
    });

    // --- 2. SEND COMMAND UTILITY ---
    async function sendFlightCommand(commandText, quiet = false) {
        if (!quiet) {
            appendCliLine(`cmd > ${commandText}`, 'command-echo');
        }

        try {
            const response = await fetch('/api/flight_command', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ command: commandText })
            });
            const data = await response.json();
            
            if (data.error) {
                if (!quiet) appendCliLine(`Error: ${data.error}`, 'error-text');
            } else {
                if (!quiet) appendCliLine(data.message, 'success-text');
                // Sync manual parameter displays if main update interval hasn't ticked yet
                if (typeof updateManualControlFlightParams === 'function') {
                    updateManualControlFlightParams();
                }
            }
        } catch (e) {
            console.error("Flight control command failure:", e);
            if (!quiet) appendCliLine("Error: Connection lost to command receiver.", "error-text");
        }
    }

    function appendCliLine(text, className = '') {
        if (!cliOutputList) return;
        const div = document.createElement('div');
        div.textContent = text;
        if (className) div.className = className;
        cliOutputList.appendChild(div);
        cliOutputList.scrollTop = cliOutputList.scrollHeight;
    }

    // --- 3. CLI TERMINAL PROCESSOR ---
    if (cliInput) {
        cliInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                const cmd = cliInput.value.trim();
                if (cmd) {
                    sendFlightCommand(cmd);
                    cliInput.value = '';
                }
            }
        });
    }

    // --- 4. BUTTON TRIGGERS ---
    if (btnHome) {
        btnHome.addEventListener('click', async () => {
            if (confirm("Are you sure you want to delete ALL system logs from the database?")) {
                try {
                    const response = await fetch('/api/override/delete_logs', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' }
                    });
                    const data = await response.json();
                    if (data.status === 'success') {
                        appendCliLine("Purge complete: All database logs cleared.", "success-text");
                    } else {
                        appendCliLine(`Purge failed: ${data.error}`, "error-text");
                    }
                } catch (e) {
                    console.error("Purge request failure:", e);
                    appendCliLine("Error connecting to server for database purge.", "error-text");
                }
            }
        });
    }

    if (btnLand) {
        btnLand.addEventListener('click', async () => {
            appendCliLine("Initiating parallel database backup and purge...", "command-echo");
            try {
                const response = await fetch('/api/override/backup_logs', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                const data = await response.json();
                if (data.status === 'success') {
                    appendCliLine("Backup complete: All logs saved to backup files and purged from DB.", "success-text");
                } else {
                    appendCliLine(`Backup failed: ${data.errors ? data.errors.join(', ') : 'Unknown error'}`, "error-text");
                }
            } catch (e) {
                console.error("Backup request failure:", e);
                appendCliLine("Error connecting to server for parallel backup.", "error-text");
            }
        });
    }

    if (btnHover) btnHover.addEventListener('click', () => sendFlightCommand("set speed 0"));
    if (btnKill) {
        btnKill.addEventListener('click', () => {
            const modal = document.getElementById('emergency-modal-overlay');
            if (modal) {
                modal.classList.add('visible');
            } else {
                if (confirm("Initiate emergency project shutdown sequence?")) {
                    fetch('/api/override/kill_server', { method: 'POST' });
                }
            }
        });
    }

    // --- 5. LIDAR RADAR SIMULATOR ---
    async function fetchObstacles() {
        try {
            const response = await fetch('/api/obstacles');
            obstacleData = await response.json();
        } catch (e) {
            console.error("Failed to retrieve radar obstacles:", e);
        }
    }

    function drawRadar() {
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        const width = canvas.width;
        const height = canvas.height;
        const centerX = width / 2;
        const centerY = height / 2;
        const maxRadius = Math.min(centerX, centerY) - 10;

        ctx.clearRect(0, 0, width, height);

        // 1. Draw range ring circles (Luxurious gold/bronze outline)
        ctx.strokeStyle = '#E2DFD5';
        ctx.lineWidth = 1;
        
        // 5m, 10m, 15m rings
        for (let r = 1; r <= 3; r++) {
            ctx.beginPath();
            ctx.arc(centerX, centerY, (maxRadius / 3) * r, 0, 2 * Math.PI);
            ctx.stroke();
        }

        // 2. Draw cross grid lines
        ctx.beginPath();
        ctx.moveTo(centerX - maxRadius, centerY);
        ctx.lineTo(centerX + maxRadius, centerY);
        ctx.moveTo(centerX, centerY - maxRadius);
        ctx.lineTo(centerX, centerY + maxRadius);
        ctx.stroke();

        // 3. Draw radar sweep shading
        ctx.save();
        ctx.translate(centerX, centerY);
        ctx.rotate(radarSweepAngle);
        
        // Draw elegant gradient sweep wedge
        const gradient = ctx.createRadialGradient(0, 0, 0, 0, 0, maxRadius);
        gradient.addColorStop(0, 'rgba(139, 112, 75, 0.2)');
        gradient.addColorStop(1, 'rgba(139, 112, 75, 0.0)');
        
        ctx.fillStyle = gradient;
        ctx.beginPath();
        ctx.moveTo(0, 0);
        ctx.arc(0, 0, maxRadius, -0.2, 0.2);
        ctx.closePath();
        ctx.fill();
        ctx.restore();

        // Rotate sweep
        radarSweepAngle = (radarSweepAngle + 0.05) % (2 * Math.PI);

        // 4. Draw plotted obstacles (Crimson bordeaux circles)
        obstacleData.forEach(obs => {
            // Distance mapped to radius (cap distance at 15m for radar range)
            const dist = Math.min(obs.distance, 15.0);
            const radiusScale = (dist / 15.0) * maxRadius;
            
            // Calculate coords on canvas based on angle
            // Math.cos expects radians. Angle is relative to drone heading (top of screen = 0 deg)
            const radAngle = (obs.angle - 90) * Math.PI / 180;
            const x = centerX + radiusScale * Math.cos(radAngle);
            const y = centerY + radiusScale * Math.sin(radAngle);

            ctx.beginPath();
            // Draw larger/brighter dots if close (critical distance < 1.5m)
            const isCritical = obs.distance < 1.5;
            ctx.arc(x, y, isCritical ? 5 : 3.5, 0, 2 * Math.PI);
            ctx.fillStyle = isCritical ? '#A63D3D' : '#8B704B';
            ctx.fill();
            
            // If critical, draw a subtle warning border
            if (isCritical) {
                ctx.strokeStyle = 'rgba(166, 61, 61, 0.4)';
                ctx.lineWidth = 2;
                ctx.beginPath();
                ctx.arc(x, y, 9, 0, 2 * Math.PI);
                ctx.stroke();
            }
        });

        // 5. Draw center focal marker (brushed bronze target marker)
        ctx.beginPath();
        ctx.arc(centerX, centerY, 4, 0, 2 * Math.PI);
        ctx.fillStyle = '#8B704B';
        ctx.fill();
        ctx.strokeStyle = '#FFFFFF';
        ctx.lineWidth = 1;
        ctx.stroke();

        requestAnimationFrame(drawRadar);
    }

    // Initialize simulation loops
    fetchObstacles();
    setInterval(fetchObstacles, 1000);
    drawRadar();
}

// Global hook if called from main.js router
window.initializeFlightControl = initializeFlightControl;
