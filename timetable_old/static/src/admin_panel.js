const csrftoken = getCookie("csrftoken");
const url = "http://127.0.0.1:81/admin/";
const urlStatic = "http://127.0.0.1:81/static/";
const secondsTimeWait = 600;
/*---------- ИЗМЕНЕНИЕ КОНФИГУРАЦИИ СИСТЕМЫ -----------*/

// Найти все элементы формы и кнопку
const formElements = document.querySelectorAll(
  "#scanFrequency, #rootUrl, #authFile, #storageType"
);
const applyChangesButton = document.getElementById("applyChangesButton");

// Список ссылок на скачивание снимков системы
const snapshotDownloadUrls = {};
fillSnapshotDownloadUrls();

// Сохраняем начальные значения всех полей в объект
const initialValues = {};
formElements.forEach((element) => {
  if (element.type === "file") {
    initialValues[element.id] = null; // Для файлов значение по умолчанию null
  } else {
    initialValues[element.id] = element.value; // Сохраняем текущее значение
  }
});

// Функция для проверки, изменилось ли состояние формы
function checkFormChanges() {
  let isChanged = false;

  formElements.forEach((element) => {
    if (element.type === "file") {
      // Проверяем, выбран ли файл
      if (element.files.length > 0) {
        isChanged = true;
      }
    } else {
      // Сравниваем текущее значение с исходным
      if (element.value !== initialValues[element.id]) {
        isChanged = true;
      }
    }
  });

  // Активируем или деактивируем кнопку в зависимости от изменений
  applyChangesButton.disabled = !isChanged;
}

// Добавляем обработчики событий для всех элементов
formElements.forEach((element) => {
  element.addEventListener("input", checkFormChanges);
  element.addEventListener("change", checkFormChanges); // Для файлов и select
});

// Обработчик для кнопки
applyChangesButton.addEventListener("click", async () => {
  if (!applyChangesButton.disabled) {
    // Применить настройки

    let settingsSetCorrect = await setSettings();

    if (settingsSetCorrect) {
      // Обновить изменения
      applyChanges();
    }
  }
});

// Функция applyChanges
function applyChanges() {
  // После применения изменений обновляем сохранённые начальные значения
  formElements.forEach((element) => {
    if (element.type === "file") {
      initialValues[element.id] = null; // Сбрасываем значение файла
    } else {
      initialValues[element.id] = element.value; // Сохраняем текущее значение
    }
  });

  // Деактивируем кнопку после применения
  applyChangesButton.disabled = true;
}

