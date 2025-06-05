let aggregatedLogs = [];
let aggregatedThreats = [];
let instancesData = [];
let currentViewMode = 'aggregated';

window.redirectToSearch = function(searchTerm) {
    window.location.href = `search.html?search=${encodeURIComponent(searchTerm)}`;
};

class MultiInstanceDashboard {
    constructor() {
        this.serverURL = this.detectServerURL();
        this.apiKey = null;
        this.setupEventListeners();
        this.loadConfig();
    }

    detectServerURL() {
        // Try to detect server URL from current location or config
        const currentHost = window.location.hostname;
        const port = 8888; // Default multi-instance server port
        return `http://${currentHost}:${port}`;
    }

    async loadConfig() {
        try {
            // Try to load configuration
            const response = await fetch('../multi-instance.json');
            if (response.ok) {
                const config = await response.json();
                this.apiKey = config.server?.api_key;
                if (config.server?.port) {
                    const currentHost = window.location.hostname;
                    this.serverURL = `http://${currentHost}:${config.server.port}`;
                }
            }
        } catch (error) {
            console.warn('Could not load multi-instance config, using defaults');
        }
        
        this.loadData();
    }

    setupEventListeners() {
        document.getElementById('refreshBtn').addEventListener('click', () => {
            this.loadData();
        });

        document.getElementById('viewModeSelect').addEventListener('change', (e) => {
            currentViewMode = e.target.value;
            this.updateView();
        });
    }

    async loadData() {
        await Promise.all([
            this.loadAggregatedData(),
            this.loadInstancesStatus()
        ]);
        this.updateView();
    }

    async loadAggregatedData() {
        try {
            // Try to load from multi-instance server first
            if (this.apiKey) {
                const response = await fetch(`${this.serverURL}/api/aggregated`, {
                    headers: {
                        'Authorization': `Bearer ${this.apiKey}`,
                        'Content-Type': 'application/json'
                    }
                });
                
                if (response.ok) {
                    const data = await response.json();
                    aggregatedLogs = data.logs || [];
                    aggregatedThreats = data.threats || [];
                    console.log('Loaded data from multi-instance server');
                    return;
                }
            }

            // Fallback to local aggregated files
            const [logsResponse, threatsResponse] = await Promise.all([
                fetch('json/logs-aggregated.json').catch(() => fetch('json/logs.json')),
                fetch('json/threats-aggregated.json').catch(() => fetch('json/threats.json'))
            ]);

            if (logsResponse.ok) {
                aggregatedLogs = await logsResponse.json();
            }
            if (threatsResponse.ok) {
                aggregatedThreats = await threatsResponse.json();
            }

            console.log('Loaded data from local files');
        } catch (error) {
            console.error('Error loading aggregated data:', error);
            this.showError('Failed to load aggregated data');
        }
    }

    async loadInstancesStatus() {
        try {
            // First try to load from local file (updated by aggregator)
            const localInstancesResponse = await fetch('json/multi-instance.json');
            if (localInstancesResponse.ok) {
                const localData = await localInstancesResponse.json();
                if (localData.instances && localData.instances.length > 0) {
                    instancesData = localData.instances;
                    return;
                }
            }
            
            if (!this.apiKey) {
                instancesData = [{
                    instance_id: 'local',
                    hostname: 'localhost',
                    last_seen: new Date().toISOString(),
                    stats: {
                        log_count: aggregatedLogs.length,
                        threat_count: aggregatedThreats.length
                    }
                }];
                return;
            }

            const response = await fetch(`${this.serverURL}/api/instances`, {
                headers: {
                    'Authorization': `Bearer ${this.apiKey}`,
                    'Content-Type': 'application/json'
                }
            });

            if (response.ok) {
                const data = await response.json();
                instancesData = data.instances || [];
            }
        } catch (error) {
            console.error('Error loading instances status:', error);
            instancesData = [];
        }
    }

    updateView() {
        this.generateMultiInstanceStatistics();
        this.renderInstancesStatus();
        this.renderCharts();
        
        const detailsContainer = document.getElementById('instancesDetails');
        if (currentViewMode === 'by-instance') {
            detailsContainer.style.display = 'block';
            this.renderInstancesBreakdown();
        } else {
            detailsContainer.style.display = 'none';
        }
    }

