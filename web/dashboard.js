/* ============================================
   AI Trading Bot — Dashboard Controller
   Real-time data polling & UI management
   ============================================ */

const API_URL = 'http://localhost:8000';

// ---- State ----
let isPaused = false;
let currentSymbol = null;
let previousBalance = null;
let chart = null;
let candleSeries = null;

// ---- Clock ----
function updateClock() {
    const now = new Date();
    const h = String(now.getHours()).padStart(2, '0');
    const m = String(now.getMinutes()).padStart(2, '0');
    const s = String(now.getSeconds()).padStart(2, '0');
    document.getElementById('clock').textContent = `${h}:${m}:${s}`;
}
setInterval(updateClock, 1000);
updateClock();

// ---- Chart Initialization ----
function initChart() {
    const container = document.getElementById('chart');
    if (!container || chart) return;

    chart = LightweightCharts.createChart(container, {
        width: container.clientWidth,
        height: container.clientHeight || 460,
        layout: {
            background: { type: 'solid', color: '#131b2b' },
            textColor: '#8b949e',
            fontFamily: "'Inter', sans-serif",
            fontSize: 11,
        },
        grid: {
            vertLines: { color: 'rgba(255,255,255,0.03)' },
            horzLines: { color: 'rgba(255,255,255,0.03)' },
        },
        crosshair: {
            mode: LightweightCharts.CrosshairMode.Normal,
            vertLine: {
                color: 'rgba(99, 148, 255, 0.3)',
                width: 1,
                style: LightweightCharts.LineStyle.Dashed,
                labelBackgroundColor: '#6394ff',
            },
            horzLine: {
                color: 'rgba(99, 148, 255, 0.3)',
                width: 1,
                style: LightweightCharts.LineStyle.Dashed,
                labelBackgroundColor: '#6394ff',
            },
        },
        timeScale: {
            timeVisible: true,
            secondsVisible: false,
            borderColor: 'rgba(255,255,255,0.06)',
            rightOffset: 5,
        },
        rightPriceScale: {
            borderColor: 'rgba(255,255,255,0.06)',
        },
    });

    candleSeries = chart.addCandlestickSeries({
        upColor: '#00d68f',
        downColor: '#ff5c5c',
        borderDownColor: '#ff5c5c',
        borderUpColor: '#00d68f',
        wickDownColor: '#ff5c5c',
        wickUpColor: '#00d68f',
    });

    // Responsive resize
    new ResizeObserver(entries => {
        if (entries.length === 0 || entries[0].target !== container) return;
        const rect = entries[0].contentRect;
        chart.applyOptions({ width: rect.width, height: rect.height });
    }).observe(container);
}

