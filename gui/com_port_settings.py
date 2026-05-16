# -*- coding: utf-8 -*-
"""Модуль для настройки COM-порта в GUI.

Содержит класс `ComPortSettings`, который управляет виджетами для выбора
COM-порта, отображения информации о порте, обновления списка портов и
выбора скорости передачи данных. Также предоставляет пользовательское
исключение `ComPortError` для обработки ошибок, связанных с настройкой порта.
"""

# System imports
from typing import TypedDict
from pprint import pformat
from pathlib import Path

# External imports
from PyQt5.QtCore import QObject
from PyQt5.QtWidgets import QRadioButton, QComboBox, QPushButton, QMessageBox, QButtonGroup
from PyQt5.QtGui import QIcon

# User imports
from config import config
from byte_source.com_port import get_ComPorts

##########################################################

class ComPortSettingsError(Exception):
    """Исключение, возникающее при неправильной настройке COM порта."""
    pass

# --------------------------------------------------------

class RadioButtonsDict(TypedDict):
    """Тип для словаря радиокнопок выбора скорости.

    Ключи соответствуют именам кнопок, значения должны быть объектами
    `QRadioButton`. В константе `BAUDRATE_MAP` этот же тип используется
    для хранения числовых значений скоростей.
    """
    rb_921600: QRadioButton | int
    rb_460800: QRadioButton | int
    rb_230400: QRadioButton | int
    rb_115200: QRadioButton | int
    rb_57600: QRadioButton | int
    rb_9600: QRadioButton | int

# --------------------------------------------------------

# Словарь соответствия имён кнопок числовым значениям скорости
BAUDRATE_MAP = RadioButtonsDict(
    rb_921600 = 921600,
    rb_460800 = 460800,
    rb_230400 = 230400,
    rb_115200 = 115200,
    rb_57600 = 57600,
    rb_9600 = 9600
)

# --------------------------------------------------------

