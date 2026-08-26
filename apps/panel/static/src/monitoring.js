"use strict";

/* ===== КОНСТАНТЫ ===== */
const CSRF = getCsrf();
/** Базовый префикс API обновления расписания (см. apps.panel.urls) */
const TIMETABLE_UPDATE_API = "/panel/timetable_update/";
const POLL_INTERVAL_MS = 2000;
const AUTO_REFRESH_MS = 30_000;

/* ===== СОСТОЯНИЕ ===== */
let allResources = [];
let currentFilter = "all";
let pollTimer = null;

/* ===== INIT ===== */
document.addEventListener("DOMContentLoaded", () => {
  loadData();
  setInterval(loadData, AUTO_REFRESH_MS);
  initSettingsForm();
  resumePendingTask();
  initConfirmModal();
});

/* ===== МОДАЛЬНОЕ ОКНО ПОДТВЕРЖДЕНИЯ ===== */
function initConfirmModal() {
  const modal = document.getElementById("confirmModal");
  if (!modal) return;

  modal.addEventListener("click", (event) => {
    if (event.target === modal) closeConfirmModal();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !modal.hidden) closeConfirmModal();
  });
}

/* ===== ВОССТАНОВЛЕНИЕ ЗАДАЧИ ПОСЛЕ ПЕРЕЗАГРУЗКИ ===== */
function resumePendingTask() {
  const taskId = sessionStorage.getItem("pendingTaskId");
  const taskType =
    sessionStorage.getItem("pendingTaskType") || "update_timetable";
  if (!taskId) return;

  const statusElemId =
    taskType === "update_timetable" ? "taskStatus" : "clearStatus";
  showStatus(statusElemId, "running", "⏳ Операция выполняется...");

  if (taskType === "update_timetable") {
    document.getElementById("runTaskBtn").disabled = true;
  }

  pollTask(
    taskId,
    taskType,
    statusElemId,
    () => {
      sessionStorage.removeItem("pendingTaskId");
      sessionStorage.removeItem("pendingTaskType");
      if (taskType === "update_timetable") {
        document.getElementById("runTaskBtn").disabled = false;
      }
      loadData();
    },
    () => {
      sessionStorage.removeItem("pendingTaskId");
      sessionStorage.removeItem("pendingTaskType");
      if (taskType === "update_timetable") {
        document.getElementById("runTaskBtn").disabled = false;
      }
    },
  );
}

