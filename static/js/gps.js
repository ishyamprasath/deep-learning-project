// static/js/gps.js

function initializeGpsConsole() {
    const mapElement = document.getElementById('gps-map');
    if (!mapElement) return; // Only run if the map element exists on the page

    // --- STATE ---
    let map = L.map('gps-map').setView([37.7749, -122.4194], 13); // Default to San Francisco
    let pointMarkers = [];
    let centralMarker = null;

    // --- INITIALIZE MAP (LIGHT LUXE THEME MAP TILES) ---
    L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
        attribution: '© OpenStreetMap contributors © CARTO',
        subdomains: 'abcd',
        maxZoom: 20
    }).addTo(map);

    // --- UI ELEMENTS ---
    const geocodeForm = document.getElementById('geocode-form');
    const addressInput = document.getElementById('address-input');
    const tableBody = document.getElementById('gps-table-body');
    const tableSubtitle = document.getElementById('gps-table-subtitle');
    const statsMostAccurate = document.getElementById('stats-most-accurate');
    const statsCoverage = document.getElementById('stats-coverage-area');
    const statsAvgAccuracy = document.getElementById('stats-avg-accuracy');
    const statsDataQuality = document.getElementById('stats-data-quality');

    // --- CORE LOGIC ---
    async function fetchAndRenderPoints(lat, lon) {
        tableSubtitle.textContent = 'Generating scan coordinates...';
        tableBody.innerHTML = `<tr><td colspan="6" style="text-align: center; padding: 40px; color: var(--text-secondary);">Loading coordinates...</td></tr>`;
        resetStats();
        clearMarkers();

        try {
            const response = await fetch('/api/generate_gps_points', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ lat, lon }),
            });

            if (!response.ok) throw new Error('Failed to generate coordinates from register.');
            
            const points = await response.json();
            tableBody.innerHTML = '';

            points.forEach(point => {
                tableBody.innerHTML += `<tr>
                    <td>${point.id}</td>
                    <td>${point.lat.toFixed(6)}°</td>
                    <td>${point.lon.toFixed(6)}°</td>
                    <td>${point.alt}</td>
                    <td>${point.acc}</td>
                    <td class="good-text">${point.quality}</td>
                </tr>`;
                
                // Draw elegant bronze markers on map
                const marker = L.circleMarker([point.lat, point.lon], {
                    radius: 5,
                    color: '#8B704B',
                    fillColor: '#8B704B',
                    fillOpacity: 0.6,
                    weight: 1
                }).addTo(map);
                pointMarkers.push(marker);
            });
            
            // Add a special marker for the coordinate focal point
            centralMarker = L.marker([lat, lon], {
                icon: L.divIcon({
                    className: 'central-marker',
                    html: '<div style="background-color: #8B704B; width: 12px; height: 12px; border-radius: 50%; border: 2px solid white; box-shadow: 0 2px 5px rgba(0,0,0,0.2);"></div>',
                    iconSize: [12, 12]
                })
            }).addTo(map);

            map.setView([lat, lon], 16);
            tableSubtitle.textContent = `${points.length} points generated`;
            calculateAndUpdateStats(points);
            
            // Re-fetch logged threats to update overlay
            fetchAndOverlayThreats();

        } catch (error) {
            console.error(error);
            tableSubtitle.textContent = 'Failed to scan coordinates';
            tableBody.innerHTML = `<tr><td colspan="6" style="text-align: center; padding: 40px; color: var(--accent-red);">${error.message}</td></tr>`;
        }
    }
    
    function calculateAndUpdateStats(points) {
        if (!points || points.length === 0) return;

        let minAcc = Infinity;
        let totalAcc = 0;
        
        points.forEach(p => {
            const accValue = parseFloat(p.acc.replace('±', '').replace('m', ''));
            totalAcc += accValue;
            if (accValue < minAcc) minAcc = accValue;
        });

        const avgAcc = totalAcc / points.length;
        
        statsMostAccurate.textContent = `±${minAcc.toFixed(2)}m`;
        statsAvgAccuracy.textContent = `±${avgAcc.toFixed(2)}m`;
        statsDataQuality.textContent = 'Excellent';
        statsCoverage.textContent = '50m Grid';
    }

    // Overlay logged threats from database onto coordinates map
    async function fetchAndOverlayThreats() {
        try {
            const res = await fetch('/api/logs?table=threat_logs&limit=30');
            const threats = await res.json();
            threats.forEach(t => {
                if (t.lat && t.lon) {
                    L.circle([t.lat, t.lon], {
                        color: '#A63D3D',
                        fillColor: '#A63D3D',
                        fillOpacity: 0.15,
                        weight: 1.5,
                        radius: 20
                    }).addTo(map).bindPopup(`
                        <div style="font-family: var(--font-family); font-size: 12px; color: var(--text-primary);">
                            <strong style="color: var(--accent-red); font-family: var(--font-serif); font-size: 13px;">Security Event: ${t.type}</strong><br>
                            <b>Description:</b> ${t.details}<br>
                            <b>Confidence:</b> ${t.confidence}%<br>
                            <b>Registered:</b> ${t.timestamp}
                        </div>
                    `);
                }
            });
        } catch (e) {
            console.error("Failed to load historical security threats:", e);
        }
    }

    function resetStats() {
        statsMostAccurate.textContent = '0.0m';
        statsAvgAccuracy.textContent = '0.0m';
        statsDataQuality.textContent = 'Pending';
        statsCoverage.textContent = '0m';
    }

    function clearMarkers() {
        pointMarkers.forEach(marker => map.removeLayer(marker));
        pointMarkers = [];
        if (centralMarker) {
            map.removeLayer(centralMarker);
            centralMarker = null;
        }
    }

    // --- EVENT LISTENERS ---
    map.on('click', e => fetchAndRenderPoints(e.latlng.lat, e.latlng.lng));

    if (geocodeForm) {
        geocodeForm.addEventListener('submit', async e => {
            e.preventDefault();
            const address = addressInput.value;
            if (!address) return;

            tableSubtitle.textContent = `Searching location...`;
            
            try {
                const response = await fetch('/api/geocode', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ address }),
                });
                const data = await response.json();
                if (data.error) throw new Error(data.error);
                
                fetchAndRenderPoints(data.lat, data.lon);

            } catch (error) {
                console.error(error);
                tableSubtitle.textContent = `Search failed: ${error.message}`;
            }
        });
    }

    // Load initial coordinate state
    resetStats();
    fetchAndOverlayThreats();
}

// Ensure this only runs on the GPS Console page.
if (window.location.pathname.includes('/gps-console')) {
    document.addEventListener('DOMContentLoaded', initializeGpsConsole);
}