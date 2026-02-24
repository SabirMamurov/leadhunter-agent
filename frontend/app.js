const API_URL = "";

// ─────────────────────────────────────────────────────────
// STATE
// ─────────────────────────────────────────────────────────
let currentUser = null;
let companiesData = [];
let currentFilter = null;   // null = all, or status string
let currentModalTab = 'letter';

// ─────────────────────────────────────────────────────────
// UTILS
// ─────────────────────────────────────────────────────────
function showLoader(text = "Загрузка...") {
    document.getElementById("loaderText").innerText = text;
    document.getElementById("loader").style.display = "flex";
}

function hideLoader() {
    document.getElementById("loader").style.display = "none";
}

let toastTimer;
function showToast(msg) {
    const el = document.getElementById("toast");
    el.innerText = msg;
    el.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.remove("show"), 3500);
}

function authHeaders() {
    const token = localStorage.getItem("keitering_token");
    return { "Content-Type": "application/json", "Authorization": `Bearer ${token}` };
}

function fmt(isoStr) {
    if (!isoStr) return "";
    const d = new Date(isoStr);
    return d.toLocaleString("ru-RU", { day: "2-digit", month: "2-digit", year: "2-digit", hour: "2-digit", minute: "2-digit" });
}

// ─────────────────────────────────────────────────────────
// AUTH
// ─────────────────────────────────────────────────────────
const statusLabels = {
    new: "Новые",
    email_sent: "Письмо отправлено",
    replied: "Ответили",
    in_progress: "В работе",
    interested: "Заинтересованы",
    rejected: "Отказ",
    closed: "Закрыто",
};

document.addEventListener("DOMContentLoaded", () => {
    const token = localStorage.getItem("keitering_token");
    if (token) {
        // Проверяем токен
        fetch(`${API_URL}/auth/me`, { headers: authHeaders() })
            .then(r => r.json())
            .then(u => {
                if (u.id) { loginSuccess(u); }
                else { showAuth(); }
            })
            .catch(() => showAuth());
    } else {
        showAuth();
    }
});

function showAuth() {
    document.getElementById("authScreen").style.display = "flex";
    document.getElementById("appScreen").style.display = "none";
}

function showApp() {
    document.getElementById("authScreen").style.display = "none";
    document.getElementById("appScreen").style.display = "flex";
}

function loginSuccess(user) {
    currentUser = user;
    showApp();
    // Заполняем сайдбар
    document.getElementById("sidebarName").innerText = user.name;
    document.getElementById("sidebarSendEmail").innerText = user.send_email;
    document.getElementById("sidebarAvatar").innerText = user.name.charAt(0).toUpperCase();
    loadCompanies();
}

function switchAuthTab(tab) {
    document.getElementById("loginForm").classList.toggle("hidden", tab !== "login");
    document.getElementById("registerForm").classList.toggle("hidden", tab !== "register");
    document.getElementById("tabLogin").classList.toggle("active", tab === "login");
    document.getElementById("tabRegister").classList.toggle("active", tab === "register");
    document.getElementById("authError").style.display = "none";
}

function showAuthError(msg) {
    const el = document.getElementById("authError");
    el.innerText = msg;
    el.style.display = "block";
}