/* ===== ЗАГРУЗКА ДАННЫХ ===== */
async function loadData() {
  try {
    const res = await fetch(`${TIMETABLE_UPDATE_API}stats/`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    renderStats(data.stats);
    renderScheduler(data.scheduler, data.stats.last_update_time);
    allResources = data.resources;
    renderResources(allResources, currentFilter);
    renderVersions(data.recent_versions);

    document.getElementById("lastRefresh").textContent =
      "Обновлено: " + new Date().toLocaleTimeString("ru-RU");
  } catch (e) {
    console.error("Ошибка загрузки данных мониторинга:", e);
  }
}

/* ===== СТАТИСТИКА ===== */
function renderStats(stats) {
  setText("statActive", stats.active_resources ?? "—");
  setText("statTotal", stats.total_resources ?? "—");
  setText("statDeprecated", stats.deprecated_resources ?? "—");
  setText("statVersions", stats.total_versions ?? "—");
}

/* ===== ПЛАНИРОВЩИК ===== */
function renderScheduler(sch, lastUpdateTime) {
  const badge = document.getElementById("schedulerBadge");

  if (!sch || !sch.configured) {
    badge.textContent = "Не настроен";
    badge.className = "badge badge--muted";
    setText("schInterval", "—");
    setText("schLastRun", "—");
    setText("schRunCount", "—");
    setText(
      "schLastUpdate",
      lastUpdateTime ? fmtDatetime(lastUpdateTime) : "—",
    );
    return;
  }

  badge.textContent = sch.enabled ? "Активен" : "Отключён";
  badge.className = sch.enabled ? "badge badge--success" : "badge badge--warn";

  setText("schInterval", sch.interval ?? "—");
  setText(
    "schLastRun",
    sch.last_run_at ? fmtDatetime(sch.last_run_at) : "Ещё не запускался",
  );
  setText("schRunCount", sch.total_run_count ?? 0);
  setText("schLastUpdate", lastUpdateTime ? fmtDatetime(lastUpdateTime) : "—");
}

/* ===== РЕСУРСЫ ===== */
function filterResources(filter, btn) {
  currentFilter = filter;
  document
    .querySelectorAll(".filter-tab")
    .forEach((b) => b.classList.remove("active"));
  btn.classList.add("active");
  renderResources(allResources, filter);
}

function renderResources(resources, filter) {
  const tbody = document.getElementById("resourcesBody");
  let list = resources;
  if (filter === "active") list = resources.filter((r) => !r.deprecated);
  if (filter === "deprecated") list = resources.filter((r) => r.deprecated);

  if (!list.length) {
    tbody.innerHTML = `<tr><td colspan="5" class="empty-row">Нет данных</td></tr>`;
    return;
  }

  tbody.innerHTML = list
    .map(
      (r) => `
    <tr>
      <td title="${esc(r.name)}">${esc(r.name)}</td>
      <td title="${esc(r.path || "")}" class="hash">${esc(r.path || "—")}</td>
      <td>${r.last_update ? fmtDatetime(r.last_update) : "—"}</td>
      <td>${
        r.deprecated
          ? '<span class="pill pill--deprecated">Устарел</span>'
          : '<span class="pill pill--active">Актуален</span>'
      }</td>
      <td>
        ${
          r.has_file
            ? `<button class="btn btn--ghost btn--sm" onclick="downloadResource(${r.id})">Скачать</button>`
            : '<span style="font-size:11px;opacity:0.4">нет файла</span>'
        }
      </td>
    </tr>`,
    )
    .join("");
}

/* ===== ИСТОРИЯ ВЕРСИЙ ===== */
function renderVersions(versions) {
  const tbody = document.getElementById("versionsBody");
  if (!versions.length) {
    tbody.innerHTML = `<tr><td colspan="4" class="empty-row">Нет данных</td></tr>`;
    return;
  }
  tbody.innerHTML = versions
    .map(
      (v) => `
    <tr>
      <td title="${esc(v.resource__name || "")}">${esc(v.resource__name || "—")}</td>
      <td>${v.timestamp ? fmtDatetime(v.timestamp) : "—"}</td>
      <td class="hash">${esc(v.hashsum_hex || v.hashsum || "—")}</td>
      <td class="hash">${esc(v.mimetype || "—")}</td>
    </tr>`,
    )
    .join("");
}

/* ===== ЗАПУСК ОБНОВЛЕНИЯ ===== */
async function runUpdate() {
  const btn = document.getElementById("runTaskBtn");
  btn.disabled = true;
  showStatus("taskStatus", "running", "Запускаем задачу обновления...");

  try {
    const res = await fetch(`${TIMETABLE_UPDATE_API}update_timetable/`, {
      method: "POST",
      headers: { "X-CSRFToken": CSRF },
      body: new FormData(),
    });
    const data = await res.json();
    const taskId = data.id || data.task_id;

    if (!taskId) {
      showStatus(
        "taskStatus",
        "error",
        "Ошибка запуска: " + (data.error_message || "нет task_id"),
      );
      btn.disabled = false;
      return;
    }

    sessionStorage.setItem("pendingTaskId", taskId);
    sessionStorage.setItem("pendingTaskType", "update_timetable");

    showStatus(
      "taskStatus",
      "running",
      "Задача запущена, ожидаем результат...",
    );
    pollTask(
      taskId,
      "update_timetable",
      "taskStatus",
      () => {
        sessionStorage.removeItem("pendingTaskId");
        sessionStorage.removeItem("pendingTaskType");
        btn.disabled = false;
        loadData();
      },
      () => {
        sessionStorage.removeItem("pendingTaskId");
        sessionStorage.removeItem("pendingTaskType");
        btn.disabled = false;
      },
    );
  } catch (e) {
    showStatus("taskStatus", "error", "Ошибка сети: " + e.message);
    sessionStorage.removeItem("pendingTaskId");
    sessionStorage.removeItem("pendingTaskType");
    btn.disabled = false;
  }
}

/* ===== НАСТРОЙКИ ===== */
function initSettingsForm() {
  const initialFreq = window.MONITOR_CTX?.timeUpdate || "";
  const initialUrl = window.MONITOR_CTX?.analyzeUrl || "";

  const freqEl = document.getElementById("scanFrequency");
  const urlEl = document.getElementById("rootUrl");
  const btn = document.getElementById("applySettingsBtn");

  function checkChanged() {
    const changed = freqEl.value !== initialFreq || urlEl.value !== initialUrl;
    btn.disabled = !changed;
  }

  freqEl.addEventListener("change", checkChanged);
  urlEl.addEventListener("input", checkChanged);
}

async function applySettings() {
  const btn = document.getElementById("applySettingsBtn");
  btn.disabled = true;
  showStatus("settingsStatus", "running", "Сохраняем настройки...");

  try {
    const formData = new FormData();
    formData.append(
      "scanFrequency",
      document.getElementById("scanFrequency").value,
    );
    formData.append("rootUrl", document.getElementById("rootUrl").value);

    const res = await fetch(`${TIMETABLE_UPDATE_API}settings/`, {
      method: "POST",
      headers: { "X-CSRFToken": CSRF },
      body: formData,
    });
    const data = await res.json();

    if (data.status === "success") {
      showStatus("settingsStatus", "success", "Настройки сохранены");
      window.MONITOR_CTX.timeUpdate =
        document.getElementById("scanFrequency").value;
      window.MONITOR_CTX.analyzeUrl = document.getElementById("rootUrl").value;
      loadData();
    } else {
      showStatus(
        "settingsStatus",
        "error",
        "Ошибка: " + (data.error_message || "неизвестная ошибка"),
      );
      btn.disabled = false;
    }
  } catch (e) {
    showStatus("settingsStatus", "error", "Ошибка сети: " + e.message);
    btn.disabled = false;
  }
}

/* ===== ОЧИСТКА ===== */
function runClear() {
  const component = document.querySelector(
    'input[name="clearTarget"]:checked',
  )?.value;
  if (!component) return;

  openConfirmModal(
    `Вы уверены? Будет очищено: "${component}". Это действие необратимо.`,
    () => executeClear(component),
  );
}

let confirmModalHandler = null;

function openConfirmModal(text, onConfirm) {
  const modal = document.getElementById("confirmModal");
  const textEl = document.getElementById("confirmModalText");
  const confirmBtn = document.getElementById("confirmModalConfirmBtn");
  textEl.textContent = text;
  modal.hidden = false;

  if (confirmModalHandler) {
    confirmBtn.removeEventListener("click", confirmModalHandler);
  }
  confirmModalHandler = () => {
    closeConfirmModal();
    onConfirm();
  };
  confirmBtn.addEventListener("click", confirmModalHandler, { once: true });
}

function closeConfirmModal() {
  document.getElementById("confirmModal").hidden = true;
}

async function executeClear(component) {
  showStatus("clearStatus", "running", `Очищаем: ${component}...`);

  try {
    const formData = new FormData();
    formData.append("action", "dell");
    formData.append("component", component);

    const res = await fetch(`${TIMETABLE_UPDATE_API}manage_storage/`, {
      method: "POST",
      headers: { "X-CSRFToken": CSRF },
      body: formData,
    });
    const data = await res.json();
    const taskId = data.id || data.task_id;

    if (!taskId) {
      showStatus("clearStatus", "error", "Ошибка запуска очистки");
      return;
    }

    sessionStorage.setItem("pendingTaskId", taskId);
    sessionStorage.setItem("pendingTaskType", "manage_storage");

    pollTask(
      taskId,
      "manage_storage",
      "clearStatus",
      () => {
        sessionStorage.removeItem("pendingTaskId");
        sessionStorage.removeItem("pendingTaskType");
        loadData();
      },
      () => {
        sessionStorage.removeItem("pendingTaskId");
        sessionStorage.removeItem("pendingTaskType");
      },
    );
  } catch (e) {
    showStatus("clearStatus", "error", "Ошибка сети: " + e.message);
  }
}

/* ===== СКАЧИВАНИЕ ФАЙЛА ===== */
function downloadResource(resourceId) {
  window.location.href = `${TIMETABLE_UPDATE_API}download/${resourceId}/`;
}

/* ===== POLLING ===== */
function pollTask(taskId, endpoint, statusElemId, onSuccess, onError) {
  if (pollTimer) clearInterval(pollTimer);

  pollTimer = setInterval(async () => {
    try {
      const res = await fetch(
        `${TIMETABLE_UPDATE_API}${endpoint}/?task_id=${taskId}`,
      );
      const data = await res.json();

      if (data.status === "running") return;

      clearInterval(pollTimer);
      pollTimer = null;

      if (data.status === "success") {
        showStatus(statusElemId, "success", "Операция выполнена успешно");
        onSuccess();
      } else {
        showStatus(
          statusElemId,
          "error",
          "Ошибка: " + (data.error_message || "неизвестная ошибка"),
        );
        onError();
      }
    } catch (e) {
      clearInterval(pollTimer);
      pollTimer = null;
      showStatus(statusElemId, "error", "Ошибка опроса статуса: " + e.message);
      onError();
    }
  }, POLL_INTERVAL_MS);
}

/* ===== ВСПОМОГАТЕЛЬНЫЕ ===== */
function showStatus(elemId, type, msg) {
  const el = document.getElementById(elemId);
  if (!el) return;
  el.style.display = "block";
  el.className = "task-status task-status--" + type;
  el.textContent = msg;
}

function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

function esc(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function fmtDatetime(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("ru-RU", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function getCsrf() {
  for (const c of document.cookie.split(";")) {
    const [k, v] = c.trim().split("=");
    if (k === "csrftoken") return decodeURIComponent(v);
  }
  return "";
}
