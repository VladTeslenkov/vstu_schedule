const csrftoken = getCookie("csrftoken");
const url = "/panel/";
const secondsTimeWait = 600;

/*---------- ИЗМЕНЕНИЕ КОНФИГУРАЦИИ СИСТЕМЫ -----------*/

const formElements = document.querySelectorAll("#scanFrequency, #rootUrl");
const applyChangesButton = document.getElementById("applyChangesButton");

// Сохраняем начальные значения полей
const initialValues = {};
formElements.forEach((element) => {
  initialValues[element.id] = element.value;
});

// Активируем кнопку если форма изменилась
function checkFormChanges() {
  let isChanged = false;
  formElements.forEach((element) => {
    if (element.value !== initialValues[element.id]) {
      isChanged = true;
    }
  });
  applyChangesButton.disabled = !isChanged;
}

formElements.forEach((element) => {
  element.addEventListener("input", checkFormChanges);
  element.addEventListener("change", checkFormChanges);
});

applyChangesButton.addEventListener("click", async () => {
  if (!applyChangesButton.disabled) {
    const success = await setSettings();
    if (success) {
      formElements.forEach((element) => {
        initialValues[element.id] = element.value;
      });
      applyChangesButton.disabled = true;
    }
  }
});

async function setSettings() {
  const scanFrequency = document.getElementById("scanFrequency").value;
  const rootUrl = document.getElementById("rootUrl").value;

  const formData = new FormData();
  formData.append("scanFrequency", scanFrequency);
  formData.append("rootUrl", rootUrl);

  try {
    const response = await fetch(`${url}settings`, {
      method: "POST",
      headers: { "X-CSRFToken": csrftoken },
      body: formData,
    });

    const data = await response.json();
    if (data.status === "success") {
      alert("Настройки успешно применены!");
      return true;
    } else {
      alert(`Ошибка при сохранении настроек: ${data.error_message}`);
      return false;
    }
  } catch (error) {
    alert(`Ошибка: ${error.message}`);
    return false;
  }
}

/*---------- ОЧИСТКА СИСТЕМЫ -----------*/

function requestDataCleansing() {
  const dataLocationSelect = document.getElementById("dataLocation");
  const spinner = document.getElementById("dataCleanSpinner");
  const selectedText =
    dataLocationSelect.options[dataLocationSelect.selectedIndex].text;

  const isConfirmed = window.confirm(
    `Вы уверены, что хотите очистить: ${selectedText.toLowerCase()}?`,
  );

  if (isConfirmed) {
    spinner.style.display = "block";
    dellData();
    alert("Происходит очистка. Пожалуйста подождите.");
  } else {
    alert("Очистка отменена.");
  }
}

async function dellData() {
  const component = document.getElementById("dataLocation").value;
  const spinner = document.getElementById("dataCleanSpinner");

  const params = new URLSearchParams();
  params.append("action", "dell");
  params.append("component", component);

  const taskId = await makePostResponse("manage_storage", params);

  if (taskId !== null) {
    let time = new Date();
    let success = null;

    while ((new Date() - time) / 1000 < secondsTimeWait && success === null) {
      success = await getTaskResult("manage_storage", taskId);
      await new Promise((resolve) => setTimeout(resolve, 1000));
    }

    if (success === true) {
      alert(`Очистка: "${component.toLowerCase()}" завершена успешно!`);
    } else {
      alert(`Не удалось завершить очистку: "${component.toLowerCase()}"!`);
    }
  }

  spinner.style.display = "none";
}

async function getTaskResult(endpoint, taskId) {
  const response = await fetch(`${url}${endpoint}?task_id=${taskId}`);
  if (!response.ok) return null;

  const data = await response.json();
  if (data?.status === "success") return true;
  if (data?.status === "error") {
    alert(data?.error_message || "Неизвестная ошибка");
    return false;
  }
  return null;
}

/*---------- ОБНОВЛЕНИЕ РАСПИСАНИЯ -----------*/

async function requestTimetableUpdate() {
  const updateButton = document.getElementById("updateTimetableButton");
  const spinner = document.getElementById("timetableUpdateSpinner");

  updateButton.disabled = true;
  spinner.style.display = "block";

  try {
    const response = await fetch(`${url}update_timetable`, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        "X-CSRFToken": csrftoken,
      },
    });

    if (!response.ok) throw new Error("Ошибка при запуске обновления");

    const data = await response.json();
    const taskId = data.id;

    let status = "running";
    while (status === "running") {
      await new Promise((resolve) => setTimeout(resolve, 1000));

      const statusResponse = await fetch(
        `${url}update_timetable?task_id=${taskId}`,
      );
      if (!statusResponse.ok) throw new Error("Ошибка при проверке статуса");

      const statusData = await statusResponse.json();
      status = statusData.status;

      if (status === "success") {
        alert("Обновление расписания успешно завершено!");
        break;
      } else if (status === "error") {
        alert(
          `Ошибка при обновлении: ${statusData.error_message || "Неизвестная ошибка"}`,
        );
        break;
      }
    }
  } catch (error) {
    alert(`Ошибка: ${error.message}`);
  } finally {
    updateButton.disabled = false;
    spinner.style.display = "none";
  }
}

/*---------- УТИЛИТЫ -----------*/

function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== "") {
    for (const cookie of document.cookie.split(";")) {
      const c = cookie.trim();
      if (c.startsWith(name + "=")) {
        cookieValue = decodeURIComponent(c.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

async function makePostResponse(nextUrl, params) {
  const response = await fetch(`${url}${nextUrl}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
      "X-CSRFToken": csrftoken,
    },
    body: params.toString(),
  });

  if (!response.ok) return null;

  const data = await response.json();
  return data?.id ?? null;
}
