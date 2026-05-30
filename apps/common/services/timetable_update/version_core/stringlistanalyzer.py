from rapidfuzz import fuzz


class StringListAnalyzer:
    """
    Класс анализа двух наборов строк.
    При анализе для каждой строки из списка строк для анализа определяется максимально похожая
    строка из списка для сравнения. Также между этими строками вычисляется коэффициент сравнения.
    """

    def __init__(
        self,
        analyze_strings: list[str] | None = None,
        compare_strings: list[str] | None = None,
        quick_analyze: bool = True,
    ) -> None:
        """
        Выполняет сравнение двух списков строк
        :param analyze_strings: Список строк для анализа
        :param compare_strings: Список строк для сравнения
        """
        # создание переменных класса
        self.__analyze_strings: list[str] = []  # Список строк для анализа
        self.__compare_strings: list[str] = []  # Список строк для сравнения
        self.__most_similar_strings: dict[str, str] = {}
        self.__max_ratio_strings: dict[str, float] = {}
        self.__quick_analyze = quick_analyze  # Использовать быстрый анализ

        # Задание значений спискам
        if analyze_strings is not None:
            self.__analyze_strings = analyze_strings
        if compare_strings is not None:
            self.__compare_strings = compare_strings

        # Вызов метода анализа двух наборов строк
        if analyze_strings is not None and compare_strings is not None:
            self.__analyze()

    def __analyze(self) -> "StringListAnalyzer":
        """
        Выполняет сравнение двух списков строк
        :return: Текущий экземпляр класса
        """
        # Для каждой пары строк из списка анализируемых и сравниваемых строк
        for analyze_string in self.__analyze_strings:
            for compare_string in self.__compare_strings:
                ratio = self.__calculate_ratio(analyze_string, compare_string)

                # Обновить значения, если текущий коэффициент больше предыдущего
                if ratio > self.__max_ratio_strings.get(analyze_string, -1):
                    self.__max_ratio_strings[analyze_string] = ratio
                    self.__most_similar_strings[analyze_string] = compare_string

        return self

    def __calculate_ratio(self, analyze_string: str, compare_string: str) -> float:
        scorer = fuzz.QRatio if self.__quick_analyze else fuzz.ratio
        return scorer(analyze_string, compare_string) / 100

    def get_analyze_strings(self) -> list[str]:
        """
        Возвращает список строк для анализа
        :return: Список строк
        """
        # Вернуть результат
        return self.__analyze_strings

    def get_compare_strings(self) -> list[str]:
        """
        Возвращает список строк для сравнения
        :return: Список строк для сравнения
        """
        # Вернуть результат
        return self.__compare_strings

    def get_similar_string(self, string: str) -> str:
        """
        Возвращает максимально похожую строку из списка для сравнения.
        :param string: Строка из списка для анализа, для которой ищется максимально похожая строка
        :return: Строка из списка для сравнения
        """
        # Вернуть результат
        return self.__most_similar_strings.get(string, "")

    def get_ratio_for_string(self, string: str) -> float:
        """
        Возвращает максимальную степень похожести для строки из списка для анализа
        :param string: Строка из списка для анализа, для которой ищется максимальная степень похожести
        :return: Степень - это число на отрезке [0,1]
        """
        # Вернуть результат
        return self.__max_ratio_strings.get(string, 0)

    def get_max_ratio_words(self) -> list[str]:
        """
        Возвращает список слов, с максимальным коэффициентом похожести
        :return: Список слов с максимальным коэффициентом похожести
        """
        # Рассчитать максимальное значение коэффициента
        max_ratio = self.get_max_ratio()

        # Вернуть список слов с коэффициентом похожести, равный максимальному
        return self.get_strings_by_ratio(max_ratio)

    def get_strings_by_ratio(self, ratio: float, round_number: int | None = None) -> list[str]:
        """
        Возвращает список строк с заданным коэффициентом похожести
        :param ratio: Коэффициент похожести
        :param round_number: Количество знаков после запятой для округления (опционально)
        :return: Список символов
        """
        if round_number is not None:
            # Выбросить исключение, если значение округления не соответствует допустимому
            if round_number < 0:
                raise ValueError(
                    f"Round number must be greater than zero. Now round number = {round_number}."
                )
            # Иначе убедится в степени округления коэффициента похожести
            else:
                ratio = round(ratio, round_number)

        # Список строк
        result_strings = []

        # Для каждой строки
        for string, string_ratio in self.__max_ratio_strings.items():
            # Расчёт значения коэффициента с учётом округления
            new_ratio = (
                round(string_ratio, round_number) if round_number is not None else string_ratio
            )

            # Добавить строку в список, если коэффициент совпадает
            if new_ratio == ratio:
                result_strings.append(string)

        # Вернуть результат
        return result_strings

    def get_strings_by_ratio_in_range(self, min_ratio: float, max_ratio: float) -> list[str]:
        """
        Возвращает список строк с коэффициентом похожести на отрезке
        :param min_ratio: Минимальное значение коэффициента похожести
        :param max_ratio: Максимальное значение коэффициента похожести
        :return: Список строк
        """
        # Список строк
        result_strings = []

        # Для каждой строки
        for string, ratio in self.__max_ratio_strings.items():
            # Добавить строку в список, если коэффициент находится в диапазоне
            if min_ratio <= ratio <= max_ratio:
                result_strings.append(string)

        # Вернуть результат
        return result_strings

    def get_max_ratio(self) -> float:
        """
        Определяет максимальную степень похожести среди всех слов
        :return: Максимальная степень похожести
        """
        # Вернуть значение
        values = self.__max_ratio_strings.values()
        if len(values) == 0:
            return 0
        return max(values)
