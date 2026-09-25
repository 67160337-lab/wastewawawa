requireLogin();

let liveTimer = null;
let trendChart = null;
const MAX_POINTS = 30;
const trendData = {
    labels: [],
    doValues: [],
    tempValues: [],
    codValues: [],
    flowValues: [],
    speedValues: []
};

function initChart() {
    const canvas = document.getElementById("trendChart");
    if (!canvas || typeof Chart === "undefined") return;

    trendChart = new Chart(canvas, {
        type: "line",
        data: {
            labels: trendData.labels,
            datasets: [
                { label: "DO (mg/L)", data: trendData.doValues, borderColor: "#116b5b", backgroundColor: "transparent", tension: 0.3, yAxisID: "y" },
                { label: "Temp (°C)", data: trendData.tempValues, borderColor: "#e07a1f", backgroundColor: "transparent", tension: 0.3, yAxisID: "y" },
                { label: "COD (mg/L)", data: trendData.codValues, borderColor: "#7c3aed", backgroundColor: "transparent", tension: 0.3, yAxisID: "y1" },
                { label: "Flow (m³/h)", data: trendData.flowValues, borderColor: "#0ea5e9", backgroundColor: "transparent", tension: 0.3, yAxisID: "y1" },
                { label: "Aerator Speed (%)", data: trendData.speedValues, borderColor: "#dc2626", backgroundColor: "transparent", tension: 0.3, yAxisID: "y1" }
            ]
        },
        options: {
            responsive: true,
            animation: false,
            interaction: { mode: "index", intersect: false },
            scales: {
                y: { type: "linear", position: "left", title: { display: true, text: "DO / Temp" } },
                y1: { type: "linear", position: "right", grid: { drawOnChartArea: false }, title: { display: true, text: "COD / Flow / Speed" } }
            }
        }
    });
}

function pushTrendPoint(data) {
    if (!trendChart) return;

    trendData.labels.push(new Date(data.timestamp).toLocaleTimeString());
    trendData.doValues.push(Number(data.current_do));
    trendData.tempValues.push(Number(data.water_temp));
    trendData.codValues.push(Number(data.influent_cod));
    trendData.flowValues.push(Number(data.flow_rate));
    trendData.speedValues.push(Number(data.predicted_speed));

    if (trendData.labels.length > MAX_POINTS) {
        trendData.labels.shift();
        trendData.doValues.shift();
        trendData.tempValues.shift();
        trendData.codValues.shift();
        trendData.flowValues.shift();
        trendData.speedValues.shift();
    }

    trendChart.update();
}

function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
}

function setGauge(speed) {
    const gauge = document.querySelector(".gauge");
    if (gauge) {
        const safe = Math.max(0, Math.min(100, Number(speed) || 0));
        gauge.style.setProperty("--speed", `${safe * 3.6}deg`);
    }
    setText("gaugeValue", `${Number(speed).toFixed(1)}%`);
}

async function loadDashboard() {
    const user = JSON.parse(localStorage.getItem("user") || "{}");
    setText("username", user.username || "User");

    try {
        const data = await api("/sensor/live");

        setText("doValue", Number(data.current_do).toFixed(2));
        setText("tempValue", Number(data.water_temp).toFixed(2));
        setText("codValue", Number(data.influent_cod).toFixed(1));
        setText("flowValue", Number(data.flow_rate).toFixed(1));
        setText("speedValue", Number(data.predicted_speed).toFixed(1));
        setText("modeValue", data.mode || "AUTO");
        setText("updatedValue", new Date(data.timestamp).toLocaleTimeString());

        const status = document.getElementById("sensorStatus");
        if (status) {
            status.textContent = "● LIVE";
            status.classList.add("live");
        }

        setGauge(data.predicted_speed);
        pushTrendPoint(data);
    } catch (e) {
        console.error(e);
        const status = document.getElementById("sensorStatus");
        if (status) status.textContent = "● OFFLINE";
    }
}

initChart();
loadDashboard();
liveTimer = setInterval(loadDashboard, 2000);
