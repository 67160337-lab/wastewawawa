requireLogin();

const ORDER_TEXT = { pending: "รอยืนยัน", confirmed: "ยืนยันแล้ว", shipped: "จัดส่งแล้ว", completed: "สำเร็จ", cancelled: "ยกเลิก" };
const baht = n => "฿" + Number(n).toLocaleString("th-TH", { maximumFractionDigits: 2 });

let products = [];
const cart = {};   // product_id -> quantity

function recommendedId() {
    const flow = parseFloat(document.getElementById("flowInput").value);
    if (!(flow > 0)) return null;
    const fit = products
        .filter(p => p.max_flow_m3h !== null && p.max_flow_m3h >= flow && p.stock > 0)
        .sort((a, b) => a.max_flow_m3h - b.max_flow_m3h)[0];
    return fit ? fit.id : null;
}

function renderProducts() {
    const grid = document.getElementById("productGrid");
    const reco = recommendedId();
    const flow = parseFloat(document.getElementById("flowInput").value);
    document.getElementById("recoNote").textContent =
        flow > 0 ? (reco ? "" : "ไม่มีรุ่นที่รองรับอัตราการไหลนี้ในสต็อกตอนนี้ กรุณาติดต่อทีมงาน") : "";

    if (!products.length) {
        grid.innerHTML = `<p class="muted">ยังไม่มีสินค้าให้เลือกในขณะนี้</p>`;
        return;
    }
    grid.innerHTML = products.map(p => `
        <div class="product ${p.id === reco ? "recommended" : ""}">
            ${p.id === reco ? pill("ok", "เหมาะกับระบบของคุณ") : ""}
            <h4>${escapeHtml(p.name)}</h4>
            <span class="muted">${escapeHtml(p.model_code)}</span>
            <div class="price">${baht(p.price)}</div>
            <ul>
                ${p.max_flow_m3h !== null ? `<li>รองรับอัตราการไหลถึง ${p.max_flow_m3h} m³/h</li>` : ""}
                ${p.airflow_m3min !== null ? `<li>ปริมาณลม ${p.airflow_m3min} m³/min</li>` : ""}
                ${p.power_kw !== null ? `<li>กำลังมอเตอร์ ${p.power_kw} kW</li>` : ""}
                <li>รับประกัน ${p.warranty_months} เดือน พร้อมใช้ Dashboard</li>
            </ul>
            ${p.description ? `<p class="muted" style="margin:0;font-size:14px">${escapeHtml(p.description)}</p>` : ""}
            <span class="note">${p.stock > 0 ? `มีสินค้า ${p.stock} เครื่อง` : "สินค้าหมด"}</span>
            <button data-add="${p.id}" ${p.stock > 0 ? "" : "disabled"}>เพิ่มลงตะกร้า</button>
        </div>`).join("");
}

function renderCart() {
    const lines = Object.entries(cart);
    const box = document.getElementById("cartLines");
    if (!lines.length) {
        box.innerHTML = `<p class="muted">ยังไม่มีสินค้าในตะกร้า</p>`;
        document.getElementById("cartTotal").textContent = "";
        return;
    }
    let total = 0;
    box.innerHTML = lines.map(([id, qty]) => {
        const p = products.find(x => x.id === Number(id));
        total += p.price * qty;
        return `<div class="cart-line">
            <span>${escapeHtml(p.name)}<br><span class="muted">${baht(p.price)} / เครื่อง</span></span>
            <span><input type="number" min="1" max="${p.stock}" value="${qty}" data-qty="${p.id}">
            <button class="button-small btn-light" data-remove="${p.id}">ลบ</button></span>
        </div>`;
    }).join("");
    document.getElementById("cartTotal").textContent = "รวม " + baht(total);
}

