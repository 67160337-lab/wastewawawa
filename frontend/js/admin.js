requireLogin();

const me = currentUser();

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

(async () => {
  const ok = await requireAdmin();
  if (!ok) return;
  loadUsers();
  loadAllWater();
  loadAllPredictions();
})();
