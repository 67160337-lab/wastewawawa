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
                { label: "อุณหภูมิ (°C)", data: trendData.tempValues, borderColor: "#e07a1f", backgroundColor: "transparent", tension: 0.3, yAxisID: "y" },
                { label: "COD (mg/L)", data: trendData.codValues, borderColor: "#7c3aed", backgroundColor: "transparent", tension: 0.3, yAxisID: "y1" },
                { label: "อัตราการไหล (m³/h)", data: trendData.flowValues, borderColor: "#0ea5e9", backgroundColor: "transparent", tension: 0.3, yAxisID: "y1" },
                { label: "ความเร็วเครื่องเติมอากาศ (%)", data: trendData.speedValues, borderColor: "#dc2626", backgroundColor: "transparent", tension: 0.3, yAxisID: "y1" }
            ]
        },
        options: {
            responsive: true,
            animation: false,
            interaction: { mode: "index", intersect: false },
            scales: {
                y: { type: "linear", position: "left", title: { display: true, text: "DO / อุณหภูมิ" } },
                y1: { type: "linear", position: "right", grid: { drawOnChartArea: false }, title: { display: true, text: "COD / การไหล / ความเร็ว" } }
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


// ---------------------------------------------------------------------------
// Customer overview: status banner, my machine(s), 24h summary.
// Refreshed less often than the live sensor because it reads saved history.
// ---------------------------------------------------------------------------
function renderBanner(current, hasDevice) {
    const box = document.getElementById("statusBanner");
    const icon = { ok: "✓", warn: "!", crit: "!", none: "…" };
    const level = current ? current.level : "none";
    box.className = `banner ${level}`;
    document.getElementById("bannerDot").textContent = icon[level];

    if (!current) {
        document.getElementById("bannerTitle").textContent = "ยังไม่มีข้อมูลจากเครื่อง";
        document.getElementById("bannerAdvice").innerHTML =
            `<p>${hasDevice ? "รอข้อมูลชุดแรกจากเซนเซอร์" : "บัญชีนี้ยังไม่ได้ผูกกับเครื่องบำบัดน้ำ กรุณาติดต่อผู้จำหน่าย"}</p>`;
        return;
    }
    document.getElementById("bannerTitle").textContent = `สถานะระบบ: ${current.label}`;
    document.getElementById("bannerAdvice").innerHTML =
        current.advice.map(a => `<p>${escapeHtml(a)}</p>`).join("");
}

function warrantyText(d) {
    if (d.warranty_days_left === null) return "-";
    if (d.warranty_days_left < 0) return `หมดประกันแล้ว (${d.warranty_until})`;
    return `ถึง ${d.warranty_until} (เหลือ ${d.warranty_days_left} วัน)`;
}

function renderDevices(devices) {
    const box = document.getElementById("deviceList");
    if (!devices.length) {
        box.innerHTML = `<p class="muted">ยังไม่มีเครื่องที่ผูกกับบัญชีนี้</p>`;
        return;
    }
    box.innerHTML = devices.map(d => `
        <div class="device-card">
            <div class="panel-title"><strong>${escapeHtml(d.model_name)}</strong>${pill(d.level, d.label)}</div>
            <dl class="kv">
                <dt>Serial</dt><dd>${escapeHtml(d.serial_no)}</dd>
                <dt>วันที่ซื้อ</dt><dd>${escapeHtml(d.purchased_at || "-")}</dd>
                <dt>ประกัน</dt><dd>${escapeHtml(warrantyText(d))}</dd>
            </dl>
        </div>`).join("");
}

function renderSummary(s, openRequests) {
    const dl = document.getElementById("summary24");
    if (!s.readings) {
        dl.innerHTML = `<dt>ยังไม่มีข้อมูลใน 24 ชั่วโมงที่ผ่านมา</dt><dd></dd>`;
    } else {
        dl.innerHTML = `
            <dt>จำนวนการวัด</dt><dd>${s.readings} ครั้ง</dd>
            <dt>ช่วงที่ระบบปกติ</dt><dd>${s.normal_percent}%</dd>
            <dt>DO เฉลี่ย</dt><dd>${s.avg_do} mg/L</dd>
            <dt>COD เฉลี่ย</dt><dd>${s.avg_cod} mg/L</dd>
            <dt>อุณหภูมิเฉลี่ย</dt><dd>${s.avg_temp} °C</dd>
            <dt>อัตราการไหลเฉลี่ย</dt><dd>${s.avg_flow} m³/h</dd>`;
    }
    document.getElementById("requestNote").innerHTML = openRequests
        ? `มีคำขอแจ้งซ่อมที่ยังไม่ปิด ${openRequests} รายการ — <a href="support.html">ดูสถานะ</a>`
        : `พบปัญหากับเครื่อง? <a href="support.html">แจ้งซ่อม / ติดต่อฝ่ายบริการ</a>`;
}

async function loadOverview() {
    try {
        const o = await api("/me/overview");
        renderBanner(o.current, o.devices.length > 0);
        renderDevices(o.devices);
        renderSummary(o.last_24h, o.open_requests);
    } catch (e) {
        console.error(e);
    }
}

loadOverview();
setInterval(loadOverview, 30000);
