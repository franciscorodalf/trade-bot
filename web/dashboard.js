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
            if (!currentSymbol && index === 0) {
                currentSymbol = item.symbol;
                document.getElementById('chart-symbol').innerText = ` // ${currentSymbol}`;
            }

            const isSelected = currentSymbol === item.symbol;
            if (isSelected) selectedSignal = item;

            const row = document.createElement('tr');
            row.style.cursor = 'pointer';
            row.style.backgroundColor = isSelected ? '#2B2B43' : 'transparent';
            row.onclick = () => {
                currentSymbol = item.symbol;
                document.getElementById('chart-symbol').innerText = ` // ${currentSymbol}`;
                fetchData(); // Refresh all with new symbol
            };

            const prob = (item.probability * 100).toFixed(1);
            const signalClass = item.signal_type === 'BUY' ? 'buy-text' : (item.signal_type === 'SELL' ? 'sell-text' : 'hold-text');
            const barColor = item.signal_type === 'BUY' ? 'var(--neon-green)' : (item.signal_type === 'SELL' ? 'var(--neon-red)' : '#666');

            row.innerHTML = `
                <td>${item.symbol}</td>
                <td class="${signalClass}">${item.signal_type}</td>
                <td>
                    ${prob}%
                    <div class="conf-bar-bg">
                        <div class="conf-bar-fill" style="width: ${prob}%; background-color: ${barColor};"></div>
                    </div>
                </td>
                <td><button class="btn-action" onclick="currentSymbol='${item.symbol}'; fetchData()">VIEW</button></td>
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
            el.innerText = `${selectedSignal.symbol} ${selectedSignal.signal_type}`;
            el.className = selectedSignal.signal_type === 'BUY' ? 'highlight-number buy-text' : (selectedSignal.signal_type === 'SELL' ? 'highlight-number sell-text' : 'highlight-number hold-text');

            document.getElementById('signal-prob').innerText = `Prob: ${(selectedSignal.probability * 100).toFixed(1)}%`;
            document.getElementById('signal-reason').innerText = `Price: ${selectedSignal.close_price < 1 ? selectedSignal.close_price.toFixed(8) : selectedSignal.close_price.toFixed(2)}`;
        }

        // 4. Stats
        const statsRes = await fetch(`${API_URL}/statistics`);
        const statsData = await statsRes.json();
        const pnlEl = document.getElementById('pnl-display');
        const pnlValue = statsData.pnl;
        // Adjust precision based on magnitude
        pnlEl.innerText = `$${Math.abs(pnlValue) < 0.01 && pnlValue !== 0 ? pnlValue.toFixed(8) : pnlValue.toFixed(2)}`;
        pnlEl.style.color = pnlValue >= 0 ? '#4caf50' : '#f44336';
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
                <td>${trade.price < 1 ? trade.price.toFixed(8) : trade.price.toFixed(2)}</td>
                <td>$${trade.cost ? trade.cost.toFixed(2) : '-'}</td>
                <td style="color: ${trade.pnl >= 0 ? '#4caf50' : '#f44336'}">${trade.pnl !== null ? trade.pnl.toFixed(8) : '-'}</td>
            `;
            tbody.appendChild(row);
        });

        // 6. Chart Data (Specific Symbol)
        if (currentSymbol) {
            // Fetch Candles
            const chartRes = await fetch(`${API_URL}/chart-data?symbol=${encodeURIComponent(currentSymbol)}`);
            const chartData = await chartRes.json();
            if (chartData.length > 0) {
                candleSeries.setData(chartData);
            }

            // Fetch and Set Markers (Trades)
            const symbolTradesRes = await fetch(`${API_URL}/trades?symbol=${encodeURIComponent(currentSymbol)}&limit=100`);
            const symbolTrades = await symbolTradesRes.json();

            const markers = symbolTrades.map(trade => {
                const isBuy = trade.side === "BUY";
                // Convert timestamp (YYYY-MM-DD HH:MM:SS) to match chart time (unix timestamp)
                // Note: stored timestamp is string, chart expects unix timestamp or string. 
                // We assume chartData uses unix timestamps, so we convert trade time.
                const tradeTime = new Date(trade.timestamp).getTime() / 1000;

                return {
                    time: tradeTime,
                    position: isBuy ? 'belowBar' : 'aboveBar',
                    color: isBuy ? '#2196F3' : '#E91E63', // Blue for Buy, Pink/Red for Sell
                    shape: isBuy ? 'arrowUp' : 'arrowDown',
                    text: `${trade.side} @ ${trade.price}`
                };
            }).sort((a, b) => a.time - b.time); // Markers must be sorted by time

            candleSeries.setMarkers(markers);
        }

        // 7. Logs
        const logsRes = await fetch(`${API_URL}/logs`);
        const logsData = await logsRes.json();
        const logsContainer = document.getElementById('logs-container');
        if (logsContainer && logsData.logs) {
            logsContainer.innerHTML = logsData.logs.map(log => {
                // Formatting log line to look like terminal
                // Assume log format: YYYY-MM-DD HH:MM:SS,mmm [LEVEL] Message
                const parts = log.split('] ');
                if (parts.length > 1) {
                    const meta = parts[0] + ']';
                    const msg = parts.slice(1).join('] ');
                    return `<div class="log-line"><span class="time">${meta}</span> ${msg}</div>`;
                }
                return `<div class="log-line">${log}</div>`;
            }).join('');
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
