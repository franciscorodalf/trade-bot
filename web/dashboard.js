/* ============================================
   Polymarket BTC Prediction Bot — Dashboard
   Real-time data polling & chart rendering
   ============================================ */

const API_BASE = window.location.origin;
const POLL_INTERVAL = 5000; // 5 seconds

let equityChart = null;
let calibrationChart = null;

// ---- Initialization ----

document.addEventListener("DOMContentLoaded", () => {
    initCharts();
    fetchAll();
    setInterval(fetchAll, POLL_INTERVAL);
});

function fetchAll() {
    fetchStatus();
    fetchBetStats();
    fetchBalanceHistory();
    fetchBets();
    fetchPredictions();
    fetchModelMetrics();
    document.getElementById("last-update").textContent = new Date().toLocaleTimeString();
}

// ---- API Calls ----

async function fetchJSON(endpoint) {
    try {
        const res = await fetch(`${API_BASE}${endpoint}`);
        if (!res.ok) return null;
        return await res.json();
    } catch {
        return null;
    }
}

async function fetchStatus() {
    const data = await fetchJSON("/api/status");
    if (!data) return;

    const badge = document.getElementById("bot-status");
    badge.textContent = data.status.toUpperCase();
    badge.className = `badge ${data.status}`;

    document.getElementById("bankroll").textContent = `$${data.bankroll.toFixed(2)}`;
    const pnl = data.total_pnl || 0;
    const changeEl = document.getElementById("bankroll-change");
    changeEl.textContent = `${pnl >= 0 ? "+" : ""}$${pnl.toFixed(2)}`;
    changeEl.className = `stat-sub ${pnl >= 0 ? "positive" : "negative"}`;

    document.getElementById("total-pnl").textContent = `${pnl >= 0 ? "+" : ""}$${pnl.toFixed(2)}`;
    document.getElementById("total-pnl").style.color = pnl >= 0 ? "var(--green)" : "var(--red)";

    const returnPct = data.bankroll > 0 ? ((data.bankroll - 100) / 100 * 100) : 0;
    const returnEl = document.getElementById("return-pct");
    returnEl.textContent = `${returnPct >= 0 ? "+" : ""}${returnPct.toFixed(1)}%`;
    returnEl.className = `stat-sub ${returnPct >= 0 ? "positive" : "negative"}`;

    document.getElementById("win-rate").textContent = `${(data.win_rate * 100).toFixed(1)}%`;
    document.getElementById("total-bets").textContent = data.total_bets;
    document.getElementById("pending-bets").textContent = `${data.pending_bets} pending`;
}

async function fetchBetStats() {
    const data = await fetchJSON("/api/bets/stats");
    if (!data) return;

    document.getElementById("win-loss").textContent = `${data.wins}W / ${data.losses}L`;
    document.getElementById("avg-edge").textContent = `${(data.avg_edge * 100).toFixed(1)}%`;
    document.getElementById("avg-bet").textContent = `Avg bet: $${data.avg_bet_size.toFixed(2)}`;
}

async function fetchBalanceHistory() {
    const data = await fetchJSON("/api/balance?limit=200");
    if (!data || data.length === 0) return;
    updateEquityChart(data);
}

async function fetchBets() {
    const data = await fetchJSON("/api/bets?limit=20");
    if (!data) return;
    updateBetsTable(data);
}

async function fetchPredictions() {
    const data = await fetchJSON("/api/predictions?limit=1");
    if (!data || data.length === 0) return;
    updatePrediction(data[0]);
}

async function fetchModelMetrics() {
    const data = await fetchJSON("/api/model/metrics");
    if (!data || data.error) return;
    if (data.calibration) updateCalibrationChart(data.calibration);
}

// ---- Chart Initialization ----

