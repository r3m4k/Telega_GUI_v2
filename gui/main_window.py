# System imports
import logging
from pathlib import Path

# External imports
from abc import ABC, abstractmethod
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QMainWindow, QTextEdit, QToolButton,
    QPushButton, QApplication, QMessageBox,
    QComboBox, QLineEdit
)
from PyQt5.uic import loadUi
from PyQt5.QtGui import QIcon

# User imports
from logger import AppLogger
from app_config import AppConfig, config_path
from gui.saving_path_settings import SavingParams, InvalidPathError, InvalidTemplateFilenameError
from gui.com_port_settings import ComPortSettings, ComPortSettingsError
from gui.com_port_reader import ComPortReader
from gui.data_storage import DataStorage

##########################################################

class ProgramStage(ABC):
    """
    Класс для описания логики отработки нажатия кнопок пользователем
    при различных стадиях программы.
    Реализует паттерн "Состояние" (State)
    """
    def __init__(self, main_window: 'MainWindow'):
        self._main_window = main_window

    @abstractmethod
    def apply_settings(self) -> None:
        """ Сохранение настроек com порта и параметров сохранения """
        ...

    @abstractmethod
    def start_calibration(self) -> None:
        """ Запуск калибровки датчиков """
        ...

    @abstractmethod
    def start_static_init(self) -> None:
        """ Запуск сбора статического буфера """
        ...

    @abstractmethod
    def start_measuring(self) -> None:
        """ Запуск сбора данных """
        ...

    @abstractmethod
    def stop_measuring(self) -> None:
        """ Завершение сбора данных """
        ...

# =============================================================

