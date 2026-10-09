// Same-origin API: works locally in Docker and on Render.
const API = "";

function token() {
    return localStorage.getItem("token") || "";
}

async function api(path, options = {}) {
    options.headers = {
        "Content-Type": "application/json",
        ...(options.headers || {})
    };

    const t = token();
    if (t) {
        options.headers["Authorization"] = `Bearer ${t}`;
    }

    const response = await fetch(API + path, options);
    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
        throw new Error(data.detail || "Request failed");
    }

    return data;
}

function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, ch => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    }[ch]));
}

const LEVEL_TEXT = { ok: "ปกติ", warn: "ควรเฝ้าระวัง", crit: "วิกฤต", offline: "ไม่ส่งข้อมูล", nodata: "ยังไม่มีข้อมูล" };
const REQUEST_TEXT = { open: "รอดำเนินการ", in_progress: "กำลังดำเนินการ", closed: "ปิดงานแล้ว" };

function pill(kind, text) {
    return `<span class="pill ${escapeHtml(kind)}">${escapeHtml(text)}</span>`;
}

function requireLogin() {
    if (!token()) {
        window.location.href = "index.html";
    }
}

function currentUser() {
    try {
        return JSON.parse(localStorage.getItem("user") || "{}");
    } catch (e) {
        return {};
    }
}

function isAdmin() {
    return !!currentUser().is_admin;
}

// Shows the "Admin" sidebar link only for accounts with is_admin = true.
function applyAdminNav() {
    const navLink = document.getElementById("navAdmin");
    if (navLink) {
        navLink.style.display = isAdmin() ? "" : "none";
    }
}

// Re-checks the role with the server (in case it changed after this session's
// login) and keeps the cached user + nav link in sync. Safe to call anywhere.
async function refreshRole() {
    if (!token()) return;
    try {
        const me = await api("/me");
        localStorage.setItem("user", JSON.stringify({ ...currentUser(), ...me }));
    } catch (e) {
        // Keep going with whatever is cached; requireLogin()/requireAdmin() on
        // protected pages will catch a truly invalid session.
    }
    applyAdminNav();
}

// Server-verified guard for admin-only pages. Redirects non-admins away.
async function requireAdmin() {
    if (!token()) {
        window.location.href = "index.html";
        return false;
    }
    try {
        const me = await api("/me");
        localStorage.setItem("user", JSON.stringify({ ...currentUser(), ...me }));
        if (!me.is_admin) {
            window.location.href = "dashboard.html";
            return false;
        }
        return true;
    } catch (e) {
        window.location.href = "index.html";
        return false;
    }
}

function logout() {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    window.location.href = "index.html";
}

// Runs on every page that loads api.js; harmless no-op where there's no nav.
applyAdminNav();
refreshRole();