    generateMultiInstanceStatistics() {
        const stats = {
            totalLogs: aggregatedLogs.length,
            totalThreats: aggregatedThreats.length,
            connectedInstances: instancesData.length,
            uniqueIPs: new Set(aggregatedLogs.map(log => log.ip)).size,
            crossInstanceIPs: this.getCrossInstanceIPs(),
            nefariousThreats: aggregatedThreats.filter(t => t.verdict === 'nefarious').length,
            maliciousThreats: aggregatedThreats.filter(t => t.verdict === 'malicious').length,
            suspiciousThreats: aggregatedThreats.filter(t => t.verdict === 'suspicious').length,
            recentActivity: this.getRecentActivity()
        };

        const statsHTML = `
            <div class="stat-card multi-instance clickable" onclick="dashboard.showInstanceDetails()">
                <div class="stat-value">${stats.connectedInstances}</div>
                <div class="stat-label">Connected Instances</div>
            </div>
            <div class="stat-card cross-instance clickable" onclick="dashboard.showCrossInstanceIPs()">
                <div class="stat-value">${stats.crossInstanceIPs}</div>
                <div class="stat-label">Cross-Instance IPs</div>
            </div>
            <div class="stat-card clickable" onclick="window.location.href='dashboard.html'">
                <div class="stat-value">${stats.totalLogs}</div>
                <div class="stat-label">Total Logs (All Instances)</div>
            </div>
            <div class="stat-card clickable" onclick="window.location.href='threat-intel.html'">
                <div class="stat-value">${stats.uniqueIPs}</div>
                <div class="stat-label">Unique Threat IPs</div>
            </div>
            <div class="stat-card ${stats.nefariousThreats > 0 ? 'alert' : 'success'} clickable" onclick="dashboard.filterThreats('nefarious')">
                <div class="stat-value">${stats.nefariousThreats}</div>
                <div class="stat-label">Nefarious Threats</div>
            </div>
            <div class="stat-card ${stats.maliciousThreats > 0 ? 'alert' : 'success'} clickable" onclick="dashboard.filterThreats('malicious')">
                <div class="stat-value">${stats.maliciousThreats}</div>
                <div class="stat-label">Malicious Threats</div>
            </div>
            <div class="stat-card clickable" onclick="dashboard.filterThreats('suspicious')">
                <div class="stat-value">${stats.suspiciousThreats}</div>
                <div class="stat-label">Suspicious IPs</div>
            </div>
            <div class="stat-card clickable" onclick="dashboard.showRecentActivity()">
                <div class="stat-value">${stats.recentActivity}</div>
                <div class="stat-label">Last Hour Activity</div>
            </div>
        `;

        document.getElementById('multiStatsGrid').innerHTML = statsHTML;
    }

    getCrossInstanceIPs() {
        const ipInstances = {};
        aggregatedLogs.forEach(log => {
            const ip = log.ip;
            const instanceId = log.instance_id || 'local';
            if (!ipInstances[ip]) {
                ipInstances[ip] = new Set();
            }
            ipInstances[ip].add(instanceId);
        });

        return Object.values(ipInstances).filter(instances => instances.size > 1).length;
    }

    getRecentActivity() {
        const oneHourAgo = new Date(Date.now() - 60 * 60 * 1000);
        return aggregatedLogs.filter(log => {
            try {
                const logDate = new Date(`${log.date} ${log.hour}`);
                return logDate >= oneHourAgo;
            } catch {
                return false;
            }
        }).length;
    }

    renderInstancesStatus() {
        if (instancesData.length === 0) {
            document.getElementById('instancesGrid').innerHTML = `
                <div class="instance-card">
                    <div class="instance-info">No instances connected</div>
                </div>
            `;
            return;
        }

        const instancesHTML = instancesData.map(instance => {
            const lastSeen = new Date(instance.last_seen);
            const now = new Date();
            const timeDiff = now - lastSeen;
            const isOnline = timeDiff < 5 * 60 * 1000; // 5 minutes
            const isStale = timeDiff < 15 * 60 * 1000; // 15 minutes
            
            let statusClass = 'offline';
            if (isOnline) statusClass = 'online';
            else if (isStale) statusClass = 'stale';

            const instanceId = instance.instance_id || 'unknown';
            const shortId = instanceId.substring(0, 8);

            return `
                <div class="instance-card">
                    <div class="instance-header">
                        <div class="instance-id">${shortId}</div>
                        <div class="instance-status ${statusClass}"></div>
                    </div>
                    <div class="instance-hostname">${instance.hostname || 'Unknown'}</div>
                    <div class="instance-last-seen">Last seen: ${this.formatTimestamp(lastSeen)}</div>
                    <div class="instance-stats">
                        <div class="instance-stat">
                            <div class="instance-stat-value">${instance.stats?.log_count || 0}</div>
                            <div class="instance-stat-label">Logs</div>
                        </div>
                        <div class="instance-stat">
                            <div class="instance-stat-value">${instance.stats?.threat_count || 0}</div>
                            <div class="instance-stat-label">Threats</div>
                        </div>
                    </div>
                </div>
            `;
        }).join('');

        document.getElementById('instancesGrid').innerHTML = instancesHTML;
    }

