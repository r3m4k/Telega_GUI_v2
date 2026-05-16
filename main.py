# System imports
import sys
import asyncio
import logging
from multiprocessing import Queue, Process
from threading import Thread, Event
from typing import Optional, Callable
from time import sleep

# External imports
import numpy as np

# User imports
from async_mc_controller.config import McConfig, ComPortConfig, LoggerConfig
from async_mc_controller.logger import McLogger
from async_mc_controller.signal_bus import McBus
from async_mc_controller.byte_source.com_port import AsyncComPortSetting, ComPortInfo
from async_mc_controller.async_mc_session import McSession
from telega_session import ComPortTelega, DecoderTelega, TelegaData, ControllerTelega

#########################

async def run_telega_session(logger_config: LoggerConfig,
                             com_port_config: ComPortConfig,
                             command_queue: Queue,
                             response_queue: Queue,
                             data_queue: Queue) -> None:
    # Настроим конфигурацию
    mc_config = McConfig()
    mc_config.logger_config = logger_config
    mc_config.com_port = com_port_config
    mc_config.logger_config.log_level = logging.DEBUG
    mc_config.logger_config.log_filename = 'telega_mc_logger.log'
    mc_config.logger_config.use_console = False

    # Создадим необходимые экземпляры
    mc_logger: McLogger = McLogger(mc_config)
    bus = McBus(mc_logger)

    com_port: ComPortTelega = ComPortTelega(mc_config.com_port.name, mc_config.com_port.baudrate,
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

    finally:
        mc_logger.debug(str(decoder))

    # Задержка для завершения всех фоновых операций
    await asyncio.sleep(1)

# =============================================================

def _start_telega_session(_logger_config: LoggerConfig,
                          _com_port_config: ComPortConfig,
                          _command_queue: Queue,
                          _response_queue: Queue,
                          _data_queue: Queue):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(run_telega_session(_logger_config, _com_port_config,
                                                   _command_queue, _response_queue, _data_queue))
    except Exception as err:
        print(err)
    finally:
        # Отменяем все незавершённые задачи
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        loop.close()

# =============================================================

def run_in_subprocess(logger_config: LoggerConfig,
                      com_port_config: ComPortConfig,
                      command_queue: Queue,
                      response_queue: Queue,
                      data_queue: Queue) -> Process:
    p = Process(target=_start_telega_session,
                args=(logger_config, com_port_config, command_queue, response_queue, data_queue),
                daemon=True)
    return p

# =============================================================

class GuiProcess:
    def __init__(self) -> None:
        self._process: Optional[Process] = None
        self._config: McConfig = McConfig()

        self._command_queue: Queue = Queue()
        self._response_queue: Queue = Queue()
        self._data_queue: Queue = Queue()

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

        for _ in range(1):
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

            # 4. Запустим измерения на 15 секунд
            self._send_command("START_MEASURING")
            sleep(5)
            self._send_command("STOP_MEASURING")

        # Завершим процесс и поток
        self._send_command("STOP_RUNNING")
        self._stop_flag = True

        # Напечатаем средние значения полученных данных
        print(f'len(received_data) = {len(self._received_data)}\n\n'
              f'DppCode = ['
              f'{np.min([data.dpp_code for data in self._received_data])}, '
              f'{np.max([data.dpp_code for data in self._received_data])}'
              f']\n'
              f'Acc_X = {np.mean([data.acc.x_coord for data in self._received_data])}\n'
              f'Acc_Y = {np.mean([data.acc.y_coord for data in self._received_data])}\n'
              f'Acc_Z = {np.mean([data.acc.z_coord for data in self._received_data])}\n\n'
              f'Gyro_X = {np.mean([data.gyro.x_coord for data in self._received_data])}\n'
              f'Gyro_Y = {np.mean([data.gyro.y_coord for data in self._received_data])}\n'
              f'Gyro_Z = {np.mean([data.gyro.z_coord for data in self._received_data])}\n')

        sleep(0.5)

        print('Завершение потока')
        self._reading_thread.join()

        print('Завершение процесса')
        self._process.join(timeout=2)

        if self._process.is_alive():
            print("Процесс ещё работает, завершение через terminate()")
            self._process.terminate()

        print('Завершение measuring_pipeline')

    def launch(self):
        settings = AsyncComPortSetting(ComPortTelega, self._config)
        settings.configure_source()
        self._com_port_info = settings.get_port_info()

        self._config.com_port.name = self._com_port_info.name
        self._config.com_port.baudrate = self._com_port_info.baudrate

        self._process = run_in_subprocess(self._config.logger_config, self._config.com_port,
                                          self._command_queue, self._response_queue, self._data_queue)

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