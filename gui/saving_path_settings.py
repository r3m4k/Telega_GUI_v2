# -*- coding: utf-8 -*-
"""Модуль для настройки пути сохранения данных в GUI.

Содержит класс `SavingPathSetting`, который управляет виджетами
`QLineEdit` и `QToolButton` для выбора директории сохранения,
а также пользовательское исключение `InvalidPathError` для обработки
ошибок, связанных с некорректным путём.
"""

# System imports
from pathlib import Path

# External imports
from PyQt5.QtWidgets import QFileDialog, QLineEdit, QToolButton

# User imports
from config import config

##########################################################

class InvalidPathError(Exception):
    """Исключение, возникающее при некорректном пути сохранения."""
    pass

# --------------------------------------------------------

class SavingPathSetting:
    """Управление выбором и проверкой пути сохранения.

    Класс связывает поле ввода (`QLineEdit`) и кнопку (`QToolButton`)
    для выбора директории через диалог. При инициализации загружает
    сохранённый путь из глобального конфига (`config.save_dir`).
    Предоставляет методы для блокировки/разблокировки элементов управления,
    получения проверенного пути и сохранения текущего пути в конфиг.

    Args:
        saving_path_edit (QLineEdit): Поле для отображения и ввода пути.
        choose_saving_path_button (QToolButton): Кнопка для открытия диалога выбора папки.
    """

    def __init__(self, saving_path_edit: QLineEdit, choose_saving_path_button: QToolButton):
        super().__init__()

        if not isinstance(saving_path_edit, QLineEdit) or not isinstance(choose_saving_path_button, QToolButton):
            raise TypeError("Ожидаются QLineEdit и QToolButton\n"
                            f"Получены: {type(saving_path_edit)} и {type(choose_saving_path_button)}")

        self._saving_path_edit: QLineEdit = saving_path_edit
        self._choose_saving_path_button: QToolButton = choose_saving_path_button

        self._load_from_config()
        self._choose_saving_path_button.clicked.connect(self._select_path)

    def get_saving_path(self) -> Path:
        """Возвращает выбранный путь как объект Path после проверки.

        Returns:
            Path: Абсолютный путь к директории.

        Raises:
            InvalidPathError: если путь не задан, не существует или не является директорией.
        """
        text = self._saving_path_edit.text().strip()
        if not text:
            raise InvalidPathError("Укажите путь сохранения!")

        path = Path(text).resolve()  # преобразуем в абсолютный путь

        if not path.exists():
            raise InvalidPathError(f"Указанный путь {path} не существует!")
        if not path.is_dir():
            raise InvalidPathError(f"Указанный путь {path} не является директорией!")

        return path

    def save_config(self) -> None:
        """Сохраняет текущий путь в объект конфигурации.

        Обновляет поле `config.save_dir` значением, взятым из поля ввода,
        преобразованным в абсолютный путь. Сохранение в файл не производится.
        """
        current_path = Path(self._saving_path_edit.text().strip()).resolve()
        if current_path.exists() and current_path.is_dir():
            config.save_dir = current_path
            config.save()

    def lock_input(self) -> None:
        """Блокирует редактирование пути и кнопку выбора."""
        self._saving_path_edit.setEnabled(False)
        self._choose_saving_path_button.setEnabled(False)

    def unlock_input(self) -> None:
        """Разблокирует редактирование пути и кнопку выбора."""
        self._saving_path_edit.setEnabled(True)
        self._choose_saving_path_button.setEnabled(True)

    def _load_from_config(self) -> None:
        """Загрузка пути сохранения из конфига."""
        if config.save_dir:
            self._saving_path_edit.setText(str(config.save_dir.resolve()))

    def _select_path(self) -> None:
        """Выбор пути сохранения через диалоговое окно."""

        # Текущий путь (для начальной директории диалога)
        current_path = self._saving_path_edit.text() or str(Path.home())

        # Используем поле как родительский виджет для правильного позиционирования
        directory = QFileDialog.getExistingDirectory(
            self._saving_path_edit,
            "Выберите директорию сохранения",
            current_path,
            QFileDialog.ShowDirsOnly
        )
        if directory:
            self._saving_path_edit.setText(directory)
