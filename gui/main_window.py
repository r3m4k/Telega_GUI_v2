# System imports
from pathlib import Path

# External imports
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QMainWindow, QTextEdit, QToolButton,
    QPushButton, QApplication, QMessageBox,
    QComboBox, QRadioButton, QLineEdit
)
from PyQt5.uic import loadUi

# User imports
from config import config
from app_logger import app_logger
from gui.saving_path_settings import SavingPathSetting, InvalidPathError
from gui.com_port_settings import ComPortSettings, ComPortSettingsError, RadioButtonsDict
from gui.com_port_reader import ComPortReader, ComPortReadError
from gui.plotting_widget import PlottingWidget
from ADCAnalysis import TorqueCalculation, TorqueCalculationError
from decoding.hx711_decoding import HX711Data

##########################################################

class MainWindow(QMainWindow):
    _main_window_path: Path = Path(__file__).parent / "ui" / "main_window.ui"

    def __init__(self):
        super().__init__(parent=None)

        # Загрузим разметку страницы
        loadUi(self._main_window_path, self)

        # Зададим название окна и устанавливаем полноэкранный режим
        self.setWindowTitle('Динамометрический стенд')
        self.setWindowState(Qt.WindowState(Qt.WindowMaximized))

        # ------------------------------
        self._start_button: QPushButton = self.findChild(QPushButton, "StartButton")
        self._stop_button: QPushButton = self.findChild(QPushButton, "StopButton")
        # ------------------------------
        self._msg_text_edit: QTextEdit = self.findChild(QTextEdit, "MessagesTextEdit")
        # ------------------------------
        self._saving_path_setting = SavingPathSetting(
            saving_path_edit = self.findChild(QLineEdit, "SavingPathEdit"),
            choose_saving_path_button = self.findChild(QToolButton, "ChooseSavingPathButton")
        )
        # ------------------------------
        self._com_port_settings = ComPortSettings(
            com_port_combo_box = self.findChild(QComboBox, "ComPortComboBox"),
            com_port_info_button = self.findChild(QPushButton, "ComPortInfoButton"),
            update_com_ports_button = self.findChild(QPushButton, "UpdateComPortsButton"),
            radio_buttons = RadioButtonsDict(
                rb_921600 = self.findChild(QRadioButton, "RadioButton_921600"),
                rb_460800 = self.findChild(QRadioButton, "RadioButton_460800"),
                rb_230400 = self.findChild(QRadioButton, "RadioButton_230400"),
                rb_115200 = self.findChild(QRadioButton, "RadioButton_115200"),
                rb_57600  = self.findChild(QRadioButton, "RadioButton_57600"),
                rb_9600   = self.findChild(QRadioButton, "RadioButton_9600"),
            )
        )
        # ------------------------------
        # TODO: реализовать параметрическое добавление виджетов для построения графиков
        self._plotters: dict[int, PlottingWidget] = {
            1: PlottingWidget(self.findChild(pg.PlotWidget, "PlotterSensor_1")),
            2: PlottingWidget(self.findChild(pg.PlotWidget, "PlotterSensor_2"))
        }
        # ------------------------------

        self._com_port_reader: ComPortReader = ComPortReader()
        self._torque_calculation: TorqueCalculation = TorqueCalculation()

        # ------------------------------
        # Настроим интерфейс
        if not self._check_UI():
            app_logger.error("Неправильно настроен main_window!")
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
            app_logger.info('Корректное завершение работы приложения')
        else:
            app_logger.warning('Принудительное завершение приложения до полной остановки ComPortReader')
        QApplication.quit()

    def _init_UI(self) -> None:
        # Подключим нажатие кнопок и другие сигналы к соответствующим функциям-обработчикам
        self._start_button.clicked.connect(self._start_measuring)
        self._stop_button.clicked.connect(self._stop_measuring)

        self._com_port_reader.data_received.connect(self._data_received)
        self._com_port_reader.finished.connect(self._finishing_reading_data)
        self._com_port_reader.error_occurred.connect(self._error_handler)

        # -------------------------------------------------------------
        # Настройка виджетов для графического отображения данных АЦП
        for sensor_id in config.calibration.sensor_id_list:
            plotter = self._plotters[sensor_id]
            plotter.configure(
                title=f'Показания датчика #{sensor_id}',
                x_label='Время (с)',
                y_label='Крутящий момент (H * m)',
                background='w',
                pen=pg.mkPen(config.main_window_config.pen_params[sensor_id]),
                symbol='o',
                symbolSize=4
            )
        # -------------------------------------------------------------

    def _check_UI(self) -> bool:
        return (isinstance(self._start_button, QPushButton) and
                isinstance(self._stop_button, QPushButton) and
                isinstance(self._msg_text_edit, QTextEdit))


    # =============================================================
    # =============== Методы для обработки сигналов ===============
    # =============================================================

    def _start_measuring(self) -> None:
        try:
            # Получение пути сохранения
            saving_path = self._saving_path_setting.get_saving_path()
            app_logger.info(f'Выбранный путь сохранения: {saving_path}')

            if any(saving_path.iterdir()):
                app_logger.info('Выбрана непустая директория для сохранения результатов. Ожидается подтверждение пользователя...')
                reply = QMessageBox.question(
                    self,
                    "Подтверждение",
                    "Указанная директория не является пустой.\nФайлы с результатами могут быть перезаписаны.\nИспользовать указанный путь?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                if reply == QMessageBox.Yes:
                    app_logger.info('Пользователь подтвердил использование непустой директории для сохранения результатов.')
                elif reply == QMessageBox.No:
                    app_logger.info('Пользователь отклонил использование непустой директории для сохранения результатов.')
                    return

            # Сконфигурируем порт
            app_logger.debug('Получение данных порта и скорости его работы')
            port_name = self._com_port_settings.get_port_name()
            baudrate = self._com_port_settings.get_baudrate()
            self._com_port_reader.configure_port(port_name, baudrate)

            # Запустим чтение данных из порта
            self._com_port_reader.start_reading()
            app_logger.info(f'Начало сбора данных. Выбран порт {port_name}. Скорость работы порта - {baudrate}')
            self._msg_text_edit.append(f'Начало сбора данных.\nВыбран порт {port_name}.\nСкорость работы порта - {baudrate}\n'
                                       f'--------------------')

            # Заблокируем изменение параметров запуска и сохраним конфиг
            self._lock_input()
            self._com_port_settings.save_config()
            self._saving_path_setting.save_config()

            # Отчистим графики
            for plotter in self._plotters.values():
                plotter.clear()

        # Ошибка пути сохранения
        except InvalidPathError as err:
            app_logger.error(f'Вызвано исключение при получении директории для сохранения результатов работы:\n{err}')
            QMessageBox.warning(self, 'Неверно указан путь сохранения', f'{err}')

        # Ошибка конфигурации порта
        except ComPortSettingsError as err:
            app_logger.error(f'Вызвано исключение при настройке COM порта:\n{err}')
            QMessageBox.warning(self, 'Ошибка конфигурации порта', f'{err}')

        # Ошибка чтения порта
        except ComPortReadError as err:
            app_logger.error(f'Вызвано исключение при сборе данных:\n{err}')
            QMessageBox.warning(self, 'Ошибка чтения порта', f'{err}')

        # Неучтённое исключение
        except Exception as err:
            app_logger.exception('Получено неучтённое исключение!')
            QMessageBox.critical(self, 'Неучтённое исключение!', f'{err}')

    def _stop_measuring(self) -> None:
        self._com_port_reader.stop_reading()

    def _lock_input(self) -> None:
        self._start_button.setEnabled(False)
        self._com_port_settings.lock_input()
        self._saving_path_setting.lock_input()

    def _unlock_input(self) -> None:
        self._start_button.setEnabled(True)
        self._com_port_settings.unlock_input()
        self._saving_path_setting.unlock_input()

    def _error_handler(self, error_info: str) -> None:
        QMessageBox.critical(self, "Ошибка выполнения!", error_info)

    def _finishing_reading_data(self) -> None:
        self._unlock_input()
        app_logger.info('Завершение чтения данных')
        self._msg_text_edit.append('Завершение чтения данных')
        QMessageBox.information(self, "Уведомление", "Чтение данных завершено")

    def _data_received(self, adc_data: HX711Data):
        # TODO: сохранить полученный пакет данных в хранилище
        # print(adc_data)
        self._calc_torque(adc_data)

    def _calc_torque(self, adc_data: HX711Data) -> None:
        try:
            torque = self._torque_calculation.calc_torque(sensor_id=adc_data.id,
                                                          adc_value=(adc_data.adc_value * int(adc_data.gain)))
            self._plot_received_data(adc_data.id, adc_data.time, torque)
        except TorqueCalculationError:
            self._msg_text_edit.append('Ошибка расчёта крутящего момента по данным АЦП')
            app_logger.exception('Ошибка расчёта крутящего момента по данным АЦП')
            self._stop_measuring()
            QMessageBox.warning(self, 'Ошибка выполнения программы!', 'Ошибка расчёта крутящего момента по данным АЦП')

    def _plot_received_data(self, plotter_id: int, x_value: float, y_value: float):
        self._plotters[plotter_id].append_data(x_value, y_value)