# System imports
import asyncio
from multiprocessing import Queue, Process
from threading import Thread, Event
from typing import Optional, NamedTuple, Callable
import logging
from time import sleep

# External imports
import numpy as np

# User imports
from async_mc_controller.config import McConfig
from async_mc_controller.logger import McLogger
from async_mc_controller.signal_bus import McBus
from async_mc_controller.byte_source.com_port import AsyncComPortSetting, ComPortInfo
from async_mc_controller.async_mc_session import McSession
from telega_session import ComPortTelega, DecoderTelega, TelegaData, ControllerTelega

#########################

async def run_telega_session(config: McConfig,
                             command_queue: Queue,
                             response_queue: Queue,
                             data_queue: Queue) -> None:
    # Настроим конфигурацию
    mc_config = config
    mc_config.logger_config.log_filename = 'telega_mc_logger.log'
    mc_config.logger_config.use_console = False

    # Создадим необходимые экземпляры
    mc_logger: McLogger = McLogger(mc_config)
    bus = McBus(mc_logger)

    com_port: ComPortTelega = ComPortTelega(config.com_port.name, config.com_port.baudrate,
                                            bus, mc_logger)

    decoder: DecoderTelega = DecoderTelega(bus, mc_logger)

    controller: ControllerTelega = ControllerTelega(bus, mc_logger, command_queue,
                                                    response_queue, data_queue)

    # ------------------------------------------
    # Запуск работы с МК.
    # Порядок вызова __aenter__ и __aexit__ важен,
    # поэтому стоит использовать McSession!
    # ------------------------------------------
    try:
        async with McSession(decoder, com_port, controller):
            await controller.running()

    except Exception as err:
        mc_logger.error(f"Получено следующее исключение вне контекстного менеджера: {err}")

# =============================================================

def run_in_subprocess(config: McConfig,
                      command_queue: Queue,
                      response_queue: Queue,
                      data_queue: Queue) -> Process:

    def _start_telega_session(_config: McConfig,
                              _command_queue: Queue,
                              _response_queue: Queue,
                              _data_queue: Queue):
        asyncio.run(run_telega_session(_config, _command_queue, _response_queue, _data_queue))

    p = Process(target=_start_telega_session,
                args=(config, command_queue, response_queue, data_queue))
    return p

# =============================================================

class GuiProcess:
    def __init__(self) -> None:
        self._process: Optional[Process] = None
        self._config: McConfig = McConfig()

        self._command_queue: Queue[str] = Queue()
        self._response_queue: Queue[str] = Queue()
        self._data_queue: Queue[TelegaData] = Queue()

        self._com_port_info: Optional[ComPortInfo] = None

        self._stop_flag = False
        self._reading_thread: Optional[Thread] = None

        self._received_data: list[TelegaData] = []

        # События для синхронизации с дочерним процессом
        self._handshake_event = Event()
        self._calibration_event = Event()
        self._static_init_event = Event()

        # Обработчики полученных команд
        self._msg_to_handler: dict[str, Callable[[], None]] = {
            "HANDSHAKE_DONE": self._handshake_done,
            "STOP_CALIBRATION": self._calibration_done,
            "STOP_STATIC_INIT": self._static_init_done,
        }

    def measuring_pipeline(self) -> None:
        if any(worker is None for worker in [self._process, self._reading_thread]):
            raise RuntimeError('Для начала запустите рабочий процесс и поток чтения очередей!')

        for _ in range(2):
            # Сбросим события
            self._handshake_event.clear()
            self._calibration_event.clear()
            self._static_init_event.clear()

            # 1. Выполним процедуру рукопожатия
            self._send_command("HANDSHAKE_INIT")
            self._handshake_event.wait()

            # 2. Запустим калибровку и дождёмся её завершения
            self._send_command("START_CALIBRATION")
            self._calibration_event.wait()

            # 3. Запустим сбор статического буфера
            self._send_command("START_STATIC_INIT")
            self._static_init_event.wait()

        # Завершим процесс и поток
        self._send_command("STOP_RUNNING")
        self._stop_flag = True

        for worker in [self._process, self._reading_thread]:
            worker.join(timeout=5)

        # Напечатаем средние значения полученных данных
        print(f'len(received_data) = {len(self._received_data)}\n\n'
              f'DppCode = ['
                  f'{np.min([data.dpp_code for data in self._received_data])}, '
                  f'{np.max([data.dpp_code for data in self._received_data])}'
              f']'
              f'Acc_X = {np.mean([data.acc.x_coord for data in self._received_data])}\n'
              f'Acc_Y = {np.mean([data.acc.y_coord for data in self._received_data])}\n'
              f'Acc_Z = {np.mean([data.acc.z_coord for data in self._received_data])}\n\n'
              f'Gyro_X = {np.mean([data.gyro.x_coord for data in self._received_data])}\n'
              f'Gyro_Y = {np.mean([data.gyro.y_coord for data in self._received_data])}\n'
              f'Gyro_Z = {np.mean([data.gyro.z_coord for data in self._received_data])}\n')

    def launch(self):
        settings = AsyncComPortSetting(ComPortTelega, self._config)
        settings.configure_source()
        self._com_port_info = settings.get_port_info()

        self._config.com_port.name = self._com_port_info.name
        self._config.com_port.baudrate = self._com_port_info.baudrate

        self._process = run_in_subprocess(self._config, self._command_queue,
                                          self._response_queue, self._data_queue)

        self._reading_thread = Thread(target=self._reading_queues)

        self._process.start()
        self._reading_thread.start()

    def _send_command(self, cmd: str) -> None:
        print(f'Отправка команды {cmd}')
        self._command_queue.put(cmd)

    def _reading_queues(self) -> None:
        while not self._stop_flag:
            if not self._response_queue.empty():
                response = self._response_queue.get()
                if response not in self._msg_to_handler.keys():
                    print(f"Неизвестное сообщение: {response}")
                    continue
                handler = self._msg_to_handler[response]
                handler()

            if not self._data_queue.empty():
                package: TelegaData = self._data_queue.get()
                self._received_data.append(package)

    def _handshake_done(self) -> None:
        print("GuiProcess: handshake_done")
        self._handshake_event.set()

    def _calibration_done(self) -> None:
        print("GuiProcess: calibration_done")
        self._calibration_event.set()

    def _static_init_done(self) -> None:
        print("GuiProcess: static_init_done")
        self._static_init_event.set()


# =============================================================


if __name__ == "__main__":
    gui_process = GuiProcess()
    gui_process.launch()
    gui_process.measuring_pipeline()