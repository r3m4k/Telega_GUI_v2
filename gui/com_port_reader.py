# -*- coding: utf-8 -*-
"""Модуль для асинхронного чтения данных из COM-порта.

Содержит класс `ComPortReader`, который управляет фоновым потоком для
непрерывного чтения байтов из COM-порта, их декодирования с помощью
`Decoder` и передачи полученных пакетов в главный поток через сигналы.
"""

# System imports
from typing import Optional
from pathlib import Path

# External imports
from PyQt5.QtCore import QObject, QThread, pyqtSignal

# User imports
from app_config import AppConfig
from async_mc_controller.config import LoggerConfig, ComPortConfig
from telega_session import start_telega_session
from telega_session import TelegaData as PackageType

##########################################################

class ComPortReader(QObject):
    """Класс для управления фоновым чтением данных из COM-порта.

    Сигналы:
        data_received(PackageType): Испускается при получении нового пакета данных.
        error_occurred(str): Испускается при возникновении ошибки чтения или декодирования.
        finished(): Испускается после полной остановки потока и очистки ресурсов.
    """

    data_received = pyqtSignal(PackageType)
    error_occurred = pyqtSignal(str)
    finished = pyqtSignal()

    # ------------------------------------------------------------------------------

    class _ComPortReaderWorker(QObject):
        """Внутренний класс, выполняющий низкоуровневое взаимодействие с МК.

        Сигналы:
            data_received(DataType): Пробрасывается наружу.
            error_occurred(str): Пробрасывается наружу.
            finished(): Испускается при завершении работы (всегда).
        """

        data_received = pyqtSignal(PackageType)
        error_occurred = pyqtSignal(str)
        finished = pyqtSignal()

        def __init__(self, port: ComPort):
            """Инициализирует воркер с заданным объектом порта.

            Args:
                port (ComPort): Объект для работы с COM-портом.
            """
            super().__init__()
            self._com_port: ComPort = port
            self._decoder: DecoderProtocol[dict[int, list[DataType]]] = Decoder()
            self._reading_flag = False

        def run(self) -> None:
            """Основной метод, выполняемый в потоке.

            Открывает порт, читает байты, передаёт их декодеру и отправляет
            готовые пакеты через сигнал `data_received`. При ошибке испускает
            `error_occurred`. В любом случае по завершении испускает `finished`.
            """
            self._reading_flag = True
            try:
                with self._com_port as port:
                    while self._reading_flag:
                        self._decoder.byte_processing(port.read_byte())
                        for sensor_id in list(self._decoder.received_data.keys()):
                            sensor_data = self._decoder.received_data[sensor_id]
                            if sensor_data:
                                self.data_received.emit(sensor_data.pop())
            except ComPortReadError as e:
                self.error_occurred.emit(f"Ошибка порта: {e}")
            except Exception as e:
                self.error_occurred.emit(f"Неизвестная ошибка: {e}")
            finally:
                self.finished.emit()
                app_logger.debug(f'{self._decoder}')

        def stop(self) -> None:
            """Изменение внутреннего флага для завершения чтения данных из порта."""
            self._reading_flag = False

    # ------------------------------------------------------------------------------

    def __init__(self):
        super().__init__()
        self._worker_thread: Optional[QThread] = None
        self._worker: Optional[ComPortReader._ComPortReaderWorker] = None
        self._com_port: Optional[ComPort] = None

    @property
    def is_active(self):
        return self._worker is not None

    def configure(self, com_port_name: str, bin_file: Path) -> None:
        ...

    def start_calibration(self) -> None:
        ...

    def start_static_init(self) -> None:
        ...

    def start_measuring(self) -> None:
        ...

    def stop_measuring(self) -> None:
        ...

    def _on_thread_finished(self) -> None:
        """Слот, вызываемый после завершения потока. Очищает ссылки и испускает сигнал."""
        self._worker_thread = None
        self._worker = None
        self.finished.emit()