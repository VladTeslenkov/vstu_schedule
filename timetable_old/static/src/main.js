
console.log("JavaScript подключен и работает!");


function adjustFontSizeToFit() {
    const titles = document.querySelectorAll('.card-title, .degree-title');

    titles.forEach(title => {
        let fontSize = 2; // Начинаем с максимального размера шрифта
        title.style.fontSize = fontSize + 'rem';

        // Проверяем, помещается ли текст с максимальным размером
        if (title.scrollHeight > title.clientHeight) {
            // Уменьшаем шрифт, пока текст не помещается внутри высоты заголовка
            while (title.scrollHeight > title.clientHeight) {
                fontSize -= 0.05; // Уменьшаем размер шрифта
                title.style.fontSize = fontSize + 'rem';

                // Прекращаем уменьшение, если размер шрифта достигает минимального значения
                if (fontSize <= 0.8) {
                    break;
                }
            }
        }
    });
}

// Запускаем функцию после загрузки страницы
window.addEventListener('load', adjustFontSizeToFit);

// Перезапускаем функцию при изменении размера окна
window.addEventListener('resize', adjustFontSizeToFit);






// Функция для определения семестра и учебного года
function updateScheduleTitle() {
    const titleElement = document.getElementById('scheduleTitle');
    const semesterElement = document.getElementById('semester');
    const yearRangeElement = document.getElementById('yearRange');

    const currentDate = new Date();
    const currentYear = currentDate.getFullYear();
    const currentMonth = currentDate.getMonth() + 1; // Месяцы идут от 0 до 11, поэтому добавляем 1
    const currentDay = currentDate.getDate();

    let semester;
    let yearStart;
    let yearEnd;

    // Определяем семестр на основе текущей даты
    if ((currentMonth > 7) || (currentMonth === 7 && currentDay >= 20) || (currentMonth <= 2) || (currentMonth === 2 && currentDay <= 10)) {
        // С 20 июля по 10 февраля - 1-й семестр
        semester = '1-й';
        if (currentMonth > 6) {
            yearStart = currentYear;
            yearEnd = currentYear + 1;
        } else {
            yearStart = currentYear - 1;
            yearEnd = currentYear;
        }
    } else if ((currentMonth > 2 && currentMonth < 7) || (currentMonth === 2 && currentDay >= 11) || (currentMonth === 7 && currentDay <= 19)) {
        // С 11 февраля по 19 июля - 2-й семестр
        semester = '2-й';
        yearStart = currentYear - 1;
        yearEnd = currentYear;
    }

    // Устанавливаем значения в HTML
    semesterElement.textContent = semester;
    yearRangeElement.textContent = `${yearStart}-${yearEnd}`;
}


// Вызываем функцию при загрузке страницы
window.onload = updateScheduleTitle;




// Доступные факультеты для каждой формы обучения
const facultiesBachelors = {
    "Очная": [
        "Факультет автоматизированных систем, транспорта и вооружений",
        "Факультет автомобильного транспорта",
        "Факультет технологии конструкционных материалов",
        "Факультет технологии пищевых производств",
        "Факультет экономики и управления",
        "Факультет электроники и вычислительной техники",
        "Химико-технологический факультет",
        "Дополнительные занятия для иностранных студентов первых курсов"
    ],
    "Очно-заочная форма": [
        "Вечерний технологический факультет (Кировский район)",
        "Вечерний технологический факультет (Красноармейский район)",
        "Факультет подготовки инженерных кадров"
    ],
    "Заочная": [
        "Вечерний технологический факультет (Кировский район)",
        "Вечерний технологический факультет (Красноармейский район)",
        "Факультет подготовки инженерных кадров"
    ]
};

// Факультеты, которые предлагают 5 курсов
const fiveCourseFacultiesBachelors = [
    "Факультет автоматизированных систем, транспорта и вооружений",
    "Вечерний технологический факультет (Кировский район)",
    "Вечерний технологический факультет (Красноармейский район)",
    "Факультет подготовки инженерных кадров"
];

const oneCourseFacultiesBachelors = [
    "Дополнительные занятия для иностранных студентов первых курсов"
];

