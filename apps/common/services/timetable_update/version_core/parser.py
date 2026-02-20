import logging
import re

import requests
from bs4 import BeautifulSoup

from .file_data import FileData

# Создаем логгер для текущего модуля
logger = logging.getLogger(__name__)


class WebParser:
    """
    Класс занимается парсингом сайта
    """

    # Текст в поле время последнего обновления, если время не было найдено
    __TEXT_NO_LAST_UPDATE_TIME = "Неизвестно"

    class FileClass:
        """
        Содержит информацию о файле
        """

        path: str = ""  # Путь к файлу
        name: str = ""  # Имя файла
        link: str = ""  # Ссылка на скачивание файла
        last_update: str = ""  # Время последнего обновления файла

    @staticmethod
    def get_files_from_webpage(web_link: str, current_path: str = "") -> list[FileData]:
        """
        Ищет на странице и в её дочерних страницах все файлы
        :param web_link: Ссылка на страницу
        :param current_path: Текущий путь к файлу
        :return: Список всех найденных файлов
        """
        # Контейнер файлов
        files = []

        # Пытаемся получить основной контент страницы
        try:
            content = WebParser.__get_page_content(web_link)
        except Exception as e:
            logger.error(
                f"Error in get_files_from_webpage for URL {web_link}: {e}",
                exc_info=True,
            )
            return files

        header3_text = ""  # Заголовок 3 уровня
        header4_text = ""  # Заголовок 4 уровня

        # Проходим по элементам контента
        for element in content.descendants:
            # Проверяем заголовок уровня 3
            if element.name == "h3":
                # Запоминаем заголовок 3 уровня
                header3_text = element.get_text(strip=True)

                # Сбрасываем header4 при нахождении нового header3
                header4_text = ""

            # Проверяем заголовок уровня 4
            elif element.name == "h4":
                # Запоминаем заголовок 4 уровня
                header4_text = element.get_text(strip=True)

            # Проверяем список
            elif element.name == "ul":
                # Формируем полный путь
                full_path = WebParser.__add_to_path_some_elements(
                    current_path, [header3_text, header4_text]
                )

                # Анализируем все гиперссылки
                for li in element.find_all("li"):
                    files += WebParser.__find_files_from_li(li, web_link, full_path)

        # Логируем количество найденных файлов
        logger.info(f"Found {len(files)} files from webpage: {web_link}")

        # Возвращаем список всех файлов
        return files

    @classmethod
    def __find_files_from_li(cls, li, web_url, current_path):
        """
        Получает все файлы из элемента <li>
        :param li: Элемента <li>
        :param web_url: Ссылка на текущую страницу, на которой размещён этот элемент
        :param current_path: Текущий путь к файлам
        :return: Список файлов, найденных по ссылке
        """
        files = []
        link_tag = li.find("a", href=True)
        if link_tag:
            # Получаем имя ссылки
            link_name = link_tag.text.strip()
            # Получаем URL ссылки
            link_url = requests.compat.urljoin(web_url, link_tag["href"])

            # Проверяем, что ссылка ведёт на файл
            if cls.is_file_with_extension(link_url, [".xls", ".xlsx", ".doc", ".docx"]):

                # Добавляем новую директорию в путь
                current_path = cls.__add_to_path(current_path, link_name, True)

                # Извлекаем дату обновления, если она есть
                last_update = cls.__get_update_time_from_text(li.text)

                # Создаем объект файла и добавляем в список
                file_data = FileData(current_path, link_url, last_update)

                logger.debug(
                    f"Found file - Path: {current_path}, URL: {link_url}, Last update: {last_update}"
                )

                files.append(file_data)

            else:
                # Добавляем новую директорию в путь
                current_path = cls.__add_to_path(current_path, link_name)

                # Логируем переход по ссылке для отладки
                logger.debug(f"Following link: {link_name} -> {link_url}")

                # Добавляем в список все файлы, которые сможем найти на веб странице по этой ссылке
                files += cls.get_files_from_webpage(link_url, current_path)

        # Вернуть список файлов
        return files

    @staticmethod
    def __get_page_content(url: str):
        """
        Получает основной контент с Web страницы
        :param url: ссылка Web страницы
        :return: Основной контент страницы
        """
        # Получение web страницы
        response = requests.get(url)
        if response.status_code != 200:
            raise Exception(f"Error opening web page. URL: {url}")

        # Распарсить HTML страницу сайта
        response.encoding = "utf-8"
        soup = BeautifulSoup(response.text, "html.parser")

        # Получение основного контента на странице
        content_wrapper = soup.find(class_="content-wrapper")
        if not content_wrapper:
            raise Exception(f"Can't find main content on web page. URL: {url}")

        # Логируем успешное получение контента
        logger.debug(f"Successfully retrieved content from: {url}")

        # Вернуть основной контент
        return content_wrapper

    @staticmethod
    def __get_update_time_from_text(text, error_text=__TEXT_NO_LAST_UPDATE_TIME):
        """
        Ищет время в строке
        :param text: Строка с временем
        :param error_text: Сообщение в случае, если время не было найдено
        :return: Строка
        """
        last_update_match = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", text)
        return last_update_match.group(0) if last_update_match else error_text

    @staticmethod
    def __add_to_path_some_elements(path, elements: list, is_file=False):
        """
        Добавляет к уже существующему пути дополнительные пути
        :param path: Изначальный путь
        :param elements: Список элементов
        :param is_file: Последний элемент является файлом, символ '/' в конце строки не нужен
        :return: Дополненный путь
        """
        result_path = path
        list_length = len(elements)
        for i in range(list_length):
            result_path = WebParser.__add_to_path(
                result_path, elements[i], i + 1 >= list_length and is_file
            )
        return result_path

    @staticmethod
    def __add_to_path(path, element: str, is_file=False):
        """
        Добавляет элемент к пути
        :param path: Изначальный путь
        :param element: Следующий элемент в пути
        :param is_file: Элемент является файлом, символ '/' в конце строки не нужен
        :return: Дополненный путь
        """
        if element != "":
            path += element
            if not is_file:
                path += "/"
        return path

    @staticmethod
    def is_file_with_extension(file_path, extensions):
        """
        Проверяет соответствие файла одному из расширений в списке
        :param file_path: Путь к файлу
        :param extensions: Список доступных разширений
        :return: Соответствие файла расширению
        """
        for extension in extensions:
            if file_path.endswith(extension):
                return True
        return False
