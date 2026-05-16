# -*- coding: utf-8 -*-
"""Модуль для асинхронного чтения данных из COM-порта.

Содержит класс `ComPortReader`, который управляет фоновым потоком для
непрерывного чтения байтов из COM-порта, их декодирования с помощью
`Decoder` и передачи полученных пакетов в главный поток через сигналы.
"""

# System imports
from typing import Optional

# External imports
from PyQt5.QtCore import QObject, QThread, pyqtSignal

# User imports
from app_logger import app_logger
from byte_source.com_port import ComPortHX711 as ComPort
from byte_source.com_port import ComPortReadError
from decoding import DecoderProtocol
from decoding.hx711_decoding import HX711Decoder as Decoder
from decoding.hx711_decoding import HX711Data as DataType

##########################################################

class ComPortReader(QObject):
    """Класс для управления фоновым чтением данных из COM-порта.

    Сигналы:
        data_received(DataType): Испускается при получении нового пакета данных.
        error_occurred(str): Испускается при возникновении ошибки чтения или декодирования.
        finished(): Испускается после полной остановки потока и очистки ресурсов.
    """

    data_received = pyqtSignal(DataType)
    error_occurred = pyqtSignal(str)
    finished = pyqtSignal()

    # ------------------------------------------------------------------------------

    class _ComPortReaderWorker(QObject):
        """Внутренний класс, выполняющий чтение порта.

        Сигналы:
            data_received(DataType): Пробрасывается наружу.
            error_occurred(str): Пробрасывается наружу.
            finished(): Испускается при завершении работы (всегда).
        """

        data_received = pyqtSignal(DataType)
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

    def configure_port(self, port_name: str, baudrate: int) -> None:
        """Сохраняет параметры порта для последующего использования.

        Создаёт объект `ComPort` с указанными параметрами. Если чтение уже
        запущено, порт нельзя изменить.

        Args:
            port_name (str): Имя порта.
            baudrate (int): Скорость работы порта.

        Raises:
            ComPortReadError: Если чтение уже запущено.
        """
        if self._worker_thread is not None and self._worker_thread.isRunning():
            raise ComPortReadError("Нельзя изменить порт во время чтения")
        self._com_port = ComPort(port_name, baudrate, app_logger.info)

    def start_reading(self) -> None:
        """Запускает фоновое чтение данных из порта.

        Создаёт новый поток и воркер, перемещает воркер в поток, подключает сигналы и запускает поток.

        Raises:
            ComPortReadError: Если порт не был предварительно настроен через `configure_port`,
                          или чтение порта уже запущено.
        """
        if self._com_port is None:
            raise ComPortReadError('Перед запуском необходимо выполнить конфигурацию порта!')
        if self._worker_thread and self._worker_thread.isRunning():
            raise ComPortReadError('Чтение порта уже запущено в другом потоке!')

        self._worker_thread = QThread()
        self._worker = self._ComPortReaderWorker(self._com_port)
        self._worker.moveToThread(self._worker_thread)

        # Подключаем сигналы
        self._worker_thread.started.connect(self._worker.run)
        self._worker_thread.finished.connect(self._worker_thread.deleteLater)
        self._worker_thread.finished.connect(self._on_thread_finished)

        self._worker.data_received.connect(self.data_received)
        self._worker.error_occurred.connect(self.error_occurred)
        self._worker.finished.connect(self._worker_thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)

        # Запустим поток для чтения com порта
        self._worker_thread.start()

    def stop_reading(self) -> None:
        """Остановка чтения порта."""
        if self._worker is not None:
            self._worker.stop()

    def _on_thread_finished(self) -> None:
        """Слот, вызываемый после завершения потока. Очищает ссылки и испускает сигнал."""
        self._worker_thread = None
        self._worker = None
        self.finished.emit()