async function setSettings() {
  const scanFrequency = document.getElementById("scanFrequency").value;
  const rootUrl = document.getElementById("rootUrl").value;
  const storageType = document.getElementById("storageType").value;
  const authFile = document.getElementById("authFile").files[0];

  const formData = new FormData();
  formData.append("scanFrequency", scanFrequency);
  formData.append("rootUrl", rootUrl);
  formData.append("storageType", storageType);
  if (authFile) {
    formData.append("authFile", authFile);
  }

  try {
    const response = await fetch(`${url}settings`, {
      method: "POST",
      headers: {
        "X-CSRFToken": csrftoken,
      },
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

async function sendSystemSettings(params) {
  // Проверить что есть изменённые параметры
  if (Object.keys(params).length === 0) {
    return null;
  }

  // Отправить запрос
  const response = await fetch(`${url}settings`, {
    method: "POST", // Указываем метод запроса
    headers: {
      "Content-Type": "application/json", // Указываем тип данных
      "X-CSRFToken": csrftoken,
    },
    body: JSON.stringify(params), // Преобразуем объект в JSON-строку
  });

  return response.ok;
}

function getSystemSettingsRequestParam() {
  const timeUpdate = document.getElementById("scanFrequency");
  const analyzeUrl = document.getElementById("rootUrl");
  const downloadStorage = document.getElementById("storageType");

  // Получить параметры
  params = {};
  if (timeUpdate.value !== initialValues[timeUpdate.id]) {
    params["time_update"] = timeUpdate.value;
  }
  if (analyzeUrl.value !== initialValues[analyzeUrl.id]) {
    params["analyze_url"] = analyzeUrl.value;
  }
  if (downloadStorage.value !== initialValues[downloadStorage.id]) {
    params["download_storage"] = downloadStorage.value;
  }

  return params;
}
async function sendAuthorizationFile() {
  const authFileInput = document.getElementById("authFile");
  const file = authFileInput.files[0];

  if (!file?.name.endsWith(".json")) {
    alert("Файл должен быть в формате JSON!");
    return false;
  }

  try {
    let formData = new FormData();
    formData.append("authFile", file);
    // Add a parameter to indicate this is for Google credentials
    // formData.append('isGoogleCredentials', 'true');

    const response = await fetch(`${url}auth`, {
      method: "POST",
      headers: {
        "X-CSRFToken": csrftoken,
      },
      body: formData,
    });

    if (!response.ok) {
      throw new Error("Ошибка сервера");
    }

    const result = await response.json();
    if (result.status === "success") {
      alert("Файл credentials.json успешно загружен!");
      return true;
    } else {
      alert(`Ошибка: ${result.message}`);
      return false;
    }
  } catch (error) {
    console.error("Ошибка:", error);
    alert("Не удалось загрузить файл. Проверьте консоль для подробностей.");
    return false;
  }
}

/*---------- ПОЛУЧЕНИЕ СОСТОЯНИЯ СИСТЕМЫ -----------*/

async function getSnapshot() {
  const snapshotType = document.getElementById("snapshotType").value;
  const spinner = document.getElementById("snapshotSpinner");
  const downloadButton = document.getElementById("downloadButton");

  // Скрываем кнопку "Скачать" и показываем спиннер
  downloadButton.style.display = "none";
  spinner.style.display = "block";

  // Создать тело запроса
  let params = new URLSearchParams();
  params.append("action", "make_new");
  params.append("snapshot", snapshotType);

  // Делаем запрос на создание нового снимка и получаем id процесса
  const processId = await makePostResponse("snapshot", params);

  // Дождаться получения снимка если есть id процесса
  if (processId !== null) {
    let time = new Date(); // Время начала изготовления списка
    let newURL = ""; // Новая URL

    // Проверять состояние процесса создания файла до истечения таймаута или пока файл не найден
    while ((new Date() - time) / 1000 < secondsTimeWait && newURL === "") {
      // Повторный запрос
      newURL = await getSnapshotUrl(processId);
      if (newURL !== "" && newURL !== null) {
        snapshotDownloadUrls[snapshotType] = newURL;
      }

      await new Promise((resolve) => setTimeout(resolve, 1000));
    }
    if (newURL !== "" && newURL !== null) {
      alert(`Снимок "${snapshotType}" создан и готов к загрузке!`);
    } else {
      alert(
        `Не удалось создать снимок "${snapshotType}"! Можно скачать предыдущий.`
      );
    }

    spinner.style.display = "none"; // Скрываем спиннер
    if (snapshotDownloadUrls[snapshotType] === "") {
      downloadButton.style.display = "none"; // Скрываем кнопку "Скачать"
    } else {
      downloadButton.style.display = "block"; // Показываем кнопку "Скачать"
    }
  }
}

async function getSnapshotUrl(processId) {
  // Отправить запрос
  const response = await fetch(`${url}snapshot?process_id=${processId}`);

  // Завершить выполнение, если ответ некорректный
  if (response.ok) {
    // Обработать ответ
    const data = await response.json();
    if (data?.status === "success") {
      return data?.result?.url;
    } else if (data?.status === "error") {
      alert(data?.result?.error_message);
    } else if (data?.status === "running") {
      return "";
    }
  }

  return null;
}

async function fillSnapshotDownloadUrls() {
  const snapshotTypeSelector = document.getElementById("snapshotType");
  for (const option of Array.from(snapshotTypeSelector.options)) {
    snapshotDownloadUrls[option.label] = await getLastSnapshotUrl(option.label);
  }
}

async function getLastSnapshotUrl(snapshot) {
  // Отправить запрос
  const response = await fetch(`${url}snapshot?snapshot_type=${snapshot}`);

  // Завершить выполнение, если ответ некорректный
  if (!response.ok) {
    return null;
  }

  return response.json().url;
}

// Найти элементы
const snapshotTypeSelect = document.getElementById("snapshotType");
const getSnapshotButton = document.getElementById("getSnapshotButton");
const downloadButton = document.getElementById("downloadButton");

// Обработчик скрытия кнопки "Скачать" при изменении списка
snapshotTypeSelect.addEventListener("change", () => {
  // скрыть кнопку, если нет ссылки для скачивания
  const url = snapshotDownloadUrls[snapshotTypeSelect.value];
  if (url === "" || url === undefined) {
    downloadButton.style.display = "none"; // Скрыть кнопку "Скачать"
  } else {
    downloadButton.style.display = "block";
  }
});

downloadButton.addEventListener("click", () => {
  const url = snapshotDownloadUrls[snapshotTypeSelect.value];
  const fileName = url.split("/").pop();

  downloadFile(`${urlStatic}${url}`, fileName);
});

/*---------- ОЧИСТКА СИСТЕМЫ -----------*/

// Функция для обработки кнопки "Очистить"
function requestDataCleansing() {
  // Получаем текст выбранного элемента
  const dataLocationSelect = document.getElementById("dataLocation");
  const spinner = document.getElementById("dataCleanSpinner");
  const selectedOptionText =
    dataLocationSelect.options[dataLocationSelect.selectedIndex].text;

  // Показываем окно подтверждения
  const isConfirmed = window.confirm(
    `Вы уверены, что хотите очистить: ${selectedOptionText.toLowerCase()}?`
  );

  // Если пользователь нажал "OK", выполняем очистку
  if (isConfirmed) {
    spinner.style.display = "block";
    dellData();
    alert("Происходит очистка. Пожалуйста подождите."); // Сообщение о начале очистки
  } else {
    spinner.style.display = "none";
    // Если пользователь нажал "Отмена", ничего не делаем
    alert("Очистка отменена.");
  }
}

async function dellData() {
  const dataLocationSelect = document.getElementById("dataLocation");
  const component = dataLocationSelect.value;
  // Создать тело запроса
  let params = new URLSearchParams();
  params.append("action", "dell");
  params.append("component", component);

  // Делаем запрос на создание нового снимка и получаем id процесса
  const processId = await makePostResponse("manage_storage", params);

  // Дождаться получения снимка если есть id процесса
  if (processId !== null) {
    let time = new Date(); // Время начала изготовления списка
    let success = null;

    // Проверять состояние процесса создания файла до истечения таймаута или пока файл не найден
    while ((new Date() - time) / 1000 < secondsTimeWait && success === null) {
      // Повторный запрос
      success = await getDellResult(processId);
      // Ожидание
      await new Promise((resolve) => setTimeout(resolve, 1000));
    }

    if (success === true) {
      alert(`Очистка: "${component.toLowerCase()}" завершена успешно!`);
    } else {
      alert(`Не удалось завершить очистку: "${component.toLowerCase()}"!`);
    }
  }

  const spinner = document.getElementById("dataCleanSpinner");
  spinner.style.display = "none";
}

async function getDellResult(processId) {
  // Отправить запрос
  const response = await fetch(`${url}manage_storage?process_id=${processId}`);

  // Завершить выполнение, если ответ некорректный
  if (response.ok) {
    // Обработать ответ
    const data = await response.json();
    if (data?.status === "success") {
      return true;
    } else if (data?.status === "error") {
      alert(data?.result?.error_message);
      return false;
    }
  }

  return null;
}
// Функция для запуска обновления расписания
async function requestTimetableUpdate() {
  const updateButton = document.getElementById("updateTimetableButton");
  const spinner = document.getElementById("timetableUpdateSpinner");

  updateButton.disabled = true;
  spinner.style.display = "block";

  try {
    // Формируем параметры в формате x-www-form-urlencoded
    const params = new URLSearchParams();
    params.append("action", "update_timetable");

    const response = await fetch(`${url}update_timetable`, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        "X-CSRFToken": csrftoken,
      },
      body: params.toString(),
    });

    if (!response.ok) {
      throw new Error("Ошибка при запуске обновления");
    }

    const data = await response.json();
    const processId = data.id;

    // Проверяем статус задачи
    let status = "running";
    while (status === "running") {
      await new Promise((resolve) => setTimeout(resolve, 1000)); // Ждем 1 секунду
      const statusResponse = await fetch(
        `${url}update_timetable?process_id=${processId}`,
        {
          method: "GET",
          headers: {
            "X-CSRFToken": csrftoken,
          },
        }
      );

      if (!statusResponse.ok) {
        throw new Error("Ошибка при проверке статуса");
      }

      const statusData = await statusResponse.json();
      status = statusData.status;

      if (status === "success") {
        alert("Обновление расписания успешно завершено!");
        break;
      } else if (status === "error") {
        alert(
          `Ошибка при обновлении: ${
            statusData.error_message || "Неизвестная ошибка"
          }\nПодробности: ${JSON.stringify(statusData.result || {})}`
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
// Функция для получения CSRF-токена из cookie
function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== "") {
    const cookies = document.cookie.split(";");
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.startsWith(name + "=")) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

async function makeResponse(url_dir, responseType, params) {
  // Отправить запрос
  return fetch(`${url}${url_dir}`, {
    method: responseType, // Указываем метод запроса
    headers: {
      "Content-Type": "application/json", // Указываем тип данных
      "X-CSRFToken": csrftoken,
    },
    body: JSON.stringify(params), // Преобразуем объект в JSON-строку
  });
}

function downloadFile(url, filename) {
  const link = document.createElement("a"); // Создаем элемент <a>
  link.href = url; // Указываем ссылку на файл
  link.download = filename; // Указываем имя файла для скачивания

  // Добавляем элемент в DOM и инициируем скачивание
  document.body.appendChild(link);
  link.click();

  // Удаляем элемент из DOM
  document.body.removeChild(link);
}

async function makePostResponse(nextUrl, params) {
  // Отправить запрос
  const response = await fetch(`${url}${nextUrl}`, {
    method: "POST", // Указываем метод запроса
    headers: {
      "Content-Type": "application/x-www-form-urlencoded", // Указываем тип данных
      "X-CSRFToken": csrftoken,
    },
    body: params.toString(), // Преобразуем объект в JSON-строку
  });

  // Завершить выполнение, если ответ некорректный
  if (!response.ok) {
    return null;
  }

  // Распарсить ответ и вернуть номер процесса
  const data = await response.json();

  // Вернуть ID процесса, если снимок принят в работу.
  return data?.id;
}