    renderInstancesBreakdown() {
        const breakdownHTML = instancesData.map(instance => {
            const instanceLogs = aggregatedLogs.filter(log => 
                (log.instance_id || 'local') === instance.instance_id
            );
            const instanceThreats = aggregatedThreats.filter(threat => 
                (threat.instance_id || 'local') === instance.instance_id
            );

            const stats = {
                http: instanceLogs.filter(log => log.protocol === 'http').length,
                ssh: instanceLogs.filter(log => log.protocol === 'ssh').length,
                ftp: instanceLogs.filter(log => log.protocol === 'ftp').length,
                modbus: instanceLogs.filter(log => log.protocol === 'modbus').length,
                uniqueIPs: new Set(instanceLogs.map(log => log.ip)).size,
                nefarious: instanceThreats.filter(t => t.verdict === 'nefarious').length
            };

            const instanceId = instance.instance_id || 'unknown';
            const shortId = instanceId.substring(0, 8);
            const lastSeen = new Date(instance.last_seen);
            const statusClass = (Date.now() - lastSeen) < 5 * 60 * 1000 ? 'online' : 'offline';

            return `
                <div class="instance-breakdown-card">
                    <div class="instance-breakdown-header">
                        <div class="instance-breakdown-title">${shortId} - ${instance.hostname}</div>
                        <div class="instance-breakdown-status">
                            <div class="instance-status ${statusClass}"></div>
                            ${statusClass === 'online' ? 'Online' : 'Offline'}
                        </div>
                    </div>
                    <div class="breakdown-stats-grid">
                        <div class="breakdown-stat">
                            <div class="breakdown-stat-value">${stats.http}</div>
                            <div class="breakdown-stat-label">HTTP Logs</div>
                        </div>
                        <div class="breakdown-stat">
                            <div class="breakdown-stat-value">${stats.ssh}</div>
                            <div class="breakdown-stat-label">SSH Logs</div>
                        </div>
                        <div class="breakdown-stat">
                            <div class="breakdown-stat-value">${stats.ftp}</div>
                            <div class="breakdown-stat-label">FTP Logs</div>
                        </div>
                        <div class="breakdown-stat">
                            <div class="breakdown-stat-value">${stats.modbus}</div>
                            <div class="breakdown-stat-label">Modbus Logs</div>
                        </div>
                        <div class="breakdown-stat">
                            <div class="breakdown-stat-value">${stats.uniqueIPs}</div>
                            <div class="breakdown-stat-label">Unique IPs</div>
                        </div>
                        <div class="breakdown-stat ${stats.nefarious > 0 ? 'alert' : ''}">
                            <div class="breakdown-stat-value">${stats.nefarious}</div>
                            <div class="breakdown-stat-label">Nefarious</div>
                        </div>
                    </div>
                </div>
            `;
        }).join('');

        document.getElementById('instancesBreakdown').innerHTML = breakdownHTML;
    }

    renderCharts() {
        this.renderActivityChart();
        this.renderProtocolChart();
        this.renderThreatsChart();
    }

