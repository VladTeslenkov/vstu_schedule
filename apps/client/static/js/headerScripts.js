document.addEventListener("DOMContentLoaded", function() {
    initSelect2Element(
        ".date-select",
        {
            placeholder : "Дата",
            allowClear : false,
            closeOnSelect : true,
            width : "100%",
            minimumResultsForSearch : Infinity,
        }
    );

    initSelect2Element(
        ".group-pillbox",
        { placeholder : "Группа"}
    );

    initSelect2Element(
        ".teacher-pillbox",
        { placeholder : "Преподаватель" }
    );

    initSelect2Element(
        ".place-pillbox",
        { placeholder : "Аудитория" }
    );

    initSelect2Element(
        ".subject-pillbox",
        { placeholder : "Предмет" }
    );
    
    initSelect2Element(
        ".kind-pillbox",
        { placeholder : "Тип предмета" }
    );

    initSelect2Element(
        ".time-slot-pillbox",
        { placeholder : "Время проведения" }
    );
});

document.onkeydown = function(e) {
    if (e.key === "Enter") {
        document.getElementById("header-form").submit();
    }
    else if (e.key === "Control") {
        update_filters_visibility();
    }
    else if (e.key === "Backspace") {
        drop_filters();
    }
};

function initSelect2Element(elementName, overrideOptions = {}) {
    const element = document.querySelector(elementName);

    if (!element) { return; }

    const options = {
        allowClear : true,
        closeOnSelect : false,
        width: "15%",
        language : {
            "noResults": function() { return "Ничего не найдено"; }
        },
        escapeMarkup: function (markup) { return markup; }
    };

    $(element).select2({ ...options, ...overrideOptions });
}

function on_date_select_change() {
    var selected_value = document.getElementById("date-select").value;

    if (selected_value != "single_date" && selected_value != "range_date") {
        document.getElementById("specified-date-container").style.display = "none";
        document.getElementById("left-date").display = "none";
        document.getElementById("right-date").display = "none";
    }
    else {
        document.getElementById("specified-date-container").style.display = "flex";
        document.getElementById("left-date").style.display = "inline";

        if (selected_value == "range_date")
            document.getElementById("right-date").style.display = "inline";
        else
            document.getElementById("right-date").style.display = "none";
    }
}

function update_filters_visibility() {
    var container = document.getElementById("addition-filters-container");
    
    if (container.style.display == "none") {
        container.style.display = "flex";
        document.getElementById("more-filters-button").innerText = "Меньше фильтров";
        document.getElementById("filters-visibility-state").value = "1";
    }
    else {
        container.style.display = "none";
        document.getElementById("more-filters-button").innerText = "Больше фильтров";
        document.getElementById("filters-visibility-state").value = "0";
    }
}

function drop_filters() {
    const pillboxes = document.querySelectorAll("select:not(.date-select)");
    pillboxes.forEach(pillbox => {
        pillbox.value = "";
        const pillboxEvent = new Event("change", { bubbles: true });
        pillbox.dispatchEvent(pillboxEvent);
    });

    const datePillbox = document.querySelector(".date-select");
    datePillbox.value = "today";
    const datePillboxEvent = new Event("change", { bubbles: true });
    datePillbox.dispatchEvent(datePillboxEvent);

    document.getElementById("left-date").value = "none";
    document.getElementById("right-date").value = "none";
    
    document.getElementById("show-calendar-checkbox").checked = true;
}