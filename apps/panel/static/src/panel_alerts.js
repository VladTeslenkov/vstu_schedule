(function () {
  const alertsRoot = document.querySelector("[data-panel-alerts]");
  if (!alertsRoot) return;

  function csrfToken() {
    const input = alertsRoot.querySelector("input[name=csrfmiddlewaretoken]");
    return input ? input.value : "";
  }

  function dismissedStorageKey(alertId) {
    return `panel.dismissedAlert.${alertId}`;
  }

  function isLocallyDismissed(alertId) {
    try {
      return localStorage.getItem(dismissedStorageKey(alertId)) === "1";
    } catch (error) {
      return false;
    }
  }

  function rememberLocalDismiss(alertId) {
    try {
      localStorage.setItem(dismissedStorageKey(alertId), "1");
    } catch (error) {
      // Browser storage may be unavailable in private mode.
    }
  }

  function attachAlertHandler(form) {
    if (form.dataset.panelAlertBound === "1") return;
    form.dataset.panelAlertBound = "1";

    form.addEventListener("submit", (event) => {
      event.preventDefault();
      if (form.dataset.panelAlertDismissible !== "1") {
        rememberLocalDismiss(form.dataset.panelAlertId);
        form.remove();
        return;
      }

      fetch(form.action, {
        method: "POST",
        headers: { "X-CSRFToken": csrfToken() },
      })
        .then((response) => {
          if (!response.ok) throw new Error("Alert dismiss failed");
          form.remove();
        })
        .catch(() => {
          form.submit();
        });
    });
  }

  function createAlertForm(alert) {
    const form = document.createElement("form");
    form.className = `panel-flash panel-flash--${alert.category}`;
    form.method = "post";
    form.action = alert.dismiss_url;
    form.dataset.panelAlertId = String(alert.id);
    form.dataset.panelAlertDismissible = alert.is_dismissible ? "1" : "0";
    form.dataset.panelAlert = "";

    const icon = document.createElement("i");
    icon.className = "icon";
    icon.dataset.lucide = alert.icon_name;

    const text = document.createElement("div");
    text.className = "panel-flash__text";

    const title = document.createElement("strong");
    title.textContent = alert.title;
    const body = document.createElement("span");
    body.textContent = alert.body;

    const closeButton = document.createElement("button");
    closeButton.className = "panel-flash__close";
    closeButton.type = "submit";
    closeButton.setAttribute("aria-label", "Close alert");

    const closeIcon = document.createElement("i");
    closeIcon.className = "icon";
    closeIcon.dataset.lucide = "x";

    const csrf = document.createElement("input");
    csrf.type = "hidden";
    csrf.name = "csrfmiddlewaretoken";
    csrf.value = csrfToken();

    form.appendChild(csrf);
    text.appendChild(title);
    text.appendChild(body);
    closeButton.appendChild(closeIcon);
    form.appendChild(icon);
    form.appendChild(text);
    form.appendChild(closeButton);
    attachAlertHandler(form);
    return form;
  }

  function syncAlerts(alerts) {
    const seen = {};
    alerts.forEach((alert) => {
      const alertId = String(alert.id);
      seen[alertId] = true;
      if (isLocallyDismissed(alertId)) return;
      if (alertsRoot.querySelector(`[data-panel-alert-id="${alertId}"]`)) return;
      alertsRoot.appendChild(createAlertForm(alert));
    });

    alertsRoot.querySelectorAll("[data-panel-alert]").forEach((form) => {
      if (!seen[form.dataset.panelAlertId]) {
        form.remove();
      }
    });

    if (window.lucide) {
      lucide.createIcons();
    }
  }

  function refreshAlerts() {
    fetch(alertsRoot.dataset.panelAlertsUrl, {
      headers: { "X-Requested-With": "XMLHttpRequest" },
    })
      .then((response) => {
        if (!response.ok) throw new Error("Alert feed failed");
        return response.json();
      })
      .then((payload) => {
        syncAlerts(payload.alerts || []);
      })
      .catch(() => {
        // Keep the existing alerts visible; the next poll may recover.
      });
  }

  document.querySelectorAll("[data-panel-alert]").forEach((form) => {
    const alertId = form.dataset.panelAlertId;
    if (isLocallyDismissed(alertId)) {
      form.remove();
      return;
    }
    attachAlertHandler(form);
  });

  window.setInterval(refreshAlerts, 10000);
})();
