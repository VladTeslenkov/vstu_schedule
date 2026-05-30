(function () {
  const filtersStorageKey = "schedule.filters";
  let autocompleteId = 0;

  function getOptionText(option) {
    return option.textContent.trim();
  }

  function getSelectedOptions(select) {
    return Array.from(select.options).filter((option) => option.selected);
  }

  function getScheduleMessages() {
    const form = document.getElementById("schedule-filter-form");
    return {
      autocompletePlaceholder: form?.dataset.autocompletePlaceholder || "",
      autocompleteEmpty: form?.dataset.autocompleteEmpty || "",
      removeLabelTemplate: form?.dataset.removeLabelTemplate || "__value__",
      moreFiltersLabel: form?.dataset.moreFiltersLabel || "",
      lessFiltersLabel: form?.dataset.lessFiltersLabel || "",
    };
  }

  function formatMessage(template, values) {
    return Object.entries(values).reduce(
      (message, [key, value]) => message.replace(`__${key}__`, value),
      template,
    );
  }

  function createAutocompleteSelect(select) {
    if (!select.multiple || select.dataset.autocompleteReady === "1") return;
    const messages = getScheduleMessages();
    autocompleteId += 1;
    const listboxId = `autocomplete-options-${autocompleteId}`;
    select.dataset.autocompleteReady = "1";
    select.classList.add("native-select-hidden");
    select.setAttribute("aria-hidden", "true");
    select.tabIndex = -1;

    const wrapper = document.createElement("div");
    wrapper.className = "autocomplete-select";

    const tags = document.createElement("div");
    tags.className = "autocomplete-tags";

    const input = document.createElement("input");
    input.className = "autocomplete-input";
    input.type = "text";
    input.autocomplete = "off";
    input.placeholder = messages.autocompletePlaceholder;
    input.setAttribute("role", "combobox");
    input.setAttribute("aria-autocomplete", "list");
    input.setAttribute("aria-expanded", "false");
    input.setAttribute("aria-controls", listboxId);
    input.setAttribute("aria-haspopup", "listbox");

    const optionsList = document.createElement("div");
    optionsList.className = "autocomplete-options is-hidden";
    optionsList.id = listboxId;
    optionsList.setAttribute("role", "listbox");
    optionsList.setAttribute("aria-multiselectable", "true");
    optionsList.hidden = true;

    wrapper.append(tags, input, optionsList);
    select.after(wrapper);
    let activeOptionIndex = -1;

    function hideOptions() {
      optionsList.classList.add("is-hidden");
      optionsList.hidden = true;
      input.setAttribute("aria-expanded", "false");
      input.removeAttribute("aria-activedescendant");
      activeOptionIndex = -1;
    }

    function showOptions() {
      renderOptions();
      optionsList.classList.remove("is-hidden");
      optionsList.hidden = false;
      input.setAttribute("aria-expanded", "true");
    }

    function updateSelect() {
      select.dispatchEvent(new Event("change", { bubbles: true }));
    }

    function updatePlaceholder() {
      const hasSelection = getSelectedOptions(select).length > 0;
      input.placeholder = hasSelection ? "" : messages.autocompletePlaceholder;
    }

    function renderTags() {
      tags.replaceChildren();
      const selectedOptions = getSelectedOptions(select);
      selectedOptions.forEach((option) => {
        const tag = document.createElement("button");
        tag.className = "autocomplete-tag";
        tag.type = "button";
        const tagText = document.createElement("span");
        tagText.className = "autocomplete-tag-text";
        tagText.textContent = getOptionText(option);
        const tagRemove = document.createElement("span");
        tagRemove.className = "autocomplete-tag-remove";
        tagRemove.textContent = "×";
        tag.setAttribute(
          "aria-label",
          formatMessage(messages.removeLabelTemplate, { value: getOptionText(option) }),
        );
        tag.append(tagText, tagRemove);
        tag.addEventListener("click", (event) => {
          event.stopPropagation();
          option.selected = false;
          updateSelect();
          input.focus();
        });
        tags.append(tag);
      });
      updatePlaceholder();
    }

    function selectOption(option) {
      option.selected = true;
      input.value = "";
      updateSelect();
      input.focus({ preventScroll: true });
      showOptions();
    }

    function getSelectableOptions() {
      return Array.from(optionsList.querySelectorAll(".autocomplete-option:not(.autocomplete-option--empty)"));
    }

    function setActiveOption(index) {
      const options = getSelectableOptions();
      options.forEach((option) => {
        option.classList.remove("is-active");
        option.setAttribute("aria-selected", "false");
      });

      if (!options.length || index < 0) {
        activeOptionIndex = -1;
        input.removeAttribute("aria-activedescendant");
        return;
      }

      activeOptionIndex = Math.min(index, options.length - 1);
      const activeOption = options[activeOptionIndex];
      activeOption.classList.add("is-active");
      activeOption.setAttribute("aria-selected", "true");
      input.setAttribute("aria-activedescendant", activeOption.id);
      activeOption.scrollIntoView({ block: "nearest" });
    }

    function renderOptions() {
      const query = input.value.trim().toLocaleLowerCase("ru");
      const matches = Array.from(select.options)
        .filter((option) => !option.selected)
        .filter((option) => getOptionText(option).toLocaleLowerCase("ru").includes(query))
        .slice(0, 80);

      optionsList.replaceChildren();
      if (matches.length === 0) {
        const empty = document.createElement("div");
        empty.className = "autocomplete-option autocomplete-option--empty";
        empty.setAttribute("role", "option");
        empty.setAttribute("aria-disabled", "true");
        empty.textContent = messages.autocompleteEmpty;
        optionsList.append(empty);
        setActiveOption(-1);
        return;
      }

      matches.forEach((option, index) => {
        const item = document.createElement("button");
        item.className = "autocomplete-option";
        item.type = "button";
        item.id = `${listboxId}-option-${index}`;
        item.setAttribute("role", "option");
        item.setAttribute("aria-selected", "false");
        item.tabIndex = -1;
        item.textContent = getOptionText(option);
        item.addEventListener("mousedown", (event) => event.preventDefault());
        item.addEventListener("click", (event) => {
          event.stopPropagation();
          selectOption(option);
        });
        optionsList.append(item);
      });
      setActiveOption(-1);
    }

    select.addEventListener("change", () => {
      renderTags();
      renderOptions();
    });
    input.addEventListener("focus", showOptions);
    input.addEventListener("input", showOptions);
    input.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        hideOptions();
      }
      if (event.key === "ArrowDown") {
        event.preventDefault();
        if (input.getAttribute("aria-expanded") !== "true") {
          showOptions();
        }
        const options = getSelectableOptions();
        setActiveOption(activeOptionIndex + 1 >= options.length ? 0 : activeOptionIndex + 1);
      }
      if (event.key === "ArrowUp") {
        event.preventDefault();
        if (input.getAttribute("aria-expanded") !== "true") {
          showOptions();
        }
        const options = getSelectableOptions();
        setActiveOption(activeOptionIndex <= 0 ? options.length - 1 : activeOptionIndex - 1);
      }
      if (event.key === "Enter") {
        event.preventDefault();
        const options = getSelectableOptions();
        const optionToSelect = options[activeOptionIndex] || options[0];
        optionToSelect?.click();
      }
    });
    wrapper.addEventListener("click", () => input.focus());
    document.addEventListener("click", (event) => {
      if (!wrapper.contains(event.target)) hideOptions();
    });

    renderTags();
    renderOptions();
  }

  function updateDateFields() {
    const dateSelect = document.getElementById("date-select");
    const dateContainer = document.getElementById("specified-date-container");
    const rightDateWrap = document.getElementById("right-date-wrap");
    if (!dateSelect || !dateContainer || !rightDateWrap) return;

    const isSingle = dateSelect.value === "single_date";
    const isRange = dateSelect.value === "range_date";
    dateContainer.classList.toggle("is-hidden", !isSingle && !isRange);
    dateContainer.hidden = !isSingle && !isRange;
    rightDateWrap.classList.toggle("is-hidden", !isRange);
    rightDateWrap.hidden = !isRange;
  }

  function updateCalendarVisibility() {
    const checkbox = document.getElementById("show-calendar-checkbox");
    if (!checkbox) return;
    document.querySelectorAll(".calendar-slot").forEach((slot) => {
      slot.classList.toggle("is-hidden", !checkbox.checked);
      slot.hidden = !checkbox.checked;
      slot.closest(".day-content")?.classList.toggle("day-content--with-calendar", checkbox.checked);
    });
  }

  function setExtraFiltersVisibility(isVisible) {
    const container = document.getElementById("addition-filters-container");
    const state = document.getElementById("filters-visibility-state");
    const button = document.getElementById("more-filters-button");
    if (!container || !state || !button) return;

    const isHidden = !isVisible;
    container.classList.toggle("is-hidden", isHidden);
    container.hidden = isHidden;
    state.value = isHidden ? "0" : "1";
    button.setAttribute("aria-expanded", String(!isHidden));
    const label = button.querySelector("span");
    if (label) {
      const messages = getScheduleMessages();
      label.textContent = isHidden ? messages.moreFiltersLabel : messages.lessFiltersLabel;
    }
  }

  function toggleExtraFilters() {
    const container = document.getElementById("addition-filters-container");
    if (!container) return;

    setExtraFiltersVisibility(container.classList.contains("is-hidden"));
  }

  function getScheduleFilterForm() {
    return document.getElementById("schedule-filter-form");
  }

  function getFormControls(form) {
    return Array.from(form.elements).filter((element) => element.name);
  }

  function hasQueryFilters(form) {
    const query = new URLSearchParams(window.location.search);
    return getFormControls(form).some((element) => query.has(element.name));
  }

  function applyQueryFilters(form) {
    const query = new URLSearchParams(window.location.search);

    getFormControls(form).forEach((element) => {
      if (element instanceof HTMLSelectElement && element.multiple) {
        const selectedValues = query.getAll(element.name);
        Array.from(element.options).forEach((option) => {
          option.selected = selectedValues.includes(option.value);
        });
        element.dispatchEvent(new Event("change", { bubbles: true }));
        return;
      }
      if (element.type === "checkbox") {
        element.checked =
          query.has(element.name) &&
          query.getAll(element.name).some((value) => value === "1" || value === "true" || value === "on");
        element.dispatchEvent(new Event("change", { bubbles: true }));
        return;
      }
      element.value = query.get(element.name) || (element.id === "date-select" ? "today" : "");
      element.dispatchEvent(new Event("change", { bubbles: true }));
    });

    setExtraFiltersVisibility(query.get("addition_filters_visible") === "1");
  }

  function saveFilters() {
    const form = getScheduleFilterForm();
    if (!form) return;

    const filters = {};
    getFormControls(form).forEach((element) => {
      if (element.type === "submit" || element.type === "button") return;
      if (element instanceof HTMLSelectElement && element.multiple) {
        filters[element.name] = getSelectedOptions(element).map((option) => option.value);
        return;
      }
      if (element.type === "checkbox") {
        filters[element.name] = element.checked;
        return;
      }
      filters[element.name] = element.value;
    });

    try {
      localStorage.setItem(filtersStorageKey, JSON.stringify(filters));
    } catch (error) {
      // Browser storage may be unavailable in private mode.
    }
  }

  function restoreFilters() {
    const form = getScheduleFilterForm();
    if (!form) return;
    if (hasQueryFilters(form)) return;

    let filters;
    try {
      filters = JSON.parse(localStorage.getItem(filtersStorageKey) || "null");
    } catch (error) {
      filters = null;
    }
    if (!filters || typeof filters !== "object") return;

    getFormControls(form).forEach((element) => {
      if (!Object.prototype.hasOwnProperty.call(filters, element.name)) return;
      const value = filters[element.name];

      if (element instanceof HTMLSelectElement && element.multiple) {
        const selectedValues = Array.isArray(value) ? value.map(String) : [];
        Array.from(element.options).forEach((option) => {
          option.selected = selectedValues.includes(option.value);
        });
        element.dispatchEvent(new Event("change", { bubbles: true }));
        return;
      }
      if (element.type === "checkbox") {
        element.checked = Boolean(value);
        element.dispatchEvent(new Event("change", { bubbles: true }));
        return;
      }
      element.value = String(value);
      element.dispatchEvent(new Event("change", { bubbles: true }));
    });
    setExtraFiltersVisibility(filters.addition_filters_visible === "1");
  }

  function clearSavedFilters() {
    try {
      localStorage.removeItem(filtersStorageKey);
    } catch (error) {
      // Browser storage may be unavailable in private mode.
    }
  }

  function resetFilters() {
    clearSavedFilters();

    document.querySelectorAll("#schedule-filter-form select").forEach((select) => {
      if (select.id === "date-select") {
        select.value = "today";
      } else {
        Array.from(select.options).forEach((option) => {
          option.selected = false;
        });
      }
      select.dispatchEvent(new Event("change", { bubbles: true }));
    });

    const leftDate = document.getElementById("left-date");
    const rightDate = document.getElementById("right-date");
    if (leftDate) leftDate.value = "";
    if (rightDate) rightDate.value = "";

    const calendar = document.getElementById("show-calendar-checkbox");
    if (calendar) {
      calendar.checked = false;
      updateCalendarVisibility();
    }
    updateDateFields();
  }

  function setupPublicAlerts() {
    let dismissedAlertIds = [];
    try {
      dismissedAlertIds = JSON.parse(localStorage.getItem("schedule.dismissedAlerts") || "[]");
    } catch (error) {
      dismissedAlertIds = [];
    }

    const dismissedAlerts = new Set(dismissedAlertIds.map(String));
    document.querySelectorAll(".alert[data-alert-id]").forEach((alert) => {
      const alertId = alert.dataset.alertId;
      if (dismissedAlerts.has(alertId)) {
        alert.remove();
        return;
      }

      const closeButton = alert.querySelector(".alert-close");
      closeButton?.addEventListener("click", () => {
        if (alert.dataset.alertDismissible === "1") {
          dismissedAlerts.add(alertId);
          try {
            localStorage.setItem("schedule.dismissedAlerts", JSON.stringify([...dismissedAlerts]));
          } catch (error) {
            // Browser storage may be unavailable in private mode.
          }
        }
        alert.remove();
      });
    });
  }

  function setupDayToggles() {
    document.querySelectorAll(".day-toggle").forEach((button) => {
      const contentId = button.getAttribute("aria-controls");
      const content = contentId ? document.getElementById(contentId) : null;
      const daySection = button.closest(".day-section");
      if (!content || !daySection) return;

      button.addEventListener("click", () => {
        const isExpanded = button.getAttribute("aria-expanded") === "true";
        const nextExpanded = !isExpanded;
        button.setAttribute("aria-expanded", String(nextExpanded));
        const label = nextExpanded ? button.dataset.collapseLabel || "" : button.dataset.expandLabel || "";
        button.setAttribute("aria-label", label);
        button.setAttribute("title", label);
        content.hidden = !nextExpanded;
        daySection.classList.toggle("is-collapsed", !nextExpanded);
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    const form = getScheduleFilterForm();
    const shouldApplyQueryFilters = form && hasQueryFilters(form);

    if (form && !shouldApplyQueryFilters) {
      restoreFilters();
    }
    document.querySelectorAll("#schedule-filter-form select[multiple]").forEach(createAutocompleteSelect);

    form?.addEventListener("submit", saveFilters);
    document.getElementById("date-select")?.addEventListener("change", updateDateFields);
    document
      .getElementById("show-calendar-checkbox")
      ?.addEventListener("change", updateCalendarVisibility);
    document
      .getElementById("more-filters-button")
      ?.addEventListener("click", toggleExtraFilters);
    document
      .getElementById("reset-filters-button")
      ?.addEventListener("click", resetFilters);

    if (form && shouldApplyQueryFilters) {
      applyQueryFilters(form);
    }

    setupPublicAlerts();
    setupDayToggles();

    updateDateFields();
    updateCalendarVisibility();
  });
})();