async function doLogin() {
    const email = document.getElementById("loginEmail").value.trim();
    const password = document.getElementById("loginPassword").value;
    if (!email || !password) return showAuthError("Заполните все поля");
    const btn = document.getElementById("loginBtn");
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span>';
    try {
        const r = await fetch(`${API_URL}/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password }),
        });
        const d = await r.json();
        if (!r.ok) return showAuthError(d.detail || "Ошибка входа");
        localStorage.setItem("keitering_token", d.token);
        loginSuccess(d.user);
    } catch (e) {
        showAuthError("Ошибка подключения к серверу");
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-box-arrow-in-right"></i> Войти';
    }
}

async function doRegister() {
    const name = document.getElementById("regName").value.trim();
    const email = document.getElementById("regEmail").value.trim();
    const send_email = document.getElementById("regSendEmail").value.trim();
    const password = document.getElementById("regPassword").value;
    if (!name || !email || !send_email || !password) return showAuthError("Заполните все поля");
    if (password.length < 6) return showAuthError("Пароль должен быть не менее 6 символов");
    const btn = document.getElementById("registerBtn");
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span>';
    try {
        const r = await fetch(`${API_URL}/auth/register`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name, email, send_email, password }),
        });
        const d = await r.json();
        if (!r.ok) return showAuthError(d.detail || "Ошибка регистрации");
        localStorage.setItem("keitering_token", d.token);
        loginSuccess(d.user);
    } catch (e) {
        showAuthError("Ошибка подключения к серверу");
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-person-plus"></i> Создать аккаунт';
    }
}

function doLogout() {
    localStorage.removeItem("keitering_token");
    currentUser = null;
    companiesData = [];
    showAuth();
}

// ─────────────────────────────────────────────────────────
// COMPANIES
// ─────────────────────────────────────────────────────────
async function loadCompanies() {
    try {
        const r = await fetch(`${API_URL}/companies`, { headers: authHeaders() });
        companiesData = await r.json();
        updateSidebarCounts();
        renderCards();
    } catch (e) {
        console.error("loadCompanies error", e);
        showToast("Ошибка загрузки данных");
    }
}

function setStatusFilter(status) {
    currentFilter = status;
    // Highlight nav item
    document.querySelectorAll(".status-nav-item").forEach(el => el.classList.remove("active"));
    const navKey = status ? `nav-${status}` : "nav-all";
    document.getElementById(navKey)?.classList.add("active");
    // Update topbar title
    document.getElementById("topbarTitle").innerText = status ? statusLabels[status] : "Все диалоги";
    renderCards();
}

function updateSidebarCounts() {
    const counts = {};
    companiesData.forEach(c => { counts[c.status] = (counts[c.status] || 0) + 1; });
    document.getElementById("cnt-all").innerText = companiesData.length;
    ["new", "email_sent", "replied", "in_progress", "interested", "rejected", "closed"].forEach(s => {
        document.getElementById(`cnt-${s}`).innerText = counts[s] || 0;
    });
}

const badgeIcons = {
    new: "bi-circle",
    email_sent: "bi-send",
    replied: "bi-reply",
    in_progress: "bi-clock-history",
    interested: "bi-star-fill",
    rejected: "bi-x-circle",
    closed: "bi-archive",
};

function renderCards() {
    const grid = document.getElementById("cardsGrid");
    const empty = document.getElementById("emptyState");
    const list = currentFilter
        ? companiesData.filter(c => c.status === currentFilter)
        : companiesData;

    grid.innerHTML = "";
    if (list.length === 0) {
        empty.classList.remove("hidden");
        return;
    }
    empty.classList.add("hidden");

    list.forEach((c, idx) => {
        const card = document.createElement("div");
        card.className = "company-card";
        card.onclick = () => openCompany(c.id);
        card.innerHTML = `
            <div class="card-num">#${idx + 1}</div>
            <div class="card-name">${c.name}</div>
            <div class="card-category">${c.category}</div>
            <div class="card-meta">
                ${c.email ? `<span><i class="bi bi-envelope"></i>${c.email}</span>` : ""}
                ${c.phone ? `<span><i class="bi bi-telephone"></i>${c.phone}</span>` : ""}
                ${c.website ? `<span><i class="bi bi-globe"></i>${c.website}</span>` : ""}
            </div>
            ${c.description ? `<div class="card-desc">${c.description}</div>` : ""}
            <div class="card-footer">
                <span class="badge badge-${c.status}">
                    <i class="bi ${badgeIcons[c.status]}"></i>
                    ${statusLabels[c.status]}
                </span>
                ${c.messages_count > 0
                ? `<span class="chat-bubble-icon"><i class="bi bi-chat-dots"></i>${c.messages_count}</span>`
                : ""}
            </div>
        `;
        grid.appendChild(card);
    });
}

// ─────────────────────────────────────────────────────────
// SEARCH
// ─────────────────────────────────────────────────────────
async function searchCompanies() {
    const query = document.getElementById("categoryInput").value.trim();
    if (!query) return showToast("Введите категорию для поиска");
    showLoader(`Ищем «${query}» через AI...`);
    try {
        const r = await fetch(`${API_URL}/search`, {
            method: "POST",
            headers: authHeaders(),
            body: JSON.stringify({ category: query }),
        });
        const d = await r.json();
        if (!r.ok) throw new Error(d.detail);
        showToast(d.message);
        await loadCompanies();
    } catch (e) {
        showToast("Ошибка поиска: " + e.message);
    } finally {
        hideLoader();
    }
}

async function sendToAllNew() {
    if (!confirm("Сгенерировать и отправить письма ВСЕМ новым компаниям?")) return;
    showLoader("Массовая генерация и отправка писем...");
    try {
        const r = await fetch(`${API_URL}/send-all`, { method: "POST", headers: authHeaders() });
        const d = await r.json();
        if (!r.ok) throw new Error(d.detail);
        showToast(d.message);
        await loadCompanies();
    } catch (e) {
        showToast("Ошибка рассылки: " + e.message);
    } finally {
        hideLoader();
    }
}

// ─────────────────────────────────────────────────────────
// MODAL
// ─────────────────────────────────────────────────────────
function openModal(id) { document.getElementById(id).classList.add("open"); }
function closeModal(id) { document.getElementById(id).classList.remove("open"); }

// Close on overlay click
document.getElementById("companyModal").addEventListener("click", function (e) {
    if (e.target === this) closeModal("companyModal");
});

function switchModalTab(tab) {
    currentModalTab = tab;
    document.querySelectorAll(".tab-btn").forEach((b, i) => {
        const names = ["letter", "chat"];
        b.classList.toggle("active", names[i] === tab);
    });
    document.getElementById("tabLetter").classList.toggle("active", tab === "letter");
    document.getElementById("tabChat").classList.toggle("active", tab === "chat");
}

function openCompany(id) {
    id = parseInt(id);
    const comp = companiesData.find(c => c.id === id);
    if (!comp) return;

    document.getElementById("modalCompanyId").value = id;
    document.getElementById("mCompanyName").innerText = comp.name;
    document.getElementById("mCompanyCategory").innerText = comp.category;
    document.getElementById("mEmail").innerText = comp.email || "—";
    document.getElementById("mPhone").innerText = comp.phone || "—";
    document.getElementById("mWeb").innerText = comp.website || "—";
    document.getElementById("mStatusSelect").value = comp.status;

    // Letter tab
    if (comp.email_body) {
        document.getElementById("letterPreview").classList.remove("hidden");
        document.getElementById("noLetterArea").classList.add("hidden");
        document.getElementById("mEmailSubject").innerText = comp.email_subject || "";
        document.getElementById("mEmailBody").innerText = comp.email_body;
        document.getElementById("btnGenerate").classList.add("hidden");
        if (comp.status === "new") {
            document.getElementById("btnSend").classList.remove("hidden");
        } else {
            document.getElementById("btnSend").classList.add("hidden");
        }
    } else {
        document.getElementById("letterPreview").classList.add("hidden");
        document.getElementById("noLetterArea").classList.remove("hidden");
        document.getElementById("btnGenerate").classList.remove("hidden");
        document.getElementById("btnSend").classList.add("hidden");
    }

    // Switch to letter tab by default
    switchModalTab("letter");

    // Load chat
    loadChat(id);

    openModal("companyModal");
}

// ─────────────────────────────────────────────────────────
// LETTER ACTIONS
// ─────────────────────────────────────────────────────────
async function generateAndPreview() {
    const id = parseInt(document.getElementById("modalCompanyId").value);
    const btn = document.getElementById("btnGenerate");
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Генерируем...';
    try {
        const r = await fetch(`${API_URL}/generate-email/${id}`, { method: "POST", headers: authHeaders() });
        if (!r.ok) { const e = await r.json(); throw new Error(e.detail || `HTTP ${r.status}`); }
        const d = await r.json();
        const comp = companiesData.find(c => c.id === id);
        if (comp) { comp.email_subject = d.subject; comp.email_body = d.body; }
        openCompany(id);
    } catch (e) {
        showToast("Ошибка генерации: " + e.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-magic"></i> Сгенерировать AI письмо';
    }
}

async function sendEmail() {
    const id = parseInt(document.getElementById("modalCompanyId").value);
    const btn = document.getElementById("btnSend");
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner" style="border-color:rgba(58,125,82,.3);border-top-color:#3a7d52;"></span> Отправка...';
    try {
        const r = await fetch(`${API_URL}/send-email/${id}`, { method: "POST", headers: authHeaders() });
        if (!r.ok) { const e = await r.json(); throw new Error(e.detail || `HTTP ${r.status}`); }
        const d = await r.json();
        showToast(d.message);
        await loadCompanies();
        openCompany(id);          // перерисовка с новым статусом
        switchModalTab("chat");   // переключаем на чат, там уже будет первое письмо
    } catch (e) {
        showToast("Ошибка отправки: " + e.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-send"></i> Отправить письмо';
    }
}

async function updateStatus() {
    const id = parseInt(document.getElementById("modalCompanyId").value);
    const status = document.getElementById("mStatusSelect").value;
    try {
        const r = await fetch(`${API_URL}/company/${id}/status`, {
            method: "PUT",
            headers: authHeaders(),
            body: JSON.stringify({ status }),
        });
        if (!r.ok) { const e = await r.json(); throw new Error(e.detail); }
        const comp = companiesData.find(c => c.id === id);
        if (comp) comp.status = status;
        updateSidebarCounts();
        renderCards();
        showToast("Статус обновлён");
    } catch (e) {
        showToast("Ошибка: " + e.message);
    }
}

// ─────────────────────────────────────────────────────────
// CHAT
// ─────────────────────────────────────────────────────────
async function loadChat(companyId) {
    try {
        const r = await fetch(`${API_URL}/company/${companyId}/messages`, { headers: authHeaders() });
        if (!r.ok) return;
        const msgs = await r.json();
        renderChat(msgs);
    } catch (e) {
        console.error("loadChat error", e);
    }
}

function renderChat(messages) {
    const container = document.getElementById("chatContainer");
    const empty = document.getElementById("chatEmpty");
    container.innerHTML = "";

    if (messages.length === 0) {
        container.appendChild(empty);
        empty.classList.remove("hidden");
        return;
    }

    messages.forEach(m => {
        const wrap = document.createElement("div");
        wrap.className = `chat-msg ${m.direction}`;
        wrap.innerHTML = `
            <div class="chat-bubble">${escapeHtml(m.text)}</div>
            <div class="chat-meta">${m.author} · ${fmt(m.created_at)}</div>
        `;
        container.appendChild(wrap);
    });

    // scroll to bottom
    container.scrollTop = container.scrollHeight;
}

function escapeHtml(text) {
    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/\n/g, "<br>");
}

async function sendChatMessage() {
    const id = parseInt(document.getElementById("modalCompanyId").value);
    const textarea = document.getElementById("chatInput");
    const text = textarea.value.trim();
    if (!text) return;

    textarea.value = "";
    try {
        const r = await fetch(`${API_URL}/company/${id}/messages`, {
            method: "POST",
            headers: authHeaders(),
            body: JSON.stringify({ text, direction: "outgoing" }),
        });
        if (!r.ok) { const e = await r.json(); throw new Error(e.detail); }
        // reload chat and companies (message count changed)
        await loadChat(id);
        await loadCompanies();
    } catch (e) {
        showToast("Ошибка отправки: " + e.message);
        textarea.value = text;
    }
}

function chatKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendChatMessage();
    }
}

async function simulateReply() {
    const id = parseInt(document.getElementById("modalCompanyId").value);
    try {
        const r = await fetch(`${API_URL}/simulate-reply/${id}`, { method: "POST", headers: authHeaders() });
        if (!r.ok) { const e = await r.json(); throw new Error(e.detail); }
        const d = await r.json();
        showToast(d.message);
        await loadCompanies();
        await loadChat(id);
        openCompany(id);
        switchModalTab("chat");
    } catch (e) {
        showToast("Ошибка: " + e.message);
    }
}