// Функция для разблокировки следующего селектора бакалавриата и обновления его опций
function unlockNextSelectForBachelor(currentLevel) {
    const formSelect = document.getElementById("form-select");
    const facultySelect = document.getElementById("faculty-select");
    const courseSelect = document.getElementById("course-select");
    const normativitySelect = document.getElementById("normativity-of-studying-periods-select");

    // Разблокируем или обновляем факультеты при выборе формы обучения
    if (currentLevel === 1) {
        facultySelect.disabled = false;
        courseSelect.disabled = true;
        normativitySelect.disabled = true;

        facultySelect.selectedIndex = 0;
        courseSelect.selectedIndex = 0;
        normativitySelect.selectedIndex = 0;

        // Очищаем и заполняем варианты факультетов
        facultySelect.innerHTML = '<option value="" disabled selected>Выбрать факультет</option>';
        const selectedForm = formSelect.value;
        if (facultiesBachelors[selectedForm]) {
            facultiesBachelors[selectedForm].forEach(faculty => {
                const option = document.createElement("option");
                option.value = faculty;
                option.textContent = faculty;
                facultySelect.appendChild(option);
            });
        }
    }
    // Разблокируем или обновляем курсы при выборе факультета
    else if (currentLevel === 2) {
        courseSelect.disabled = false;
        normativitySelect.disabled = true;
        courseSelect.selectedIndex = 0;
        normativitySelect.selectedIndex = 0;

        // Очищаем и заполняем курсы
        courseSelect.innerHTML = '<option value="" disabled selected>Выбрать курс</option>';
        const selectedFaculty = facultySelect.value;

        let countOfCourses = 4;
        if (fiveCourseFacultiesBachelors.includes(selectedFaculty)) {countOfCourses = 5;}
        if(oneCourseFacultiesBachelors.includes(selectedFaculty)) {countOfCourses = 1;}

        for (let i = 1; i <= countOfCourses; i++) {
            const option = document.createElement("option");
            option.value = `${i} курс`;
            option.textContent = `${i} курс`;
            courseSelect.appendChild(option);
        }

        if (document.getElementById("form-select").value === "Очная")
        {
            if(document.getElementById("faculty-select").value === "Дополнительные занятия для иностранных студентов первых курсов")
            {
                courseSelect.disabled = true;
                courseSelect.selectedIndex = 1;
                normativitySelect.disabled = true;
                normativitySelect.selectedIndex = 1;
            }
            else
            {
                normativitySelect.disabled = true;
                normativitySelect.selectedIndex = 2;
            }
        }

    }
    // Разблокируем последний селектор для выбора срока обучения
    else if (currentLevel === 3) {
        if (document.getElementById("normativity-of-studying-periods-select").value === "")
        {
            normativitySelect.disabled = false;
            normativitySelect.selectedIndex = 0;
        }

    }
}

const facultiesMaster= {
    "Очная": [
        "ВМЦЭ",
        "ФАСТиВ",
        "ФАТ",
        "ФТКМ",
        "ФТКМ вечерники",
        "ФТПП",
        "ФЭВТ",
        "ФЭВТ вечерники",
        "ФЭУ",
        "ХТФ"
],
  "Очно-заочная форма": [
    "САПР"
]
};



// Функция для разблокировки следующего селектора бакалавриата и обновления его опций
function unlockNextSelectForMaster(currentLevel) {
    const formSelect = document.getElementById("form-select");
    const facultySelect = document.getElementById("faculty-select");
    const courseSelect = document.getElementById("course-select");

    // Разблокируем или обновляем факультеты при выборе формы обучения
    if (currentLevel === 1) {
        facultySelect.disabled = false;
        courseSelect.disabled = true;

        facultySelect.selectedIndex = 0;
        courseSelect.selectedIndex = 0;

        // Очищаем и заполняем варианты факультетов
        facultySelect.innerHTML = '<option value="" disabled selected>Выбрать факультет</option>';
        const selectedForm = formSelect.value;
        if (facultiesMaster[selectedForm]) {
            facultiesMaster[selectedForm].forEach(faculty => {
                const option = document.createElement("option");
                option.value = faculty;
                option.textContent = faculty;
                facultySelect.appendChild(option);
            });
        }
    }
    // Разблокируем или обновляем курсы при выборе факультета
    else if (currentLevel === 2) {
        courseSelect.disabled = false;
        courseSelect.selectedIndex = 0;

        // Очищаем и заполняем курсы
        courseSelect.innerHTML = '<option value="" disabled selected>Выбрать курс</option>';
        const selectedFaculty = facultySelect.value;

        /**********************/
        let countOfCourses = 2;

        for (let i = 1; i <= countOfCourses; i++) {
            const option = document.createElement("option");
            option.value = `${i} курс`;
            option.textContent = `${i} курс`;
            courseSelect.appendChild(option);
        }
        /*************/


    }
    // Разблокируем последний селектор для выбора срока обучения
    else if (currentLevel === 3) {
        normativitySelect.disabled = false;
        normativitySelect.selectedIndex = 0;

    }
}




// Функция для сброса всех фильтров
function resetFilters() {
    document.getElementById("form-select").selectedIndex = 0;
    document.getElementById("faculty-select").selectedIndex = 0;
    document.getElementById("course-select").selectedIndex = 0;
    document.getElementById("normativity-of-studying-periods-select").selectedIndex = 0;
    document.getElementById("faculty-select").disabled = true;
    document.getElementById("course-select").disabled = true;
    document.getElementById("normativity-of-studying-periods-select").disabled = true;
}









document.addEventListener("DOMContentLoaded", () => {

    // Находим кнопку
    const scrollToTopButton = document.getElementById("scrollToTop");

    // Функция для показа кнопки
    const toggleScrollButton = () => {
        if (window.scrollY > 75) {
            scrollToTopButton.classList.add("visible");
        } else {
            scrollToTopButton.classList.remove("visible");
        }
    };

    // Добавляем событие на прокрутку
    window.addEventListener("scroll", toggleScrollButton);

    // Добавляем событие на клик по кнопке
    scrollToTopButton.addEventListener("click", () => {
        window.scrollTo({
            top: 0,
            behavior: "smooth", // Плавная прокрутка
        });
    });
});