function renderOrders(orders) {
    const body = document.getElementById("ordersBody");
    body.innerHTML = orders.map(o => `
        <tr>
            <td>${new Date(o.created_at).toLocaleString()}</td>
            <td>${o.items.map(i => `${escapeHtml(i.product_name)} × ${i.quantity}`).join("<br>")}</td>
            <td>${baht(o.total)}</td>
            <td>${pill(o.status, ORDER_TEXT[o.status] || o.status)}</td>
            <td>${o.status === "pending" ? `<button class="button-small btn-light" data-cancel="${o.id}">ยกเลิก</button>` : ""}</td>
        </tr>`).join("") || `<tr><td colspan="5">ยังไม่มีคำสั่งซื้อ</td></tr>`;
}

async function loadOrders() {
    try { renderOrders(await api("/orders")); }
    catch (err) { document.getElementById("ordersBody").innerHTML = `<tr><td colspan="5">${escapeHtml(err.message)}</td></tr>`; }
}

document.getElementById("productGrid").addEventListener("click", e => {
    const btn = e.target.closest("button[data-add]");
    if (!btn) return;
    const id = Number(btn.dataset.add);
    const p = products.find(x => x.id === id);
    cart[id] = Math.min((cart[id] || 0) + 1, p.stock);
    renderCart();
    document.getElementById("cartPanel").scrollIntoView({ behavior: "smooth" });
});

document.getElementById("cartLines").addEventListener("click", e => {
    const btn = e.target.closest("button[data-remove]");
    if (!btn) return;
    delete cart[btn.dataset.remove];
    renderCart();
});

document.getElementById("cartLines").addEventListener("change", e => {
    const input = e.target.closest("input[data-qty]");
    if (!input) return;
    const p = products.find(x => x.id === Number(input.dataset.qty));
    const qty = Math.max(1, Math.min(parseInt(input.value, 10) || 1, p.stock));
    cart[p.id] = qty;
    renderCart();
});

document.getElementById("ordersBody").addEventListener("click", async e => {
    const btn = e.target.closest("button[data-cancel]");
    if (!btn || !confirm("ยกเลิกคำสั่งซื้อนี้?")) return;
    try {
        await api(`/orders/${btn.dataset.cancel}/cancel`, { method: "POST" });
        await Promise.all([loadOrders(), loadProducts()]);
    } catch (err) { document.getElementById("orderMessage").textContent = err.message; }
});

document.getElementById("flowInput").addEventListener("input", renderProducts);

document.getElementById("orderBtn").addEventListener("click", async () => {
    const msg = document.getElementById("orderMessage");
    const items = Object.entries(cart).map(([id, qty]) => ({ product_id: Number(id), quantity: qty }));
    const phone = document.getElementById("phone").value.trim();
    const address = document.getElementById("address").value.trim();
    if (!items.length) { msg.textContent = "กรุณาเลือกสินค้าอย่างน้อย 1 รายการ"; return; }
    if (phone.length < 5 || !address) { msg.textContent = "กรุณากรอกเบอร์โทรและที่อยู่จัดส่ง"; return; }
    try {
        await api("/orders", {
            method: "POST",
            body: JSON.stringify({ items, contact_phone: phone, shipping_address: address, note: document.getElementById("note").value.trim() || null })
        });
        msg.textContent = "ส่งคำสั่งซื้อเรียบร้อย ทีมงานจะติดต่อกลับเพื่อยืนยัน";
        Object.keys(cart).forEach(k => delete cart[k]);
        renderCart();
        await Promise.all([loadOrders(), loadProducts()]);
    } catch (err) { msg.textContent = err.message; }
});

async function loadProducts() {
    try {
        products = await api("/products");
        Object.keys(cart).forEach(id => { if (!products.some(p => p.id === Number(id) && p.stock > 0)) delete cart[id]; });
        renderProducts();
        renderCart();
    } catch (err) {
        document.getElementById("productGrid").innerHTML = `<p class="muted">${escapeHtml(err.message)}</p>`;
    }
}

(async () => {
    // Prefill flow rate from the customer's own latest sensor reading.
    try {
        const o = await api("/me/overview");
        if (o.current && o.current.flow_rate) document.getElementById("flowInput").value = Math.round(o.current.flow_rate);
    } catch (e) { /* optional */ }
    await loadProducts();
    loadOrders();
})();