// ---- Utility Functions ----
function formatPrice(price) {
    if (price == null) return '--';
    if (price < 0.01) return price.toFixed(6);
    if (price < 1) return price.toFixed(4);
    if (price < 1000) return price.toFixed(2);
    return price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatPnl(pnl) {
    if (pnl == null) return '--';
    const prefix = pnl >= 0 ? '+' : '';
    if (Math.abs(pnl) < 0.01 && pnl !== 0) return prefix + pnl.toFixed(6);
    return prefix + pnl.toFixed(2);
}

function getSignalClass(signal) {
    if (!signal) return '';
    const s = signal.toUpperCase();
    if (s === 'BUY') return 'signal-buy';
    if (s === 'SELL') return 'signal-sell';
    return 'signal-hold';
}

function getConfidenceLevel(prob) {
    if (prob >= 0.6) return 'high';
    if (prob >= 0.5) return 'medium';
    return 'low';
}

function flashElement(el, className) {
    el.classList.remove(className);
    void el.offsetWidth; // trigger reflow
    el.classList.add(className);
    setTimeout(() => el.classList.remove(className), 800);
}

// ---- Main Data Fetch ----
async function fetchData() {
    try {
        // Parallel fetch for performance
        const [scannerRes, balanceRes, statsRes, tradesRes, logsRes] = await Promise.all([
            fetch(`${API_URL}/scanner`).catch(() => null),
            fetch(`${API_URL}/balance`).catch(() => null),
            fetch(`${API_URL}/statistics`).catch(() => null),
            fetch(`${API_URL}/trades`).catch(() => null),
            fetch(`${API_URL}/logs`).catch(() => null),
        ]);

        // ========== SCANNER ==========
        if (scannerRes && scannerRes.ok) {
            const scannerData = await scannerRes.json();
            renderScanner(scannerData);
        }

        // ========== BALANCE ==========
        if (balanceRes && balanceRes.ok) {
            const data = await balanceRes.json();
            const balanceEl = document.getElementById('balance-display');
            const newBalance = Number(data.balance);

            balanceEl.textContent = `$${formatPrice(newBalance)}`;

            // Flash on change
            if (previousBalance !== null && newBalance !== previousBalance) {
                flashElement(balanceEl, newBalance > previousBalance ? 'flash-green' : 'flash-red');
            }
            previousBalance = newBalance;

            document.getElementById('equity-display').textContent = `Equity: $${formatPrice(Number(data.equity))}`;
        }

        // ========== STATISTICS ==========
        if (statsRes && statsRes.ok) {
            const stats = await statsRes.json();
            const pnlEl = document.getElementById('pnl-display');
            const pnlValue = stats.pnl || 0;

            pnlEl.textContent = `$${formatPnl(pnlValue)}`;
            pnlEl.style.color = pnlValue >= 0 ? 'var(--green)' : 'var(--red)';

            document.getElementById('winrate-display').textContent =
                `Win Rate: ${stats.winrate || 0}% | Trades: ${stats.total_trades || 0}`;
        }

        // ========== TRADES ==========
        if (tradesRes && tradesRes.ok) {
            const trades = await tradesRes.json();
            renderTrades(trades);
        }

        // ========== CHART ==========
        if (currentSymbol) {
            try {
                const chartRes = await fetch(`${API_URL}/chart-data?symbol=${encodeURIComponent(currentSymbol)}`);
                if (chartRes.ok) {
                    const chartData = await chartRes.json();
                    if (chartData.length > 0 && candleSeries) {
                        candleSeries.setData(chartData);
                    }
                }
            } catch (e) { /* silent */ }

            document.getElementById('chart-symbol-label').textContent = currentSymbol;
        }

        // ========== LOGS ==========
        if (logsRes && logsRes.ok) {
            const logsData = await logsRes.json();
            renderLogs(logsData.logs || []);
        }

        // Update timestamp
        const now = new Date();
        document.getElementById('last-update').textContent =
            `Last update: ${now.toLocaleTimeString()}`;

    } catch (e) {
        console.error('Dashboard fetch error:', e);
        document.getElementById('balance-display').textContent = 'Error';
        document.getElementById('balance-display').style.color = 'var(--red)';
    }
}

// ---- Render: Scanner Table ----
function renderScanner(data) {
    const tbody = document.querySelector('#scanner-table tbody');
    if (!data || data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="table-empty">No scanner data available</td></tr>';
        return;
    }

    // Auto-select first symbol
    if (!currentSymbol) currentSymbol = data[0].symbol;

    // Update badge count
    document.getElementById('scanner-count').textContent = `${data.length} pairs`;

    // Count open positions (BUY signals can approximate this)
    const openCount = data.filter(d => d.signal_type === 'BUY').length;
    document.getElementById('positions-display').textContent = `${Math.min(openCount, 3)} / 3`;

    let html = '';
    data.forEach(item => {
        const isActive = currentSymbol === item.symbol;
        const prob = item.probability || 0;
        const pct = (prob * 100).toFixed(1);
        const level = getConfidenceLevel(prob);
        const signalClass = getSignalClass(item.signal_type);

        html += `
            <tr class="scanner-row${isActive ? ' active' : ''}"
                onclick="selectSymbol('${item.symbol}')">
                <td><span class="symbol-name">${item.symbol}</span></td>
                <td><span class="signal-badge ${signalClass}">${item.signal_type}</span></td>
                <td>
                    <div class="confidence-wrapper">
                        <div class="confidence-bar">
                            <div class="confidence-fill ${level}" style="width: ${pct}%"></div>
                        </div>
                        <span class="confidence-value">${pct}%</span>
                    </div>
                </td>
                <td class="hide-mobile" style="font-family: var(--font-mono); font-size: 0.82rem;">
                    $${formatPrice(item.close_price)}
                </td>
                <td>
                    <button class="btn-chart" onclick="event.stopPropagation(); selectSymbol('${item.symbol}')">
                        View
                    </button>
                </td>
            </tr>
        `;
    });

    tbody.innerHTML = html;

    // Update active signal card
    const selected = data.find(d => d.symbol === currentSymbol);
    if (selected) {
        const sigEl = document.getElementById('signal-display');
        sigEl.textContent = `${selected.signal_type}`;
        sigEl.style.color = selected.signal_type === 'BUY' ? 'var(--green)' :
                            selected.signal_type === 'SELL' ? 'var(--red)' : 'var(--yellow)';

        document.getElementById('signal-prob').textContent =
            `Confidence: ${(selected.probability * 100).toFixed(1)}%`;
        document.getElementById('signal-reason').textContent =
            `${selected.symbol} @ $${formatPrice(selected.close_price)}`;
    }
}

// ---- Render: Trades Table ----
function renderTrades(trades) {
    const tbody = document.querySelector('#trades-table tbody');
    if (!trades || trades.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="table-empty">No trades recorded yet</td></tr>';
        return;
    }

    document.getElementById('trades-count').textContent = `${trades.length} trades`;

    let html = '';
    trades.forEach(trade => {
        const time = new Date(trade.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        const sideClass = trade.side.toUpperCase() === 'BUY' ? 'side-buy' : 'side-sell';
        const pnl = trade.pnl;
        const pnlClass = pnl != null ? (pnl >= 0 ? 'pnl-positive' : 'pnl-negative') : '';
        const pnlText = pnl != null ? formatPnl(pnl) : '--';

        html += `
            <tr>
                <td style="color: var(--text-muted); font-family: var(--font-mono); font-size: 0.78rem;">${time}</td>
                <td><span class="symbol-name">${trade.symbol}</span></td>
                <td><span class="${sideClass}">${trade.side}</span></td>
                <td style="font-family: var(--font-mono); font-size: 0.82rem;">$${formatPrice(trade.price)}</td>
                <td class="${pnlClass}" style="font-size: 0.82rem;">${pnlText}</td>
            </tr>
        `;
    });

    tbody.innerHTML = html;
}

// ---- Render: Logs ----
function renderLogs(logs) {
    const container = document.getElementById('logs-container');
    if (!logs || logs.length === 0) {
        container.innerHTML = '<span class="log-line log-dim">No logs available</span>';
        return;
    }

    let html = '';
    logs.forEach(line => {
        // Colorize keywords
        let styledLine = line
            .replace(/BUY/g, '<span class="log-buy">BUY</span>')
            .replace(/SELL/g, '<span class="log-sell">SELL</span>')
            .replace(/ERROR/gi, '<span style="color: var(--red)">ERROR</span>')
            .replace(/WARNING/gi, '<span style="color: var(--yellow)">WARNING</span>');

        html += `<span class="log-line">${styledLine}</span>`;
    });

    container.innerHTML = html;
    container.scrollTop = container.scrollHeight;
}

// ---- Actions ----
function selectSymbol(symbol) {
    currentSymbol = symbol;
    fetchData();
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

        const indicator = document.getElementById('connection-status');
        const statusText = document.getElementById('bot-status-text');
        const btnText = document.getElementById('btn-pause-text');
        const btnIcon = document.getElementById('pause-icon');

        if (data.status === 'paused') {
            isPaused = true;
            indicator.classList.add('paused');
            statusText.textContent = 'PAUSED';
            btnText.textContent = 'RESUME';
            btnIcon.innerHTML = '<polygon points="5 3 19 12 5 21 5 3"></polygon>';
        } else {
            isPaused = false;
            indicator.classList.remove('paused');
            statusText.textContent = 'LIVE';
            btnText.textContent = 'PAUSE';
            btnIcon.innerHTML = '<rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect>';
        }
    } catch (e) {
        console.error('Error toggling bot:', e);
    }
}

// ---- Initialize ----
document.addEventListener('DOMContentLoaded', () => {
    initChart();
    fetchData();

    // Poll every 3 seconds
    setInterval(fetchData, 3000);
});
