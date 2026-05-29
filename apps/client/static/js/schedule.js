(function () {
  function getOptionText(option) {
    return option.textContent.trim();
  }

  function getSelectedOptions(select) {
    return Array.from(select.options).filter((option) => option.selected);
  }

  function createAutocompleteSelect(select) {
    if (!select.multiple || select.dataset.autocompleteReady === "1") return;
    select.dataset.autocompleteReady = "1";
    select.classList.add("native-select-hidden");

    const wrapper = document.createElement("div");
    wrapper.className = "autocomplete-select";

    const tags = document.createElement("div");
    tags.className = "autocomplete-tags";

    const input = document.createElement("input");
    input.className = "autocomplete-input";
    input.type = "text";
    input.autocomplete = "off";
    input.placeholder = "Начните вводить";

    const optionsList = document.createElement("div");
    optionsList.className = "autocomplete-options is-hidden";
    optionsList.setAttribute("role", "listbox");

    wrapper.append(tags, input, optionsList);
    select.after(wrapper);

    function hideOptions() {
      optionsList.classList.add("is-hidden");
    }

    function showOptions() {
      renderOptions();
      optionsList.classList.remove("is-hidden");
    }

    function updateSelect() {
      select.dispatchEvent(new Event("change", { bubbles: true }));
    }

    function updatePlaceholder() {
      const hasSelection = getSelectedOptions(select).length > 0;
      input.placeholder = hasSelection ? "" : "Начните вводить";
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
        tag.setAttribute("aria-label", `Удалить ${getOptionText(option)}`);
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
        empty.textContent = "Ничего не найдено";
        optionsList.append(empty);
        return;
      }

      matches.forEach((option) => {
        const item = document.createElement("button");
        item.className = "autocomplete-option";
        item.type = "button";
        item.textContent = getOptionText(option);
        item.addEventListener("mousedown", (event) => event.preventDefault());
        item.addEventListener("click", (event) => {
          event.stopPropagation();
          selectOption(option);
        });
        optionsList.append(item);
      });
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
      if (event.key === "Enter") {
        event.preventDefault();
        const firstOption = optionsList.querySelector(".autocomplete-option:not(.autocomplete-option--empty)");
        firstOption?.click();
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
    rightDateWrap.classList.toggle("is-hidden", !isRange);
  }

  function updateCalendarVisibility() {
    const checkbox = document.getElementById("show-calendar-checkbox");
    if (!checkbox) return;
    document.querySelectorAll(".calendar-slot").forEach((slot) => {
      slot.classList.toggle("is-hidden", !checkbox.checked);
      slot.closest(".day-content")?.classList.toggle("day-content--with-calendar", checkbox.checked);
    });
  }

  function toggleExtraFilters() {
    const container = document.getElementById("addition-filters-container");
    const state = document.getElementById("filters-visibility-state");
    const button = document.getElementById("more-filters-button");
    if (!container || !state || !button) return;

    const isHidden = container.classList.toggle("is-hidden");
    state.value = isHidden ? "0" : "1";
    const label = button.querySelector("span");
    if (label) label.textContent = isHidden ? "Больше фильтров" : "Меньше фильтров";
  }

  function resetFilters() {
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

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("#schedule-filter-form select[multiple]").forEach(createAutocompleteSelect);

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

    document.querySelectorAll(".alert-close").forEach((button) => {
      button.addEventListener("click", () => button.closest(".alert")?.remove());
    });

    updateDateFields();
    updateCalendarVisibility();
  });
})();
