requireLogin();

async function loadDevices() {
  try {
    const o = await api("/me/overview");
    const select = document.getElementById("deviceSelect");
    o.devices.forEach(d => {
      const opt = document.createElement("option");
      opt.value = d.id;
      opt.textContent = `${d.model_name} (${d.serial_no})`;
      select.appendChild(opt);
    });
  } catch (e) { /* the form still works without a device */ }
}

async function loadRequests() {
  const body = document.getElementById("requestsBody");
  try {
    const rows = await api("/service-requests");
    body.innerHTML = rows.map(r => `
      <tr>
        <td>${new Date(r.created_at).toLocaleString()}</td>
        <td>${escapeHtml(r.serial_no || "-")}</td>
        <td><b>${escapeHtml(r.subject)}</b><br><span class="muted">${escapeHtml(r.detail)}</span></td>
        <td>${pill(r.status, REQUEST_TEXT[r.status] || r.status)}</td>
        <td>${escapeHtml(r.admin_note || "-")}</td>
      </tr>`).join("") || `<tr><td colspan="5">ยังไม่มีคำขอ</td></tr>`;
  } catch (err) {
    body.innerHTML = `<tr><td colspan="5">${escapeHtml(err.message)}</td></tr>`;
  }
}

document.getElementById("sendBtn").addEventListener("click", async () => {
  const msg = document.getElementById("formMessage");
  const subject = document.getElementById("subject").value.trim();
  const detail = document.getElementById("detail").value.trim();
  const deviceId = document.getElementById("deviceSelect").value;
  if (!subject || !detail) { msg.textContent = "กรุณากรอกหัวข้อและรายละเอียด"; return; }

  try {
    await api("/service-requests", {
      method: "POST",
      body: JSON.stringify({ subject, detail, device_id: deviceId ? Number(deviceId) : null })
    });
    msg.textContent = "ส่งคำขอเรียบร้อย ทีมงานจะติดต่อกลับ";
    document.getElementById("subject").value = "";
    document.getElementById("detail").value = "";
    loadRequests();
  } catch (err) { msg.textContent = err.message; }
});

loadDevices();
loadRequests();
