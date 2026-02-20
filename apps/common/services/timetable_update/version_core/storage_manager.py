from abc import ABC
from pathlib import Path
import re

import fs
import fs.copy
from fs.memoryfs import FS
import ipdb

from timetable_project.settings import ALLOWED_HOSTS, STATIC_URL, STATIC_ROOT
from timetable.models import Resource, FileVersion, Storage


class StorageManager(ABC):
    # ------------------КОНСТРУКТОРЫ------------------- #
    def __init__(self, storage_type: str, fs_root: FS):
        """
        Инициализация объектов, необходимых для работы файлового менеджера.
        :param storage_type: Тип хранилища (описывается строкой).
        :param fs_root: Корневая файловая система.
        """
        self._fs_root = fs_root
        self._storage_type = storage_type

    # -----------------ОТКРЫТЫЕ МЕТОДЫ----------------- #
    def add_new_file_version(
        self, local_file_path: Path | str, resource: Resource, file_version: FileVersion
    ):
        """
        Добавляет новую версию файла в хранилище.
        :param local_file_path: Путь к файлу в локальном хранилище.
        :param resource: Запись базы данных с информацией о ресурсе, которому принадлежит этот файл.
        :param file_version: Запись базы данных с информацией о версии файла, которой принадлежит этот файл.
        """

        local_file_path = Path(local_file_path)

        if not local_file_path.is_file():
            raise FileNotFoundError(str(local_file_path))

        # Получить доступ к локальному хранилищу файлов
        fs_local = fs.open_fs("osfs://" + str(local_file_path.parent))

        # Получить список всех версий ресурса в порядке убывания
        file_versions = FileVersion.objects.filter(
            resource=file_version.resource
        ).order_by("-last_changed", "-timestamp")

        # Определим относительный путь к актуальной версии файла
        actual_file_path = self.__create_actual_file_path(resource, file_version)
        # Если есть предыдущая версия
        if (
            file_versions is not None
            and len(file_versions) >= 2
            and resource.derived_from is None
        ):
            # Получить предыдущую версию
            previous_file_version = file_versions[1]
            # Перевести предыдущую версию (актуальную) в архивную
            self.__make_file_version_is_archive(resource, previous_file_version)
            # Перезаписать файл с актуальной версией
            self.__rewrite_file(
                fs_local, str(local_file_path.name), self._fs_root, actual_file_path
            )
        else:
            # Создать новый файл актуальной версии
            self.__copy_file(
                fs_local, str(local_file_path.name), self._fs_root, actual_file_path
            )

        # Создать запись в базе данных с информацией об этом файле
        new_storage = Storage()
        new_storage.storage_type = self._storage_type
        new_storage.path = actual_file_path
        new_storage = self._set_storage_link(actual_file_path, new_storage)
        new_storage.file_version = file_version
        new_storage.save()

    def dell_storages_by_resource(
        self, resource: Resource, need_dell_file_versions=False
    ):
        """
        Удаляет записи с информацией о файле в этом хранилище по ресурсу.
        :param resource: Запись в базе данных содержащая информацию о ресурсе.
        :param need_dell_file_versions: Определяет необходимость удалять записи в базе данных,
        которые содержат информацию о версии файла, если те не имеют больше ссылок на файлы в хранилищах.
        """
        # Найти все версии файла
        file_versions = FileVersion.objects.filter(resource=resource)

        # Удалить файлы этого хранилища для всех версий файла этого ресурса
        for file_version in file_versions:
            # Удалить файлы
            self.dell_storages_by_file_version(file_version)

            # Удалить запись с информацией о версии файла, если это необходимо и можно сделать
            if need_dell_file_versions:
                storages = Storage.objects.filter(file_version=file_version)
                if len(storages) == 0:
                    file_version.delete()

    def get_google_storage_by_file_version(file_version: FileVersion):
        return Storage.objects.filter(
            storage_type="google drive", file_version=file_version
        ).first()

    def dell_storages_by_file_version(self, file_version: FileVersion):
        """
        Удаляет записи с информацией о файле в этом хранилище по версии файла.
        :param file_version: Запись в базе данных содержащая информацию о версии файла.
        """
        # Найти все записи с информацией о ресурсе, которые принадлежат этому ресурсу и относятся к этой версии файла
        storages = Storage.objects.filter(
            file_version=file_version, storage_type=self._storage_type
        )

        # Удалить файл для каждого хранилища и запись о нём в базе данных
        for storage in storages:
            self.dell_storages_by_file_version(storage)

    def dell_file_by_storage(self, storage: Storage):
        """
        Удаляет запись с информацией о файле в этом хранилище.
        :param storage: Запись в базе данных с информацией о файле на этом ресурсе.
        """
        # Завершить выполнение досрочно, если запись содержит информацию о файле не в этом хранилище.
        if storage.storage_type != self._storage_type:
            return False

        # Удалить файл, если он существует
        if self._fs_root.exists(storage.path):
            self._fs_root.remove(storage.path)

        # Удалить запись о хранилище
        storage.delete()
        return True

    def clear_storage(self):
        """
        Очищает всё хранилище, удаляет все записи о себе в базе данных.
        """
        # Удалить все записи в базе данных о себе
        self.__clear_storage_in_db()

        # Удалить каждый объект в корневой папке
        for path in self._fs_root.listdir("/"):
            # Удалить путь, даже если в нём есть файлы
            if self._fs_root.isdir(path):
                self._fs_root.removetree(path)
            # Удалить файл
            else:
                self._fs_root.remove(path)

    def get_storage_type(self):
        return self._storage_type

    # ----------------ПРИВАТНЫЕ МЕТОДЫ----------------- #
    def _set_storage_link(self, file_dir: str, storage: Storage):
        """
        Задаёт ссылки для файла в запись базы данных.
        :param file_dir: Путь к файлу
        :param storage: Запись базы данных.
        :return: Запись базы данных.
        """
        storage.resource_url = None
        file = (
            Path(self._fs_root.getsyspath("/"))
            .joinpath(file_dir)
            .relative_to(STATIC_ROOT)
        )
        storage.download_url = f"http://{ALLOWED_HOSTS[0]}:81/{STATIC_URL}{file}"
        return storage

    def _make_file_public(self, file_dir: str):
        """
        Делает файл публичным.
        :param file_dir: Путь к файлу.
        """
        pass

    def _make_dir_public(self, file_dir: str):
        """
        Делает папку публичной.
        :param file_dir: Путь к файлу.
        """
        pass

    # -----------------ЗАКРЫТЫЕ МЕТОДЫ----------------- #
    def __make_file_version_is_archive(
        self, resource: Resource, file_version: FileVersion
    ):
        """
        Ищет последнюю версию ресурса. Создаёт архивный файл с информацией из последней версии. Обновляет запись в базе данных.
        :param resource: Запись базы данных с информацией о ресурсе.
        :param file_version: Запись базы данных с информацией о версии файла.
        :return:
        """
        # Найти предыдущую версию, которая является актуальной
        storage = Storage.objects.filter(
            storage_type=self._storage_type, file_version=file_version
        ).first()
        if storage is None:
            return

        # Создать для версии архивный путь
        archive_path = self.__create_archive_file_path(resource, file_version)
        current_path = storage.path

        # Сохранить файл под новым названием
        self.__copy_file(self._fs_root, current_path, self._fs_root, archive_path)

        # Обновить параметры записи базы данных
        storage.path = self.__create_archive_file_path(resource, file_version)
        storage = self._set_storage_link(archive_path, storage)
        storage.save()

    def __rewrite_file(
        self,
        fs_source: FS,
        source_file_path: str,
        fs_destination: FS,
        destination_file_path: str,
        chunk_size: int = 4096,
    ):
        """
        Перезаписывает файл из одной файловой системы, файлом из другой файловой системы.
        :param fs_source: Файловая система источника.
        :param source_file_path: Путь к исходному файлу.
        :param fs_destination: Файловая система назначения.
        :param destination_file_path: Путь к целевому файлу.
        :param chunk_size: Размер буфера для чтения данных.
        """
        # Создаём пути к папкам
        fs_destination.makedirs(fs.path.dirname(destination_file_path), recreate=True)
        # Открываем файлы и делаем перезапись
        with fs_source.open(source_file_path, "rb") as source_file:
            with fs_destination.open(destination_file_path, "wb") as target_file:
                # Чтение части данных из исходного файла
                chunk = source_file.read(chunk_size)
                while chunk:
                    # Запись части данных в целевой файл
                    target_file.write(chunk)
                    # Чтение части данных из исходного файла
                    chunk = source_file.read(chunk_size)
        # Задаём файлам открытые права доступа
        self._make_file_public(destination_file_path)
        self._make_dir_public(destination_file_path)

    def __copy_file(
        self,
        fs_source: FS,
        source_file_path: str,
        fs_destination: FS,
        destination_file_path: str,
    ):
        """
        Копирует файл из одной файловой системы в другую.
        :param fs_source: Файловая система источника.
        :param source_file_path: Путь к исходному файлу.
        :param fs_destination: Файловая система назначения.
        :param destination_file_path: Путь к целевому файлу.
        """
        # Создаём путь к файлу
        fs_destination.makedirs(fs.path.dirname(destination_file_path), recreate=True)
        # Копируем файл

        fs.copy.copy_file(
            fs_source, source_file_path, fs_destination, destination_file_path
        )
        # Задаём новому файлу открытые права доступа
        self._make_file_public(destination_file_path)
        self._make_dir_public(destination_file_path)

    def __create_actual_file_path(self, resource: Resource, file_version: FileVersion):
        """
        Создаёт путь к актуальному файлу на основании записей базы данных.
        :param resource: Запись базы данных с информацией о ресурсе, которому принадлежит этот файл.
        :param file_version: Запись базы данных с информацией о версии файла, которой принадлежит этот файл.
        :return: Путь к файлу.
        """
        parent_dir = self.__get_parent_dir_path(resource)
        self._fs_root.makedirs(parent_dir, recreate=True)
        return f"{parent_dir}/{self.__get_actual_file_path(resource, file_version)}"

    def __create_archive_file_path(self, resource: Resource, file_version: FileVersion):
        """
        Создаёт путь к архивному файлу на основании записей базы данных.
        :param resource: Запись базы данных с информацией о ресурсе, которому принадлежит этот файл.
        :param file_version: Запись базы данных с информацией о версии файла, которой принадлежит этот файл.
        :return: Путь к файлу.
        """
        new_dir = self.__get_parent_dir_path(resource)
        self._fs_root.makedirs(new_dir, recreate=True)
        return new_dir + "/" + self.__get_archive_file_name(resource, file_version)

    @classmethod
    def __get_actual_file_path(cls, resource: Resource, file_version: FileVersion):
        """
        Возвращает путь к актуальному файлу на основании записей базы данных.
        :param resource: Запись базы данных с информацией о ресурсе, которому принадлежит этот файл.
        :param file_version: Запись базы данных с информацией о версии файла, которой принадлежит этот файл.
        :return: Путь.
        """
        return resource.name + file_version.mimetype

    @classmethod
    def __get_archive_file_name(cls, resource: Resource, file_version: FileVersion):
        """
        Возвращает путь к архивному файлу на основании записей базы данных.
        :param resource: Запись базы данных с информацией о ресурсе, которому принадлежит этот файл.
        :param file_version: Запись базы данных с информацией о версии файла, которой принадлежит этот файл.
        :return: Путь.
        """
        return (
            resource.name
            + " "
            + file_version.timestamp.strftime("%Y-%m-%d_%H-%M-%S")
            + file_version.mimetype
        )

    @classmethod
    def __get_parent_dir_path(cls, resource: Resource):
        """
        Возвращает путь к родительской директории для файла.
        :param resource:
        :return:
        """
        return (Path(resource.path) / resource.name).as_posix()

    def __clear_storage_in_db(self):
        """
        Удалить все записи, содержащие информацию об этом хранилище.
        """
        storages = Storage.objects.filter(storage_type=self._storage_type)
        for storage in storages:
            storage.delete()
