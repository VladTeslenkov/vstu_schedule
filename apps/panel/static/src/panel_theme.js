(function () {
  const storageKey = "panel.theme";
  const choiceOrder = ["auto", "light", "dark"];
  const choices = new Set(choiceOrder);
  const labels = {
    auto: "Тема: авто",
    light: "Тема: светлая",
    dark: "Тема: тёмная",
  };
  const mediaQuery = window.matchMedia("(prefers-color-scheme: light)");

  function storedChoice() {
    let value = "auto";
    try {
      value = localStorage.getItem(storageKey) || "auto";
    } catch (error) {
      value = "auto";
    }
    return choices.has(value) ? value : "auto";
  }

  function resolvedTheme(choice) {
    if (choice === "auto") {
      return mediaQuery.matches ? "light" : "dark";
    }
    return choice;
  }

  function applyTheme(choice) {
    const normalizedChoice = choices.has(choice) ? choice : "auto";
    document.documentElement.dataset.theme = resolvedTheme(normalizedChoice);
    document.documentElement.dataset.themeChoice = normalizedChoice;

    const label = document.querySelector("[data-panel-theme-label]");
    if (label) {
      label.textContent = labels[normalizedChoice];
    }
    const button = document.querySelector("[data-panel-theme-toggle]");
    if (button) {
      button.setAttribute("aria-label", labels[normalizedChoice]);
      button.setAttribute("title", labels[normalizedChoice]);
    }
  }

  const button = document.querySelector("[data-panel-theme-toggle]");
  if (button) {
    button.addEventListener("click", () => {
      const currentChoice = storedChoice();
      const currentIndex = choiceOrder.indexOf(currentChoice);
      const choice = choiceOrder[(currentIndex + 1) % choiceOrder.length];
      try {
        localStorage.setItem(storageKey, choice);
      } catch (error) {
        // Keep the in-memory change even when storage is unavailable.
      }
      applyTheme(choice);
    });
  }

  mediaQuery.addEventListener("change", () => {
    if (storedChoice() === "auto") {
      applyTheme("auto");
    }
  });

  applyTheme(storedChoice());
})();
