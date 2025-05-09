class CoinFlipClient {
    constructor() {
        this.serverUrl = 'http://localhost:5000/api';
        this.updateInterval = 100; // 100ms update interval
        this.lastFlipTime = null;
        this.updateTimer = null;
        this.retryDelay = 5000; // 5 seconds before retry on error
        this.maxRetries = 3;
        this.connected = false;
        
        // Check for authentication
        const token = localStorage.getItem('token');
        if (!token) {
            console.log('No authentication token found');
            window.location.href = 'login.html';
            return;
        }
    }

    destroy() {
        if (this.updateTimer) {
            clearInterval(this.updateTimer);
            this.updateTimer = null;
        }
    }

    async getStatus(retries = 0) {
        try {
            const token = localStorage.getItem('token');
            if (!token) {
                console.log('Token missing, redirecting to login');
                window.location.href = 'login.html';
                return null;
            }

            const response = await fetch(`${this.serverUrl}/status`, {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                }
            });
            
            if (response.status === 401) {
                console.log('Authentication failed, redirecting to login');
                localStorage.removeItem('token');
                localStorage.removeItem('username');
                window.location.href = 'login.html';
                return null;
            }

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            if (!this.connected) {
                this.connected = true;
                document.getElementById('status').textContent = 'Connected to server';
            }
            return data;
        } catch (error) {
            console.error('Failed to fetch status:', error);
            document.getElementById('status').textContent = 'Connection error. Retrying...';
            this.connected = false;
            if (retries < this.maxRetries) {
                await new Promise(resolve => setTimeout(resolve, this.retryDelay));
                return this.getStatus(retries + 1);
            }
            document.getElementById('status').textContent = 'Failed to connect to server. Please refresh the page.';
            return null;
        }
    }

    updateDisplay(status) {
        if (!status) return;

        try {
            // Update time and countdown
            document.getElementById('current_time').textContent = status.current_time;
            document.getElementById('countdown').textContent = status.seconds_until_flip;

            // Update stats
            document.getElementById('headsCount').textContent = status.stats.heads;
            document.getElementById('tailsCount').textContent = status.stats.tails;
            document.getElementById('headsPercent').textContent = `${status.stats.heads_percent}`;
            document.getElementById('tailsPercent').textContent = `${status.stats.tails_percent}`;

            // Update user information if available
            if (status.user) {
                const userElement = document.getElementById('current_user');
                if (userElement) {
                    userElement.textContent = `Current User: ${status.user}`;
                }
            }

            // Check for new flip
            const latestFlip = status.history[0];
            if (latestFlip && this.lastFlipTime !== latestFlip.time) {
                this.performFlipAnimation(latestFlip);
                this.lastFlipTime = latestFlip.time;
            }

            // Update history table
            this.updateHistoryTable(status.history);
        } catch (error) {
            console.error('Error updating display:', error);
            document.getElementById('status').textContent = 'Error updating display';
        }
    }

    updateHistoryTable(history) {
        const tbody = document.getElementById('historyBody');
        if (!tbody) return;

        try {
            tbody.innerHTML = '';
            history.forEach(flip => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${flip.time}</td>
                    <td class="${flip.result.toLowerCase()}-result">${flip.result}</td>
                    <td class="mono">${flip.seed}</td>
                    <td class="mono">${flip.hash}</td>
                `;
                tbody.appendChild(row);
            });
        } catch (error) {
            console.error('Error updating history table:', error);
        }
    }

    performFlipAnimation(flipData) {
        const coin = document.getElementById('coin');
        const result = document.getElementById('result');
        const seed = document.getElementById('seed');
        const hash = document.getElementById('hash');
        const lastFlipTime = document.getElementById('lastFlipTime');

        if (!coin || !result || !seed || !hash || !lastFlipTime) return;

        try {
            // Reset coin state
            coin.style.transform = 'rotateY(0deg)';
            coin.classList.remove('flipping');

            // Start the flip animation
            requestAnimationFrame(() => {
                coin.classList.add('flipping');
            });

            // Update displays after animation
            setTimeout(() => {
                result.textContent = `Result: ${flipData.result}!`;
                seed.textContent = flipData.seed;
                hash.textContent = flipData.hash;
                lastFlipTime.textContent = flipData.time;

                coin.classList.remove('flipping');
                coin.style.transform = `rotateY(${flipData.result === 'Heads' ? 0 : 180}deg)`;
            }, 3000);
        } catch (error) {
            console.error('Error performing flip animation:', error);
        }
    }

    async start() {
        try {
            document.getElementById('status').textContent = 'Connecting to server...';

            // Initial status update
            const status = await this.getStatus();
            if (status) {
                this.updateDisplay(status);
            }

            // Set up regular updates
            this.updateTimer = setInterval(async () => {
                const status = await this.getStatus();
                if (status) {
                    this.updateDisplay(status);
                }
            }, this.updateInterval);
        } catch (error) {
            console.error('Error starting client:', error);
            document.getElementById('status').textContent = 'Failed to start client';
        }
    }
}

// Initialize when the page loads
let client = null;

document.addEventListener('DOMContentLoaded', () => {
    client = new CoinFlipClient();
    client.start().catch(error => {
        console.error('Error starting client:', error);
        document.getElementById('status').textContent = 'Failed to initialize client';
    });
});

// Cleanup on page unload
window.addEventListener('unload', () => {
    if (client) {
        client.destroy();
        client = null;
    }
});