function initCharts() {
    const chartDefaults = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { display: false },
        },
        scales: {
            x: {
                ticks: { color: "#64748b", font: { size: 10 } },
                grid: { color: "rgba(42,58,78,0.3)" },
            },
            y: {
                ticks: { color: "#64748b", font: { size: 10 } },
                grid: { color: "rgba(42,58,78,0.3)" },
            },
        },
    };

    // Equity chart
    const eqCtx = document.getElementById("equity-chart").getContext("2d");
    equityChart = new Chart(eqCtx, {
        type: "line",
        data: {
            labels: [],
            datasets: [{
                data: [],
                borderColor: "#3b82f6",
                backgroundColor: "rgba(59,130,246,0.1)",
                fill: true,
                tension: 0.3,
                pointRadius: 0,
                borderWidth: 2,
            }],
        },
        options: {
            ...chartDefaults,
            scales: {
                ...chartDefaults.scales,
                y: {
                    ...chartDefaults.scales.y,
                    ticks: {
                        ...chartDefaults.scales.y.ticks,
                        callback: (v) => `$${v.toFixed(0)}`,
                    },
                },
            },
        },
    });

    // Calibration chart
    const calCtx = document.getElementById("calibration-chart").getContext("2d");
    calibrationChart = new Chart(calCtx, {
        type: "scatter",
        data: {
            datasets: [
                {
                    label: "Calibration",
                    data: [],
                    backgroundColor: "#a855f7",
                    pointRadius: 6,
                },
                {
                    label: "Perfect",
                    data: Array.from({ length: 11 }, (_, i) => ({ x: i / 10, y: i / 10 })),
                    borderColor: "rgba(255,255,255,0.2)",
                    borderDash: [5, 5],
                    pointRadius: 0,
                    type: "line",
                    fill: false,
                },
            ],
        },
        options: {
            ...chartDefaults,
            plugins: { legend: { display: false } },
            scales: {
                x: {
                    ...chartDefaults.scales.x,
                    title: { display: true, text: "Predicted", color: "#64748b" },
                    min: 0, max: 1,
                },
                y: {
                    ...chartDefaults.scales.y,
                    title: { display: true, text: "Actual", color: "#64748b" },
                    min: 0, max: 1,
                },
            },
        },
    });
}

// ---- UI Updates ----

function updateEquityChart(data) {
    const labels = data.map((d) => {
        const date = new Date(d.timestamp);
        return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    });
    const values = data.map((d) => d.bankroll);

    equityChart.data.labels = labels;
    equityChart.data.datasets[0].data = values;

    // Color based on performance
    const last = values[values.length - 1];
    const first = values[0];
    const color = last >= first ? "#22c55e" : "#ef4444";
    const bgColor = last >= first ? "rgba(34,197,94,0.1)" : "rgba(239,68,68,0.1)";
    equityChart.data.datasets[0].borderColor = color;
    equityChart.data.datasets[0].backgroundColor = bgColor;

    equityChart.update("none");
}

function updateCalibrationChart(cal) {
    if (!cal.bin_centers) return;
    const points = cal.bin_centers.map((c, i) => ({ x: c, y: cal.bin_actuals[i] }));
    calibrationChart.data.datasets[0].data = points;
    calibrationChart.update("none");
}

function updatePrediction(pred) {
    const signalEl = document.getElementById("pred-signal");
    signalEl.textContent = pred.signal;
    signalEl.className = `pred-value signal ${pred.signal.toLowerCase()}`;

    document.getElementById("pred-prob").textContent =
        `${(pred.calibrated_probability * 100).toFixed(1)}%`;

    const conf = pred.confidence || 0;
    document.getElementById("confidence-fill").style.width = `${conf * 200}%`;

    const edgeUpEl = document.getElementById("pred-edge-up");
    edgeUpEl.textContent = `${(pred.edge_up * 100).toFixed(1)}%`;
    edgeUpEl.style.color = pred.edge_up > 0 ? "var(--green)" : "var(--text-muted)";

    const edgeDownEl = document.getElementById("pred-edge-down");
    edgeDownEl.textContent = `${(pred.edge_down * 100).toFixed(1)}%`;
    edgeDownEl.style.color = pred.edge_down > 0 ? "var(--green)" : "var(--text-muted)";

    document.getElementById("pred-action").textContent = pred.action_taken;
    document.getElementById("pred-action").style.color =
        pred.action_taken === "BET" ? "var(--green)" : "var(--text-muted)";

    if (pred.btc_price) {
        document.getElementById("btc-price").textContent =
            `BTC $${pred.btc_price.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
    }
}

function updateBetsTable(bets) {
    const tbody = document.getElementById("bets-table");
    if (!bets.length) {
        tbody.innerHTML = '<tr><td colspan="7" class="empty">No bets yet</td></tr>';
        return;
    }

    tbody.innerHTML = bets.map((bet) => {
        const time = new Date(bet.timestamp).toLocaleTimeString();
        const sideClass = bet.side === "UP" ? "side-up" : "side-down";
        const resultClass = bet.result === "WIN" ? "result-win" :
            bet.result === "LOSS" ? "result-loss" : "result-pending";
        const pnlClass = bet.pnl > 0 ? "pnl-positive" : bet.pnl < 0 ? "pnl-negative" : "";

        return `<tr>
            <td>${time}</td>
            <td class="${sideClass}">${bet.side}</td>
            <td>$${bet.amount.toFixed(2)}</td>
            <td>${(bet.edge * 100).toFixed(1)}%</td>
            <td>$${(bet.btc_price_at_bet || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}</td>
            <td class="${resultClass}">${bet.result}</td>
            <td class="${pnlClass}">${bet.pnl >= 0 ? "+" : ""}$${bet.pnl.toFixed(2)}</td>
        </tr>`;
    }).join("");
}
