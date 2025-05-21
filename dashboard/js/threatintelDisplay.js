let threats = [];

window.redirectToSearch = function(searchTerm) {
    window.location.href = `search.html?search=${encodeURIComponent(searchTerm)}`;
};

async function loadThreats() {
    try {
        const response = await fetch('../json/threats.json');
        if (!response.ok) throw new Error('File not found');
        threats = await response.json();
        generateThreatStatistics();
        renderThreatChart();
        renderMaliciousList(threats);
        setupExportButton();
    } catch (error) {
        console.error('Error:', error);
        document.getElementById('threatStatsGrid').innerHTML = `
            <div class="stat-card error">
                <div class="stat-value">!</div>
                <div class="stat-label">Error</div>
            </div>`;
    }
}

// Threats stats
function generateThreatStatistics() {
    const stats = {
        totalThreats: threats.length,
        benignThreats: threats.filter(threat => threat.verdict === 'benign').length,
        suspiciousThreats: threats.filter(threat => threat.verdict === 'suspicious').length,
        maliciousThreats: threats.filter(threat => threat.verdict === 'malicious').length,
        nefariousThreats: threats.filter(threat => threat.verdict === 'nefarious').length,
    };

    const statsHTML = `
        <div class="stat-card">
            <div class="stat-value">${stats.totalThreats}</div>
            <div class="stat-label">Total Threats</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">${stats.benignThreats}</div>
            <div class="stat-label">Benign</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">${stats.suspiciousThreats}</div>
            <div class="stat-label">Suspicious</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">${stats.maliciousThreats}</div>
            <div class="stat-label">Malicious</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">${stats.nefariousThreats}</div>
            <div class="stat-label">Nefarious</div>
        </div>
    `;

    document.getElementById('threatStatsGrid').innerHTML = statsHTML;
}

function renderThreatChart() {
    const protocolScores = threats.map(threat => threat['protocol-score']);
    const labels = threats.map(threat => threat.ip);

    new Chart(document.getElementById('threatChart'), {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Protocol Score',
                data: protocolScores,
                backgroundColor: '#eb4e4e7c'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    grid: {
                        color: '#f8f9fa'
                    }
                },
                x: {
                    grid: {
                        display: false
                    }
                }
            },
            plugins: {
                legend: {
                    display: false
                }
            }
        }
    });
}

// Threats list
function renderMaliciousList(threatsToRender) {
    const listContainer = document.getElementById('maliciousList');
    listContainer.innerHTML = `
        <table class="log-table">
            <thead>
                <tr>
                    <th>Type</th>
                    <th>IP</th>
                    <th>Verdict</th>
                </tr>
            </thead>
            <tbody>
                ${threatsToRender.map(threat => `
                    <tr>
                        <td>${threat.type.toUpperCase()}</td>
                        <td>
                            <a href="javascript:void(0);" class="ip-link" onclick="redirectToSearch('ip:${threat.ip}')">
                                ${threat.ip}
                            </a>
                        </td>
                        <td>
                            <span class="verdict-tag ${getVerdictClass(threat.verdict)}">
                                ${threat.verdict.toUpperCase()}
                            </span>
                        </td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}

// Export button
function setupExportButton() {
    const exportButton = document.getElementById('exportButton');
    exportButton.onclick = () => {
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-'); 
        const fileName = `melissae-iocs_${timestamp}.json`;

        const dataStr = JSON.stringify(threats, null, 2);
        const dataUri = `data:application/json;charset=utf-8,${encodeURIComponent(dataStr)}`;

        const linkElement = document.createElement('a');
        linkElement.setAttribute('href', dataUri);
        linkElement.setAttribute('download', fileName);
        document.body.appendChild(linkElement);
        linkElement.click();
        document.body.removeChild(linkElement);
    };
}

function getVerdictClass(verdict) {
    const classes = {
        'benign': 'verdict-benign',
        'suspicious': 'verdict-suspicious',
        'malicious': 'verdict-malicious',
        'nefarious': 'verdict-nefarious'
    };
    return classes[verdict.toLowerCase()] || '';
}

// Verdict filtering
document.getElementById('filterType').addEventListener('change', event => {
    const filter = event.target.value;
    const filteredThreats = filter === 'all'
        ? threats
        : threats.filter(threat => threat.verdict.toLowerCase() === filter);

    renderMaliciousList(filteredThreats);
});

loadThreats();
