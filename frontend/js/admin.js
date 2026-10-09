requireLogin();

const me = currentUser();
let allUsers = [];

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, ch => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[ch]));
}

async function loadUsers() {
  const body = document.getElementById("usersBody");
  const message = document.getElementById("usersMessage");
  try {
    const users = await api("/admin/users");
    allUsers = users;
    fillCustomerSelect();
    body.innerHTML = users.map(u => `
      <tr>
        <td>${u.id}</td>
        <td>${escapeHtml(u.username)}</td>
        <td>${escapeHtml(u.email)}</td>
        <td>${u.is_admin ? "<b>Admin</b>" : "User"}</td>
        <td>${new Date(u.created_at).toLocaleString()}</td>
        <td>
          <button class="button-small" data-action="toggle" data-id="${u.id}" data-admin="${u.is_admin}"
            ${u.id === me.id ? "disabled title=\"Can't change your own role\"" : ""}>
            ${u.is_admin ? "Remove Admin" : "Make Admin"}
          </button>
          <button class="button-small" style="background:#c0392b;margin-left:6px" data-action="delete" data-id="${u.id}"
            ${u.id === me.id ? "disabled title=\"Can't delete your own account\"" : ""}>
            Delete
          </button>
        </td>
      </tr>
    `).join("") || `<tr><td colspan="6">No users found</td></tr>`;
  } catch (err) {
    message.textContent = err.message;
  }
}

async function loadAllWater() {
  const body = document.getElementById("allWaterBody");
  try {
    const rows = await api("/admin/water");
    body.innerHTML = rows.map(r => `
      <tr>
        <td>${new Date(r.created_at).toLocaleString()}</td>
        <td>${escapeHtml(r.username)}</td>
        <td>${r.influent_cod}</td>
        <td>${r.flow_rate}</td>
        <td>${r.water_temp}</td>
        <td>${r.current_do}</td>
        <td>${r.status}</td>
      </tr>
    `).join("") || `<tr><td colspan="7">No records yet</td></tr>`;
  } catch (err) {
    body.innerHTML = `<tr><td colspan="7">${err.message}</td></tr>`;
  }
}

async function loadAllPredictions() {
  const body = document.getElementById("allPredictionsBody");
  try {
    const rows = await api("/admin/predictions");
    body.innerHTML = rows.map(r => `
      <tr>
        <td>${new Date(r.created_at).toLocaleString()}</td>
        <td>${escapeHtml(r.username)}</td>
        <td>${r.influent_cod}</td>
        <td>${r.flow_rate}</td>
        <td>${r.water_temp}</td>
        <td>${r.current_do}</td>
        <td><b>${r.predicted_speed}%</b></td>
      </tr>
    `).join("") || `<tr><td colspan="7">No predictions yet</td></tr>`;
  } catch (err) {
    body.innerHTML = `<tr><td colspan="7">${err.message}</td></tr>`;
  }
}