class MainWindow(QMainWindow):
    _main_window_path: Path = Path(__file__).parent / "ui" / "main_window.ui"
    _app_icon_path: Path = Path(__file__).parent / "ui" / "telega.png"
    _logger: logging.Logger
    _app_config: AppConfig

    # =============================================================
    # ===================== Внутренние классы =====================
    # ============== для описания состояний программы =============
    # =============================================================

    class SettingStage(ProgramStage):
        """ Ожидание настроек сохранения и параметров порта """

        def apply_settings(self) -> None:
            """ Сохранение настроек com порта и параметров сохранения """
            try:
                saving_path = self._main_window._saving_params.get_saving_path()
                template_filename = self._main_window._saving_params.get_template_filename()
                com_port_name = self._main_window._com_port_settings.get_port_name()

                # Применим полученные параметры и заблокируем их изменение
                self._main_window.apply_settings(saving_path, template_filename, com_port_name)
                self._main_window._saving_params.lock_input()
                self._main_window._com_port_settings.lock_input()
                self._main_window._apply_settings_button.setEnabled(False)

            except (InvalidPathError, InvalidTemplateFilenameError, ComPortSettingsError) as err:
                QMessageBox.critical(self._main_window, 'Ошибка задания параметров!', f'{err}')

        def start_calibration(self) -> None:
            """ Запуск калибровки датчиков """
            QMessageBox.warning(self._main_window,
                                'Ошибка начала калибровки',
                                'Для начала задайте настройки com порта и параметры сохранения')

        def start_static_init(self) -> None:
            """ Запуск сбора статического буфера """
            QMessageBox.warning(self._main_window,
                                'Ошибка начала набора статического буфера',
                                'Для начала задайте настройки com порта и параметры сохранения')

        def start_measuring(self) -> None:
            """ Запуск сбора данных """
            QMessageBox.warning(self._main_window,
                                'Ошибка начала сбора данных',
                                'Для начала задайте настройки com порта и параметры сохранения')

        def stop_measuring(self) -> None:
            """ Завершение сбора данных """
            QMessageBox.warning(self._main_window,
                                'Ошибка завершения сбора данных',
                                'Для начала задайте настройки com порта и параметры сохранения')

    # -------------------------------------------------------------

    class CalibrationState(ProgramStage):
        """ Ожидание настроек сохранения и параметров порта """
        def __init__(self, main_window: 'MainWindow'):
            super().__init__(main_window)
            self.calibration_start_flag: bool = False

        def apply_settings(self) -> None:
            """ Сохранение настроек com порта и параметров сохранения """
            QMessageBox.warning(self._main_window,
                                'Ошибка изменения параметров сохранения',
                                'Параметры сохранения и настройки com порта '
                                'не могут быть изменены во время работы программы')

        def start_calibration(self) -> None:
            """ Запуск калибровки датчиков """
            if not self.calibration_start_flag:
                self._main_window._com_port_reader.start_calibration()
                self.calibration_start_flag = True
            else:
                QMessageBox.warning(self._main_window,
                                    'Ошибка начала калибровки',
                                    'Калибровка датчиков уже запущена')

        def start_static_init(self) -> None:
            """ Запуск сбора статического буфера """
            QMessageBox.warning(self._main_window,
                                'Ошибка начала набора статического буфера',
                                'Необходимо провести калибровку датчиков!')

        def start_measuring(self) -> None:
            """ Запуск сбора данных """
            QMessageBox.warning(self._main_window,
                                'Ошибка начала сбора данных',
                                'Необходимо провести калибровку датчиков!')

        def stop_measuring(self) -> None:
            """ Завершение сбора данных """
            QMessageBox.warning(self._main_window,
                                'Ошибка завершения сбора данных',
                                'Необходимо провести калибровку датчиков!')

    # -------------------------------------------------------------

    class StaticInitState(ProgramStage):
        """ Ожидание настроек сохранения и параметров порта """

        def apply_settings(self) -> None:
            """ Сохранение настроек com порта и параметров сохранения """
            self._main_window.apply_settings()

        def start_calibration(self) -> None:
            """ Запуск калибровки датчиков """
            QMessageBox.warning(self._main_window,
                                'Ошибка начала калибровки',
                                'Для начала задайте настройки com порта и параметры сохранения')

        def start_static_init(self) -> None:
            """ Запуск сбора статического буфера """
            QMessageBox.warning(self._main_window,
                                'Ошибка начала набора статического буфера',
                                'Для начала задайте настройки com порта и параметры сохранения')

        def start_measuring(self) -> None:
            """ Запуск сбора данных """
            QMessageBox.warning(self._main_window,
                                'Ошибка начала сбора данных',
                                'Для начала задайте настройки com порта и параметры сохранения')

        def stop_measuring(self) -> None:
            """ Завершение сбора данных """
            QMessageBox.warning(self._main_window,
                                'Ошибка завершения сбора данных',
                                'Для начала задайте настройки com порта и параметры сохранения')

    # -------------------------------------------------------------

    class ReadyForMeasurementState(ProgramStage):
        """ Ожидание настроек сохранения и параметров порта """

        def apply_settings(self) -> None:
            """ Сохранение настроек com порта и параметров сохранения """
            self._main_window.apply_settings()

        def start_calibration(self) -> None:
            """ Запуск калибровки датчиков """
            QMessageBox.warning(self._main_window,
                                'Ошибка начала калибровки',
                                'Для начала задайте настройки com порта и параметры сохранения')

        def start_static_init(self) -> None:
            """ Запуск сбора статического буфера """
            QMessageBox.warning(self._main_window,
                                'Ошибка начала набора статического буфера',
                                'Для начала задайте настройки com порта и параметры сохранения')

        def start_measuring(self) -> None:
            """ Запуск сбора данных """
            QMessageBox.warning(self._main_window,
                                'Ошибка начала сбора данных',
                                'Для начала задайте настройки com порта и параметры сохранения')

        def stop_measuring(self) -> None:
            """ Завершение сбора данных """
            QMessageBox.warning(self._main_window,
                                'Ошибка завершения сбора данных',
                                'Для начала задайте настройки com порта и параметры сохранения')

    # -------------------------------------------------------------

    class MeasuringState(ProgramStage):
        """ Ожидание настроек сохранения и параметров порта """

        def apply_settings(self) -> None:
            """ Сохранение настроек com порта и параметров сохранения """
            self._main_window.apply_settings()

        def start_calibration(self) -> None:
            """ Запуск калибровки датчиков """
            QMessageBox.warning(self._main_window,
                                'Ошибка начала калибровки',
                                'Для начала задайте настройки com порта и параметры сохранения')

        def start_static_init(self) -> None:
            """ Запуск сбора статического буфера """
            QMessageBox.warning(self._main_window,
                                'Ошибка начала набора статического буфера',
                                'Для начала задайте настройки com порта и параметры сохранения')

        def start_measuring(self) -> None:
            """ Запуск сбора данных """
            QMessageBox.warning(self._main_window,
                                'Ошибка начала сбора данных',
                                'Для начала задайте настройки com порта и параметры сохранения')

        def stop_measuring(self) -> None:
            """ Завершение сбора данных """
            QMessageBox.warning(self._main_window,
                                'Ошибка завершения сбора данных',
                                'Для начала задайте настройки com порта и параметры сохранения')

    # =============================================================

    def __init__(self):
        super().__init__(parent=None)

        # Создадим конфигурацию приложения
        self._app_config = AppConfig.load(config_path)

        # Зададим логгер приложения
        self._logger = AppLogger(self._app_config.logger_config).get_child_logger("MainWindow")

        # Загрузим разметку страницы
        loadUi(self._main_window_path, self)

        # Зададим название окна и иконку
        self.setWindowTitle('Путеизмерительная тележка')
        self.setWindowIcon(QIcon(str(self._app_icon_path)))

        # Зададим стадии программы
        self._setting_stage: MainWindow.SettingStage = self.SettingStage(self)
        self._calibration_stage: MainWindow.CalibrationState = self.CalibrationState(self)
        self._static_init : MainWindow.StaticInitState = self.StaticInitState(self)
        self._ready_for_measuring_stage : MainWindow.ReadyForMeasurementState = self.ReadyForMeasurementState(self)
        self._measuring_stage : MainWindow.MeasuringState = self.MeasuringState(self)

        self._current_stage: ProgramStage = self._setting_stage

        # ------------------------------
        # Кнопка сохранения настроек com порта и параметров сохранения
        self._apply_settings_button: QPushButton = self.findChild(QPushButton, "ApplySettingsButton")

        # Кнопки управления измерениями
        self._start_calibration_button: QPushButton = self.findChild(QPushButton, "StartCalibrationButton")
        self._start_static_init_button: QPushButton = self.findChild(QPushButton, "StartStaticInitButton")
        self._start_measuring_button: QPushButton = self.findChild(QPushButton, "StartMeasuringButton")
        self._stop_measuring_button:  QPushButton = self.findChild(QPushButton, "StopMeasuringButton")
        # ------------------------------
        self._msg_text_edit: QTextEdit = self.findChild(QTextEdit, "MessagesTextEdit")
        # ------------------------------
        self._saving_params = SavingParams(
            app_config=self._app_config,
            saving_path_edit = self.findChild(QLineEdit, "SavingPathEdit"),
            choose_saving_path_button = self.findChild(QToolButton, "ChooseSavingPathButton"),
            template_filename_edit = self.findChild(QLineEdit, "TemplateFilenameEdit"),
            template_info_button = self.findChild(QPushButton, "TemplateInfoButton")
        )
        # ------------------------------
        self._com_port_settings = ComPortSettings(
            app_config=self._app_config,
            com_port_combo_box = self.findChild(QComboBox, "ComPortComboBox"),
            com_port_info_button = self.findChild(QPushButton, "ComPortInfoButton"),
            update_com_ports_button = self.findChild(QPushButton, "UpdateComPortsButton")
        )
        # ------------------------------
        self._com_port_reader: ComPortReader = ComPortReader()
        # ------------------------------
        self._data_storage = DataStorage()
        # ------------------------------
        # Настроим интерфейс
        if not self._check_UI():
            self._app_logger.error("Неправильно настроен main_window!")
            QMessageBox.critical(self, "Ошибка", "Неправильно настроен main_window")
            QApplication.quit()
            exit(10)

        self._init_UI()
        # ------------------------------

    def closeEvent(self, event)-> None:
        """ Дополнительная логика перед закрытием окна """
        self.hide()
        event.accept()
        self._stop_measuring()
        QTimer.singleShot(1000, self._quit_app)

    def _quit_app(self) -> None:
        """ Метод для завершения работы программы """
        if not self._com_port_reader.is_active:
            self._app_logger.info('Корректное завершение работы приложения')
        else:
            self._app_logger.warning('Принудительное завершение приложения до полной остановки ComPortReader')
        QApplication.quit()

    def _init_UI(self) -> None:
        # Подключим нажатие кнопок и другие сигналы к соответствующим функциям-обработчикам
        self._start_calibration_button.clicked.connect(lambda: self._current_stage.start_calibration())
        self._start_static_init_button.clicked.connect(lambda: self._current_stage.start_static_init())
        self._start_measuring_button.clicked.connect(lambda: self._current_stage.start_measuring())
        self._stop_measuring_button.clicked.connect(lambda: self._current_stage.stop_measuring())

        self._com_port_reader.data_received.connect(lambda package: self._data_storage.add_package(package))
        self._com_port_reader.error_occurred.connect(self._error_handler)

    def _check_UI(self) -> bool:
        return (isinstance(self._start_measuring_button,    QPushButton) and
                isinstance(self._stop_measuring_button,     QPushButton) and
                isinstance(self._start_calibration_button,  QPushButton) and
                isinstance(self._start_static_init_button,  QPushButton) and
                isinstance(self._apply_settings_button,     QPushButton) and
                isinstance(self._msg_text_edit, QTextEdit))

    # =============================================================
    # =================== Внутренняя логика =======================
    # =============================================================

    def apply_settings(self,
                       saving_path: Path,
                       template_filename: str,
                       com_port_name: str) -> None:
        ...

    def change_settings(self) -> None:
        ...

    def _error_handler(self, error_info: str) -> None:
        QMessageBox.critical(self, "Ошибка выполнения!", error_info)
        self._com_port_settings.unlock_input()
        self._saving_path_setting.unlock_input()
        self._current_stage = self._setting_stage

    # =============================================================
    # =============== Методы для обработки сигналов ===============
    # =============================================================

    def _handshake_failed(self) -> None:
        ...