    renderActivityChart() {
        const canvas = document.getElementById('multiActivityChart');
        const ctx = canvas.getContext('2d');
        
        // Clear any existing chart
        if (canvas.chart) {
            canvas.chart.destroy();
        }

        const hours = Array.from({length: 24}, (_, i) => `${i}h`);
        const activityData = new Array(24).fill(0);
        
        aggregatedLogs.forEach(log => {
            try {
                const hour = parseInt(log.hour.split(':')[0]);
                if (hour >= 0 && hour < 24) {
                    activityData[hour]++;
                }
            } catch {
                // Ignore invalid time formats
            }
        });

        canvas.chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: hours,
                datasets: [{
                    label: 'Activity (All Instances)',
                    data: activityData,
                    borderColor: '#eb4e4e7c',
                    backgroundColor: 'rgba(235, 78, 78, 0.1)',
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                layout: {
                    padding: {
                        top: 20,
                        bottom: 20
                    }
                },
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

    renderProtocolChart() {
        const canvas = document.getElementById('multiProtocolChart');
        const ctx = canvas.getContext('2d');
        
        if (canvas.chart) {
            canvas.chart.destroy();
        }

        const protocolData = {
            ssh: aggregatedLogs.filter(log => log.protocol === 'ssh').length,
            ftp: aggregatedLogs.filter(log => log.protocol === 'ftp').length,
            http: aggregatedLogs.filter(log => log.protocol === 'http').length,
            modbus: aggregatedLogs.filter(log => log.protocol === 'modbus').length
        };

        canvas.chart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['SSH', 'FTP', 'HTTP', 'Modbus'],
                datasets: [{
                    data: [protocolData.ssh, protocolData.ftp, protocolData.http, protocolData.modbus],
                    backgroundColor: ['#aab2c2', '#b3c2aa', "#b2aac2", "#c2aab2"]
                }]
            },
            options: {
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        });
    }

    renderThreatsChart() {
        const canvas = document.getElementById('multiThreatsChart');
        const ctx = canvas.getContext('2d');
        
        if (canvas.chart) {
            canvas.chart.destroy();
        }

        // Get top threats by activity count
        const topThreats = aggregatedThreats
            .filter(threat => threat.activity_count > 0)
            .sort((a, b) => (b.activity_count || 0) - (a.activity_count || 0))
            .slice(0, 5);

        if (topThreats.length === 0) {
            // No threat data available
            canvas.chart = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: ['No Data'],
                    datasets: [{
                        data: [1],
                        backgroundColor: ['#f0f0f0']
                    }]
                },
                options: {
                    plugins: {
                        legend: {
                            display: false
                        }
                    }
                }
            });
            return;
        }

        const colors = ['#eca1a1', '#b7afaf', '#9a5555', '#5d5a5a', '#b12929'];

        canvas.chart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: topThreats.map(threat => threat.ip),
                datasets: [{
                    data: topThreats.map(threat => threat.activity_count || 0),
                    backgroundColor: colors.slice(0, topThreats.length)
                }]
            },
            options: {
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            boxWidth: 15,
                            padding: 15
                        }
                    }
                }
            }
        });
    }

    formatTimestamp(date) {
        const now = new Date();
        const diff = now - date;
        
        if (diff < 60 * 1000) {
            return 'Just now';
        } else if (diff < 60 * 60 * 1000) {
            const minutes = Math.floor(diff / (60 * 1000));
            return `${minutes} minute${minutes === 1 ? '' : 's'} ago`;
        } else if (diff < 24 * 60 * 60 * 1000) {
            const hours = Math.floor(diff / (60 * 60 * 1000));
            return `${hours} hour${hours === 1 ? '' : 's'} ago`;
        } else {
            return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
        }
    }

    showError(message) {
        document.getElementById('multiStatsGrid').innerHTML = `
            <div class="stat-card error">
                <div class="stat-value">!</div>
                <div class="stat-label">${message}</div>
            </div>
        `;
    }
    
    showInstanceDetails() {
        // Switch to by-instance view
        document.getElementById('viewModeSelect').value = 'by-instance';
        currentViewMode = 'by-instance';
        this.updateView();
        
        // Scroll to instances section
        document.getElementById('instancesStatus').scrollIntoView({ behavior: 'smooth' });
    }
    
    showCrossInstanceIPs() {
        // Find IPs that appear in multiple instances
        const ipInstances = {};
        aggregatedLogs.forEach(log => {
            const ip = log.ip;
            const instanceId = log.instance_id || 'local';
            if (!ipInstances[ip]) {
                ipInstances[ip] = new Set();
            }
            ipInstances[ip].add(instanceId);
        });
        
        const crossInstanceIPs = Object.entries(ipInstances)
            .filter(([ip, instances]) => instances.size > 1)
            .map(([ip, instances]) => ip);
        
        if (crossInstanceIPs.length > 0) {
            // Redirect to search with cross-instance IPs
            const searchQuery = crossInstanceIPs.join(' OR ');
            window.location.href = `search.html?search=${encodeURIComponent(searchQuery)}`;
        } else {
            alert('No IPs found across multiple instances');
        }
    }
    
    filterThreats(verdict) {
        // Redirect to threat intel page with filter
        window.location.href = `threat-intel.html?verdict=${verdict}`;
    }
    
    showRecentActivity() {
        // Show logs from the last hour
        const oneHourAgo = new Date(Date.now() - 60 * 60 * 1000);
        const timeFilter = oneHourAgo.toISOString().split('T')[0] + ' ' + oneHourAgo.toTimeString().split(' ')[0];
        window.location.href = `search.html?search=${encodeURIComponent('after:' + timeFilter)}`;
    }
}

// Initialize dashboard when page loads
const dashboard = new MultiInstanceDashboard();
document.addEventListener('DOMContentLoaded', () => {
    // Dashboard is already initialized
});