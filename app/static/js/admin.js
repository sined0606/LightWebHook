const state = {
    username: null,
    webhooks: [],
    selectedWebhook: null,
    selectedStatus: null,
    events: [],
    activeEventId: null,
};

function getElement(id) {
    return document.getElementById(id);
}

function setBanner(message, isError = false) {
    const banner = getElement("flash-banner");
    if (!message) {
        banner.hidden = true;
        banner.textContent = "";
        banner.classList.remove("error");
        return;
    }

    banner.hidden = false;
    banner.textContent = message;
    banner.classList.toggle("error", isError);
}

function formatDate(value) {
    if (!value) {
        return "Noch nie";
    }

    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return value;
    }

    return new Intl.DateTimeFormat("de-DE", {
        dateStyle: "medium",
        timeStyle: "medium",
    }).format(date);
}

function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (character) => {
        const replacements = {
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#39;",
        };
        return replacements[character] || character;
    });
}

function prettyJson(value) {
    try {
        if (typeof value === "string") {
            return JSON.stringify(JSON.parse(value), null, 2);
        }
        return JSON.stringify(value, null, 2);
    } catch (error) {
        return String(value);
    }
}

async function api(path, options = {}) {
    const response = await fetch(path, {
        credentials: "same-origin",
        headers: {
            Accept: "application/json",
            ...(options.body ? { "Content-Type": "application/json" } : {}),
            ...(options.headers || {}),
        },
        ...options,
    });

    const payload = await response.json().catch(() => ({}));
    if (response.status === 401) {
        window.location.replace("/admin/login");
        throw new Error("Nicht angemeldet.");
    }

    if (!response.ok) {
        throw new Error(payload.detail || "Request fehlgeschlagen.");
    }

    return payload;
}

function renderSummary() {
    const total = state.webhooks.length;
    const triggered = state.webhooks.filter((item) => item.triggered).length;
    const events = state.webhooks.reduce((sum, item) => sum + item.trigger_count, 0);

    getElement("summary-total").textContent = String(total);
    getElement("summary-triggered").textContent = String(triggered);
    getElement("summary-events").textContent = String(events);
}

function renderWebhookList() {
    const list = getElement("webhook-list");
    if (!state.webhooks.length) {
        list.innerHTML = '<div class="empty-state">Keine Webhooks konfiguriert.</div>';
        return;
    }

    list.innerHTML = state.webhooks
        .map((webhook) => {
            const activeClass = webhook.webhook === state.selectedWebhook ? " active" : "";
            const badgeClass = webhook.triggered ? "active" : "idle";
            const badgeText = webhook.triggered ? "Ausgeloest" : "Wartend";
            const description = webhook.description || "Keine Beschreibung";
            return `
                <button class="webhook-button${activeClass}" type="button" data-webhook="${escapeHtml(webhook.webhook)}">
                    <div class="webhook-button-header">
                        <strong>${escapeHtml(webhook.webhook)}</strong>
                        <span class="status-pill ${badgeClass}">${badgeText}</span>
                    </div>
                    <div class="webhook-meta">${escapeHtml(description)}</div>
                    <div class="webhook-meta">Trigger: ${webhook.trigger_count} | Letztes Event: ${escapeHtml(formatDate(webhook.last_triggered_at))}</div>
                </button>
            `;
        })
        .join("");

    list.querySelectorAll("[data-webhook]").forEach((button) => {
        button.addEventListener("click", () => {
            const nextWebhook = button.getAttribute("data-webhook");
            if (!nextWebhook || nextWebhook === state.selectedWebhook) {
                return;
            }

            state.selectedWebhook = nextWebhook;
            state.activeEventId = null;
            renderWebhookList();
            void loadSelectedWebhook();
        });
    });
}

function renderDetails() {
    const selected = state.webhooks.find((item) => item.webhook === state.selectedWebhook);
    const resetButton = getElement("reset-button");

    if (!selected || !state.selectedStatus) {
        getElement("webhook-title").textContent = "Kein Webhook gewaehlt";
        getElement("webhook-description").textContent = "Waehle links einen Webhook aus.";
        getElement("metric-trigger-count").textContent = "0";
        getElement("metric-last-trigger").textContent = "Noch nie";
        getElement("metric-loaded-events").textContent = "0";
        getElement("status-badge").textContent = "Unbekannt";
        getElement("status-badge").className = "status-pill idle";
        resetButton.disabled = true;
        return;
    }

    getElement("webhook-title").textContent = selected.webhook;
    getElement("webhook-description").textContent = selected.description || "Kein Beschreibungstext hinterlegt.";
    getElement("metric-trigger-count").textContent = String(state.selectedStatus.trigger_count);
    getElement("metric-last-trigger").textContent = formatDate(state.selectedStatus.last_triggered_at);
    getElement("metric-loaded-events").textContent = String(state.events.length);
    getElement("status-badge").textContent = state.selectedStatus.triggered ? "Ausgeloest" : "Wartend";
    getElement("status-badge").className = `status-pill ${state.selectedStatus.triggered ? "active" : "idle"}`;
    resetButton.disabled = false;
}