class ComPortSettings(QObject):
    """Управление настройками COM-порта.

    Класс связывает выпадающий список портов (`QComboBox`), кнопки для
    обновления списка и отображения информации, а также группу радиокнопок
    для выбора скорости. При инициализации загружает сохранённые настройки
    из глобального конфига (`config.com_port`). Предоставляет методы для
    получения выбранного порта и скорости, а также для сохранения текущих
    настроек в конфиг.

    Args:
        com_port_combo_box (QComboBox): Выпадающий список доступных COM-портов.
        com_port_info_button (QPushButton): Кнопка для отображения информации
            о выбранном порте.
        update_com_ports_button (QPushButton): Кнопка для обновления списка портов.
        radio_buttons (RadioButtonsDict): Словарь радиокнопок для выбора скорости.
            Ключи должны строго соответствовать `BAUDRATE_MAP.keys()`.

    Raises:
        TypeError: Если переданные виджеты имеют неверный тип.
        KeyError: Если набор ключей в `radio_buttons` не совпадает с ожидаемым.
    """

    def __init__(self,
                 com_port_combo_box: QComboBox,
                 com_port_info_button: QPushButton,
                 update_com_ports_button: QPushButton,
                 radio_buttons: RadioButtonsDict):
        # -------------------------------------------------------------
        super().__init__()

        # Проверка типов переданных параметров
        if not isinstance(com_port_combo_box, QComboBox):
            raise TypeError(f"Ожидается com_port_combo_box: QComboBox, получен {type(com_port_combo_box)}")
        if not isinstance(com_port_info_button, QPushButton):
            raise TypeError(f"Ожидается com_port_info_button: QPushButton, получен {type(com_port_info_button)}")
        if not isinstance(update_com_ports_button, QPushButton):
            raise TypeError(f"Ожидается update_com_ports_button: QPushButton, получен {type(update_com_ports_button)}")

        # Проверка наличия всех ожидаемых ключей в словаре кнопок
        expected_keys = set(BAUDRATE_MAP.keys())
        provided_keys = set(radio_buttons.keys())
        if expected_keys != provided_keys:
            raise KeyError(f"Ожидались ключи {pformat(expected_keys)}, получены {pformat(provided_keys)}")

        for key, rb in radio_buttons.items():
            if not isinstance(rb, QRadioButton):
                raise TypeError(f"Элемент '{key}' должен быть QRadioButton, получен {type(rb)}")

        # -------------------------------------------------------------

        self._com_port_combo_box: QComboBox = com_port_combo_box
        self._com_port_info_button: QPushButton = com_port_info_button
        self._update_com_ports_button: QPushButton = update_com_ports_button

        self._com_ports: dict[str, dict[str, str]] = {}     # информация о доступных портах
        self._current_port: str = '-----'                   # текущий выбранный порт (по умолчанию заглушка)
        self._current_baudrate: int = 0                     # текущая выбранная скорость работы порта

        # Группа для радиокнопок (обеспечивает взаимоисключающий выбор)
        self._baudrate_group = QButtonGroup(self)
        for key, rb in radio_buttons.items():
            # Присваиваем ID, равный значению скорости (или можно любой другой уникальный)
            self._baudrate_group.addButton(rb, BAUDRATE_MAP[key])

        self._init_UI()

    def get_port_name(self) -> str:
        """Возвращает имя выбранного порта.

        Raises:
            ComPortError: если имя порта не задано.
        """
        if self._com_port_combo_box.currentText() and self._com_port_combo_box.currentText() != '-----':
            return self._com_port_combo_box.currentText()
        raise ComPortSettingsError("Выберите порт для подключения!")

    def get_baudrate(self) -> int:
        """Возвращает выбранную скорость.

        Raises:
            ComPortError: если скорость работы порта не выбрана.
        """
        if self._current_baudrate:
            return  self._current_baudrate
        raise ComPortSettingsError("Не задана скорость работы порта!")

    def lock_input(self) -> None:
        """Блокирует все элементы управления настройками COM-порта."""
        self._com_port_combo_box.setEnabled(False)
        self._update_com_ports_button.setEnabled(False)
        for btn in self._baudrate_group.buttons():
            btn.setEnabled(False)

    def unlock_input(self) -> None:
        """Разблокирует все элементы управления настройками COM-порта."""
        self._com_port_combo_box.setEnabled(True)
        self._update_com_ports_button.setEnabled(True)
        for btn in self._baudrate_group.buttons():
            btn.setEnabled(True)

    def save_config(self) -> None:
        """Сохраняет текущие настройки порта и скорости в глобальный конфиг."""

        if self._current_port != '-----':
            config.com_port.name = self._current_port
            config.com_port.desc = self._com_ports[self._current_port]["desc"]
            config.com_port.hwid = self._com_ports[self._current_port]["hwid"]
        if self._current_baudrate:
            config.com_port.baudrate = self._current_baudrate
        config.save()

    def _init_UI(self) -> None:
        """Инициализация интерфейса: установка иконки, подключение сигналов,
        первичное обновление списка портов и загрузка настроек из конфига.
        """
        # Поместим на кнопку обновления соответствующую иконку
        icon_path = Path(__file__).parent / "ui" / "update_logo.png"
        self._update_com_ports_button.setIcon(QIcon(str(icon_path)))

        self._connect_signals()
        self._update_com_ports()
        self._load_from_config()

    def _connect_signals(self) -> None:
        """Подключает сигналы виджетов к внутренним слотам."""
        self._com_port_combo_box.currentTextChanged.connect(self._on_port_changed)
        self._com_port_info_button.clicked.connect(self._show_port_info)
        self._baudrate_group.idToggled.connect(self._on_baudrate_toggled)
        self._update_com_ports_button.clicked.connect(self._update_com_ports)

    def _load_from_config(self) -> None:
        """Загружает сохранённые настройки из конфига и применяет их.

        - Восстанавливает порт по совпадению `hwid` (если такой порт есть в текущем списке).
        - Восстанавливает скорость, устанавливая соответствующую радиокнопку.
        """
        # Зададим порт по умолчанию, если hwid одного из порта совпадает с config.com_port.hwid
        for port in self._com_ports.keys():
            if config.com_port.hwid:
                if self._com_ports[port]["hwid"] == config.com_port.hwid:
                    self._com_port_combo_box.setCurrentIndex(list(self._com_ports.keys()).index(port))

        # Зададим скорость работы порта из конфига
        saved_baudrate = config.com_port.baudrate
        if saved_baudrate:
            button = self._baudrate_group.button(saved_baudrate)
            if button:
                button.setChecked(True)
                self._current_baudrate = saved_baudrate

    def _update_com_ports(self) -> None:
        """Обновляет список доступных COM-портов.

        Получает актуальный список через `get_ComPorts()`, добавляет фиктивный
        элемент '-----' в начало и заполняет комбобокс.
        """
        self._com_ports = (
                {'-----': {"desc": "Здесь будет отображаться дескриптор выбранного COM порта",
                           "hwid": "Здесь будет отображаться hwid выбранного COM порта"}} | get_ComPorts()
        )
        self._com_port_combo_box.clear()
        self._com_port_combo_box.addItems(self._com_ports.keys())

    def _show_port_info(self) -> None:
        """Отображает диалоговое окно с информацией о выбранном порте."""
        QMessageBox.information(None, "Информация о выбранном порте",
                                f"Выбранный порт: {self._current_port}\n"
                                f"| desc: {self._com_ports[self._current_port]['desc']}\n"
                                f"| hwid: {self._com_ports[self._current_port]['hwid']}\n")

    def _on_port_changed(self, port_name: str) -> None:
        """Слот, вызываемый при изменении выбранного порта в комбобоксе."""
        self._current_port = port_name

    def _on_baudrate_toggled(self, button_id: int, checked: bool):
        """Слот, вызываемый при переключении радиокнопки скорости.

        Обновляет `_current_baudrate` только при выборе кнопки (checked=True).
        """
        if checked:
            self._current_baudrate = button_id