document.getElementById("usersBody").addEventListener("click", async (e) => {
  const btn = e.target.closest("button[data-action]");
  if (!btn) return;

  const message = document.getElementById("usersMessage");
  const id = Number(btn.dataset.id);

  try {
    if (btn.dataset.action === "toggle") {
      const currentlyAdmin = btn.dataset.admin === "true";
      await api(`/admin/users/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ is_admin: !currentlyAdmin })
      });
    } else if (btn.dataset.action === "delete") {
      if (!confirm("Delete this user and all of their records? This cannot be undone.")) return;
      await api(`/admin/users/${id}`, { method: "DELETE" });
      await loadAllWater();
      await loadAllPredictions();
    }
    message.textContent = "";
    await loadUsers();
  } catch (err) {
    message.textContent = err.message;
  }
});

async function loadExplain() {
  const box = document.getElementById("explainResult");
  box.innerHTML = "Checking...";
  try {
    const plans = await api("/admin/explain");
    if (!Array.isArray(plans)) {
      box.innerHTML = `<p class="muted">${plans.message}</p>`;
      return;
    }
    box.innerHTML = plans.map(p => `
      <div style="margin-bottom:14px">
        <strong>${escapeHtml(p.query)}</strong>
        <pre style="background:#0f172a;color:#e2e8f0;padding:10px;border-radius:8px;overflow:auto;margin-top:6px;font-size:13px">${escapeHtml(p.plan.join("\n"))}</pre>
      </div>
    `).join("");
  } catch (err) {
    box.innerHTML = `<p class="muted">${err.message}</p>`;
  }
}




// ---------------------------------------------------------------------------
// Admin dashboard: KPIs, machines, service requests
// ---------------------------------------------------------------------------
function fmtTime(iso) { return iso ? new Date(iso).toLocaleString() : "-"; }

function fillCustomerSelect() {
  const sel = document.getElementById("dUser");
  if (!sel) return;
  const keep = sel.value;
  sel.innerHTML = `<option value="">ยังไม่ผูกลูกค้า</option>` +
    allUsers.map(u => `<option value="${u.id}">${escapeHtml(u.username)}</option>`).join("");
  sel.value = keep;
}

async function loadOverview() {
  try {
    const o = await api("/admin/overview");
    const k = o.kpis;
    const set = (id, v) => { document.getElementById(id).textContent = v; };
    set("kCustomers", k.customers);
    set("kDevices", k.devices_total);
    set("kUnassigned", k.devices_unassigned ? `ยังไม่ผูกลูกค้า ${k.devices_unassigned}` : "");
    set("kAlert", k.devices_critical + k.devices_warning);
    set("kCritical", k.devices_critical ? `วิกฤต ${k.devices_critical}` : "");
    set("kRequests", k.open_requests);
    set("kOffline", k.devices_offline);
    set("kWarranty", k.warranty_expiring_30d);
    set("kExpired", k.warranty_expired ? `หมดประกันแล้ว ${k.warranty_expired}` : "");
    set("kReadings", k.readings_24h);
    document.getElementById("kAlertBox").classList.toggle("alert", k.devices_critical + k.devices_warning > 0);
    document.getElementById("kReqBox").classList.toggle("alert", k.open_requests > 0);

    document.getElementById("attentionBody").innerHTML = o.attention.map(d => `
      <tr>
        <td>${escapeHtml(d.serial_no)}</td>
        <td>${escapeHtml(d.owner || "-")}</td>
        <td>${pill(d.level, d.label)}</td>
        <td>${d.reading ? d.reading.current_do : "-"}</td>
        <td>${fmtTime(d.last_seen)}</td>
      </tr>`).join("") || `<tr><td colspan="5">ไม่มีเครื่องที่ต้องดูแลเป็นพิเศษ 🎉</td></tr>`;
  } catch (err) {
    document.getElementById("attentionBody").innerHTML = `<tr><td colspan="5">${escapeHtml(err.message)}</td></tr>`;
  }
}

function warrantyCell(d) {
  if (d.warranty_days_left === null) return "-";
  if (d.warranty_days_left < 0) return `${escapeHtml(d.warranty_until)} ${pill("crit", "หมดแล้ว")}`;
  if (d.warranty_days_left <= 30) return `${escapeHtml(d.warranty_until)} ${pill("warn", `เหลือ ${d.warranty_days_left} วัน`)}`;
  return escapeHtml(d.warranty_until);
}

async function loadDevices() {
  const body = document.getElementById("devicesBody");
  try {
    const devices = await api("/admin/devices");
    body.innerHTML = devices.map(d => `
      <tr>
        <td>${escapeHtml(d.serial_no)}</td>
        <td>${escapeHtml(d.model_name)}</td>
        <td>
          <select data-action="assign" data-id="${d.id}">
            <option value="">ยังไม่ผูกลูกค้า</option>
            ${allUsers.map(u => `<option value="${u.id}" ${u.id === d.user_id ? "selected" : ""}>${escapeHtml(u.username)}</option>`).join("")}
          </select>
        </td>
        <td>${pill(d.level, d.label)}</td>
        <td>${warrantyCell(d)}</td>
        <td><button class="button-small btn-danger" data-action="delete-device" data-id="${d.id}">ลบ</button></td>
      </tr>`).join("") || `<tr><td colspan="6">ยังไม่มีเครื่อง เพิ่มเครื่องแรกได้จากฟอร์มด้านบน</td></tr>`;
  } catch (err) {
    body.innerHTML = `<tr><td colspan="6">${escapeHtml(err.message)}</td></tr>`;
  }
}

async function loadRequests() {
  const body = document.getElementById("requestsBody");
  const status = document.getElementById("reqFilter").value;
  try {
    const rows = await api("/admin/service-requests" + (status ? `?status=${status}` : ""));
    body.innerHTML = rows.map(r => `
      <tr data-id="${r.id}">
        <td>${fmtTime(r.created_at)}</td>
        <td>${escapeHtml(r.username)}<br><span class="muted">${escapeHtml(r.serial_no || "ไม่ระบุเครื่อง")}</span></td>
        <td><b>${escapeHtml(r.subject)}</b><br><span class="muted">${escapeHtml(r.detail)}</span></td>
        <td>
          <select data-field="status">
            ${Object.entries(REQUEST_TEXT).map(([v, label]) => `<option value="${v}" ${v === r.status ? "selected" : ""}>${label}</option>`).join("")}
          </select>
        </td>
        <td><input data-field="note" value="${escapeHtml(r.admin_note || "")}" placeholder="ข้อความถึงลูกค้า" maxlength="2000"></td>
        <td><button class="button-small" data-action="save-request" data-id="${r.id}">บันทึก</button></td>
      </tr>`).join("") || `<tr><td colspan="6">ไม่มีคำขอ</td></tr>`;
  } catch (err) {
    body.innerHTML = `<tr><td colspan="6">${escapeHtml(err.message)}</td></tr>`;
  }
}

document.getElementById("addDeviceBtn").addEventListener("click", async () => {
  const msg = document.getElementById("deviceMessage");
  const serial = document.getElementById("dSerial").value.trim();
  const model = document.getElementById("dModel").value.trim();
  if (!serial || !model) { msg.textContent = "กรุณากรอก Serial และรุ่น"; return; }
  const userId = document.getElementById("dUser").value;
  const date = document.getElementById("dDate").value;
  try {
    await api("/admin/devices", {
      method: "POST",
      body: JSON.stringify({
        serial_no: serial,
        model_name: model,
        user_id: userId ? Number(userId) : null,
        purchased_at: date || null,
        warranty_months: Number(document.getElementById("dWarranty").value || 0)
      })
    });
    msg.textContent = "";
    document.getElementById("dSerial").value = "";
    document.getElementById("dModel").value = "";
    await Promise.all([loadDevices(), loadOverview()]);
  } catch (err) { msg.textContent = err.message; }
});

document.getElementById("devicesBody").addEventListener("change", async (e) => {
  const sel = e.target.closest("select[data-action='assign']");
  if (!sel) return;
  const msg = document.getElementById("deviceMessage");
  try {
    await api(`/admin/devices/${sel.dataset.id}`, {
      method: "PATCH",
      body: JSON.stringify({ user_id: sel.value ? Number(sel.value) : null })
    });
    msg.textContent = "";
    await Promise.all([loadDevices(), loadOverview()]);
  } catch (err) { msg.textContent = err.message; }
});

document.getElementById("devicesBody").addEventListener("click", async (e) => {
  const btn = e.target.closest("button[data-action='delete-device']");
  if (!btn) return;
  if (!confirm("ลบเครื่องนี้ออกจากระบบ? ประวัติข้อมูลคุณภาพน้ำจะยังอยู่ แต่ไม่ผูกกับเครื่องแล้ว")) return;
  try {
    await api(`/admin/devices/${btn.dataset.id}`, { method: "DELETE" });
    await Promise.all([loadDevices(), loadOverview()]);
  } catch (err) { document.getElementById("deviceMessage").textContent = err.message; }
});

document.getElementById("requestsBody").addEventListener("click", async (e) => {
  const btn = e.target.closest("button[data-action='save-request']");
  if (!btn) return;
  const row = btn.closest("tr");
  const msg = document.getElementById("requestMessage");
  try {
    await api(`/admin/service-requests/${btn.dataset.id}`, {
      method: "PATCH",
      body: JSON.stringify({
        status: row.querySelector("[data-field='status']").value,
        admin_note: row.querySelector("[data-field='note']").value
      })
    });
    msg.textContent = "";
    await Promise.all([loadRequests(), loadOverview()]);
  } catch (err) { msg.textContent = err.message; }
});

document.getElementById("reqFilter").addEventListener("change", loadRequests);

(async () => {
  const ok = await requireAdmin();
  if (!ok) return;
  await loadUsers();            // fills allUsers for the customer dropdowns
  loadOverview();
  loadDevices();
  loadRequests();
  loadAllWater();
  loadAllPredictions();
  setInterval(loadOverview, 30000);
})();