function renderEvents() {
    const eventsList = getElement("events-list");
    if (!state.selectedWebhook) {
        eventsList.className = "events-list empty-state";
        eventsList.textContent = "Waehle einen Webhook, um Events zu laden.";
        return;
    }

    if (!state.events.length) {
        eventsList.className = "events-list empty-state";
        eventsList.textContent = "Fuer diesen Webhook wurden noch keine Events gespeichert.";
        return;
    }

    eventsList.className = "events-list";
    eventsList.innerHTML = state.events
        .map((eventItem) => {
            const activeClass = eventItem.id === state.activeEventId ? " active" : "";
            const contentType = eventItem.content_type || "ohne Content-Type";
            const encodingLabel = eventItem.payload_encoding === "base64" ? "Base64" : "UTF-8";
            return `
                <button class="event-row${activeClass}" type="button" data-event-id="${eventItem.id}">
                    <div class="event-row-header">
                        <strong>#${eventItem.id}</strong>
                        <span>${escapeHtml(formatDate(eventItem.received_at))}</span>
                    </div>
                    <div class="event-subline">${escapeHtml(contentType)}</div>
                    <div class="event-subline">Payload: ${escapeHtml(encodingLabel)}</div>
                </button>
            `;
        })
        .join("");

    eventsList.querySelectorAll("[data-event-id]").forEach((button) => {
        button.addEventListener("click", () => {
            const nextId = Number(button.getAttribute("data-event-id"));
            state.activeEventId = nextId;
            renderEvents();
            renderInspector();
        });
    });
}

function renderInspector() {
    const eventItem = state.events.find((item) => item.id === state.activeEventId);
    if (!eventItem) {
        getElement("event-meta").textContent = "Noch kein Event gewaehlt";
        getElement("payload-viewer").textContent = "Keine Daten geladen.";
        getElement("headers-viewer").textContent = "Keine Daten geladen.";
        return;
    }

    const encodingHint = eventItem.payload_encoding === "base64" ? "Base64" : "UTF-8";
    getElement("event-meta").textContent = `Event #${eventItem.id} | ${formatDate(eventItem.received_at)} | ${encodingHint}`;
    getElement("payload-viewer").textContent = prettyJson(eventItem.payload);
    getElement("headers-viewer").textContent = prettyJson(eventItem.headers);
}

async function ensureSession() {
    const session = await api("/auth/session");
    if (!session.authenticated) {
        window.location.replace("/admin/login");
        return false;
    }

    state.username = session.username || "admin";
    getElement("session-user").textContent = `Angemeldet als ${state.username}`;
    return true;
}

async function loadOverview() {
    const payload = await api("/list");
    state.webhooks = payload.webhooks || [];
    renderSummary();

    if (!state.webhooks.length) {
        state.selectedWebhook = null;
        state.selectedStatus = null;
        state.events = [];
        state.activeEventId = null;
        renderWebhookList();
        renderDetails();
        renderEvents();
        renderInspector();
        return;
    }

    if (!state.selectedWebhook || !state.webhooks.some((item) => item.webhook === state.selectedWebhook)) {
        state.selectedWebhook = state.webhooks[0].webhook;
    }

    renderWebhookList();
}

async function loadSelectedWebhook() {
    if (!state.selectedWebhook) {
        renderDetails();
        renderEvents();
        renderInspector();
        return;
    }

    const limit = Number(getElement("events-limit").value || "50");
    const [statusPayload, eventsPayload] = await Promise.all([
        api(`/status/${encodeURIComponent(state.selectedWebhook)}`),
        api(`/events/${encodeURIComponent(state.selectedWebhook)}?limit=${limit}`),
    ]);

    state.selectedStatus = statusPayload;
    state.events = eventsPayload.events || [];

    if (!state.events.some((item) => item.id === state.activeEventId)) {
        state.activeEventId = state.events[0] ? state.events[0].id : null;
    }

    renderDetails();
    renderEvents();
    renderInspector();
}

async function reloadAll() {
    setBanner("");
    try {
        await loadOverview();
        await loadSelectedWebhook();
    } catch (error) {
        setBanner(error.message, true);
    }
}

async function handleLogout() {
    try {
        await api("/auth/logout", { method: "POST" });
    } finally {
        window.location.replace("/admin/login");
    }
}

async function handleReset() {
    if (!state.selectedWebhook) {
        return;
    }

    const confirmed = window.confirm(`Webhook "${state.selectedWebhook}" wirklich zuruecksetzen?`);
    if (!confirmed) {
        return;
    }

    try {
        const result = await api(`/reset/${encodeURIComponent(state.selectedWebhook)}`, { method: "POST" });
        setBanner(`${result.deleted_events} Event(s) fuer ${state.selectedWebhook} geloescht.`);
        await reloadAll();
    } catch (error) {
        setBanner(error.message, true);
    }
}

window.addEventListener("DOMContentLoaded", async () => {
    getElement("refresh-button").addEventListener("click", () => {
        void reloadAll();
    });

    getElement("logout-button").addEventListener("click", () => {
        void handleLogout();
    });

    getElement("reset-button").addEventListener("click", () => {
        void handleReset();
    });

    getElement("events-limit").addEventListener("change", () => {
        void loadSelectedWebhook().catch((error) => setBanner(error.message, true));
    });

    try {
        const authenticated = await ensureSession();
        if (!authenticated) {
            return;
        }

        await reloadAll();
    } catch (error) {
        setBanner(error.message, true);
    }
});
