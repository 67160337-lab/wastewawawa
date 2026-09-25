requireLogin();

let historyChart = null;

function renderHistoryChart(rows) {
  const canvas = document.getElementById("historyChart");
  if (!canvas || typeof Chart === "undefined") return;

  // rows come newest-first; charts read better chronologically (oldest -> newest).
  const chronological = [...rows].reverse();
  const labels = chronological.map(r => new Date(r.created_at).toLocaleString());
  const speeds = chronological.map(r => Number(r.predicted_speed));

  if (historyChart) {
    historyChart.data.labels = labels;
    historyChart.data.datasets[0].data = speeds;
    historyChart.update();
    return;
  }

  historyChart = new Chart(canvas, {
    type: "line",
    data: {
      labels,
      datasets: [{
        label: "Predicted Aerator Speed (%)",
        data: speeds,
        borderColor: "#116b5b",
        backgroundColor: "#116b5b22",
        fill: true,
        tension: 0.3
      }]
    },
    options: {
      responsive: true,
      scales: { y: { min: 0, max: 100, title: { display: true, text: "Speed (%)" } } }
    }
  });
}

async function loadHistory(){
  const body = document.getElementById("history");
  try {
    const rows = await api("/predictions");
    body.innerHTML = rows.map(r => `
      <tr>
        <td>${new Date(r.created_at).toLocaleString()}</td>
        <td>${r.influent_cod}</td>
        <td>${r.flow_rate}</td>
        <td>${r.water_temp}</td>
        <td>${r.current_do}</td>
        <td><b>${r.predicted_speed}%</b></td>
      </tr>
    `).join("") || '<tr><td colspan="6">No prediction records</td></tr>';

    renderHistoryChart(rows);
  } catch(err) { body.innerHTML = `<tr><td colspan="6">${err.message}</td></tr>`; }
}
loadHistory();
