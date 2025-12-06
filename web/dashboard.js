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
let currentSymbol = null; // Will be set by scanner

async function fetchData() {
    try {
        console.log("Fetching live data...");

        // 1. Scanner (Priority to set symbol)
        const scannerRes = await fetch(`${API_URL}/scanner`);
        const scannerData = await scannerRes.json();
        const scannerTable = document.querySelector('#scanner-table tbody');
        scannerTable.innerHTML = '';

        let selectedSignal = null;

        scannerData.forEach((item, index) => {
            if (!currentSymbol && index === 0) currentSymbol = item.symbol;

            const isSelected = currentSymbol === item.symbol;
            if (isSelected) selectedSignal = item;

            const row = document.createElement('tr');
            row.style.cursor = 'pointer';
            row.style.backgroundColor = isSelected ? '#2B2B43' : 'transparent';
            row.onclick = () => {
                currentSymbol = item.symbol;
                fetchData(); // Refresh all with new symbol
            };

            row.innerHTML = `
                <td style="font-weight: bold; color: #fff;">${item.symbol}</td>
                <td class="${item.signal_type.toLowerCase()}">${item.signal_type}</td>
                <td>${(item.probability * 100).toFixed(1)}%</td>
                <td>${item.close_price.toFixed(2)}</td>
                <td><button onclick="currentSymbol='${item.symbol}'; fetchData()">VIEW</button></td>
            `;
            scannerTable.appendChild(row);
        });

        // 2. Balance
        const balanceRes = await fetch(`${API_URL}/balance`);
        const balanceData = await balanceRes.json();
        document.getElementById('balance-display').innerText = `$${Number(balanceData.balance).toFixed(2)}`;
        document.getElementById('equity-display').innerText = `Equity: $${Number(balanceData.equity).toFixed(2)}`;

        // 3. Highlighted Signal (Selected Symbol)
        if (selectedSignal) {
            const el = document.getElementById('signal-display');
            el.innerText = `${selectedSignal.symbol}: ${selectedSignal.signal_type}`;
            el.className = selectedSignal.signal_type.toLowerCase();
            document.getElementById('signal-prob').innerText = `Prob: ${(selectedSignal.probability * 100).toFixed(1)}%`;
            document.getElementById('signal-reason').innerText = `Price: ${selectedSignal.close_price}`;
        }

        // 4. Stats
        const statsRes = await fetch(`${API_URL}/statistics`);
        const statsData = await statsRes.json();
        const pnlEl = document.getElementById('pnl-display');
        pnlEl.innerText = `$${statsData.pnl.toFixed(2)}`;
        pnlEl.style.color = statsData.pnl >= 0 ? '#4caf50' : '#f44336';
        document.getElementById('winrate-display').innerText = `Winrate: ${statsData.winrate}% (${statsData.total_trades})`;

        // 5. Trades
        const tradesRes = await fetch(`${API_URL}/trades`);
        const tradesData = await tradesRes.json();
        const tbody = document.querySelector('#trades-table tbody');
        tbody.innerHTML = '';
        tradesData.forEach(trade => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${new Date(trade.timestamp).toLocaleTimeString()}</td>
                <td>${trade.symbol}</td>
                <td class="${trade.side.toLowerCase()}">${trade.side}</td>
                <td>${trade.price.toFixed(2)}</td>
                <td style="color: ${trade.pnl >= 0 ? '#4caf50' : '#f44336'}">${trade.pnl !== null ? trade.pnl.toFixed(2) : '-'}</td>
            `;
            tbody.appendChild(row);
        });

        // 6. Chart Data (Specific Symbol)
        if (currentSymbol) {
            const chartRes = await fetch(`${API_URL}/chart-data?symbol=${encodeURIComponent(currentSymbol)}`);
            const chartData = await chartRes.json();
            if (chartData.length > 0) {
                candleSeries.setData(chartData);
            }
        }

        // 7. Logs
        const logsRes = await fetch(`${API_URL}/logs`);
        const logsData = await logsRes.json();
        const logsContainer = document.getElementById('logs-container');
        if (logsContainer && logsData.logs) {
            logsContainer.innerHTML = logsData.logs.join('<br>');
            logsContainer.scrollTop = logsContainer.scrollHeight;
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
