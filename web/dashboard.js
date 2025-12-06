const API_URL = 'http://localhost:8000';

// Initialize Chart
const chartContainer = document.getElementById('chart');
const chart = LightweightCharts.createChart(chartContainer, {
    width: chartContainer.clientWidth,
    height: 500,
    layout: {
        background: { type: 'solid', color: '#1e1e1e' },
        textColor: '#d1d4dc',
    },
    grid: {
        vertLines: { color: '#2B2B43' },
        horzLines: { color: '#2B2B43' },
    },
    timeScale: {
        timeVisible: true,
        secondsVisible: false,
    },
});

const candleSeries = chart.addCandlestickSeries({
    upColor: '#4caf50',
    downColor: '#f44336',
    borderDownColor: '#f44336',
    borderUpColor: '#4caf50',
    wickDownColor: '#f44336',
    wickUpColor: '#4caf50',
});

// Resize Observer
new ResizeObserver(entries => {
    if (entries.length === 0 || entries[0].target !== chartContainer) { return; }
    const newRect = entries[0].contentRect;
    chart.applyOptions({ width: newRect.width, height: newRect.height });
}).observe(chartContainer);

// State
let isPaused = false;

async function fetchData() {
    try {
        console.log("Fetching data...");

        // 1. Balance
        const balanceRes = await fetch(`${API_URL}/balance`);
        if (!balanceRes.ok) throw new Error(`Balance API Error: ${balanceRes.status}`);
        const balanceData = await balanceRes.json();
        console.log("Balance Data:", balanceData);

        const balanceEl = document.getElementById('balance-display');
        if (balanceEl) {
            balanceEl.innerText = `$${Number(balanceData.balance).toFixed(2)}`;
            balanceEl.style.color = '#e0e0e0'; // Reset color
        }
        document.getElementById('equity-display').innerText = `Equity: $${Number(balanceData.equity).toFixed(2)}`;

        // 2. Signal
        const signalRes = await fetch(`${API_URL}/live-signal`);
        if (!signalRes.ok) throw new Error(`Signal API Error: ${signalRes.status}`);
        const signalData = await signalRes.json();

        if (signalData.signal_type) {
            const el = document.getElementById('signal-display');
            el.innerText = signalData.signal_type;
            el.className = signalData.signal_type.toLowerCase();
            document.getElementById('signal-prob').innerText = `Prob: ${(signalData.probability * 100).toFixed(1)}%`;

            // Show reason if available, or construct it
            let reason = signalData.reason || "AI Model Decision";
            if (signalData.volatility && signalData.volatility < 0.002) {
                reason = `Low Volatility (${signalData.volatility.toFixed(4)})`;
            }
            document.getElementById('signal-reason').innerText = `Reason: ${reason}`;
        } else {
            document.getElementById('signal-display').innerText = "Waiting...";
            document.getElementById('signal-reason').innerText = "Reason: Analyzing market...";
        }

        // 3. Stats
        const statsRes = await fetch(`${API_URL}/statistics`);
        const statsData = await statsRes.json();
        const pnlEl = document.getElementById('pnl-display');
        pnlEl.innerText = `$${statsData.pnl.toFixed(2)}`;
        pnlEl.style.color = statsData.pnl >= 0 ? '#4caf50' : '#f44336';
        document.getElementById('winrate-display').innerText = `Winrate: ${statsData.winrate}% (${statsData.total_trades} trades)`;

        // 4. Trades
        const tradesRes = await fetch(`${API_URL}/trades`);
        const tradesData = await tradesRes.json();
        const tbody = document.querySelector('#trades-table tbody');
        tbody.innerHTML = '';
        tradesData.forEach((trade, index) => {
            // Calculate unrealized PnL for open trades
            // We check if it's explicitly OPEN, OR if it's the latest trade and it's a BUY (implying open)
            let pnl = trade.pnl;
            if ((trade.status === 'OPEN' || (index === 0 && trade.side === 'BUY')) && signalData.close_price) {
                pnl = (signalData.close_price - trade.price) * trade.amount;
            }

            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${new Date(trade.timestamp).toLocaleTimeString()}</td>
                <td class="${trade.side.toLowerCase()}">${trade.side}</td>
                <td>${trade.price.toFixed(2)}</td>
                <td style="color: ${pnl >= 0 ? '#4caf50' : '#f44336'}">${pnl !== null && pnl !== undefined ? pnl.toFixed(2) : '-'}</td>
                <td>${trade.reason || '-'}</td>
            `;
            tbody.appendChild(row);
        });

        // 5. Chart Data
        const chartRes = await fetch(`${API_URL}/chart-data`);
        const chartData = await chartRes.json();
        if (chartData.length > 0) {
            candleSeries.setData(chartData);

            // Add markers for trades (simplified)
            const markers = [];
            tradesData.forEach(trade => {
                // Find time for marker (approximate match if needed, but here we assume sync)
                // We need unix timestamp for markers
                const tradeTime = new Date(trade.timestamp).getTime() / 1000;
                markers.push({
                    time: tradeTime,
                    position: trade.side === 'BUY' ? 'belowBar' : 'aboveBar',
                    color: trade.side === 'BUY' ? '#2196f3' : '#e91e63',
                    shape: trade.side === 'BUY' ? 'arrowUp' : 'arrowDown',
                    text: trade.side
                });
            });
            // Note: Markers need to be sorted by time and match existing bars. 
            // This is a simplified implementation.
            // candleSeries.setMarkers(markers); 
        }

        // 6. Logs
        const logsRes = await fetch(`${API_URL}/logs`);
        const logsData = await logsRes.json();
        const logsContainer = document.getElementById('logs-container');
        if (logsContainer && logsData.logs) {
            logsContainer.innerHTML = logsData.logs.join('<br>');
            logsContainer.scrollTop = logsContainer.scrollHeight; // Auto scroll to bottom
        }

    } catch (e) {
        console.error("Error fetching data:", e);
        const balanceEl = document.getElementById('balance-display');
        if (balanceEl) {
            balanceEl.innerText = "Error";
            balanceEl.style.color = '#f44336';
        }
    }
}

async function toggleBot() {
    const action = isPaused ? 'resume' : 'pause';
    try {
        const res = await fetch(`${API_URL}/control`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action })
        });
        const data = await res.json();
        if (data.status === 'paused') {
            isPaused = true;
            document.getElementById('bot-status').innerText = "PAUSED";
            document.getElementById('bot-status').className = "status-badge paused";
            document.getElementById('btn-pause').innerText = "RESUME";
        } else {
            isPaused = false;
            document.getElementById('bot-status').innerText = "RUNNING";
            document.getElementById('bot-status').className = "status-badge running";
            document.getElementById('btn-pause').innerText = "PAUSE";
        }
    } catch (e) {
        console.error("Error toggling bot:", e);
    }
}

// Initial Load
fetchData();

// Poll every 3 seconds
setInterval(fetchData, 3000);
