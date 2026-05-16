# -*- coding: utf-8 -*-
"""Асинхронная сессия для работы с МК путеизмерительной тележки.

Запускается в отдельном процессе, общается с родителем через multiprocessing.Queue.
"""

# System imports
import asyncio
import logging
from multiprocessing import Queue, Process

# External imports

# User imports
from async_mc_controller.config import McConfig, ComPortConfig, LoggerConfig
from async_mc_controller.logger import McLogger
from async_mc_controller.signal_bus import McBus
from async_mc_controller.async_mc_session import McSession
from telega_session import ComPortTelega, DecoderTelega, ControllerTelega

#########################

async def _run_telega_session(logger_config: LoggerConfig,
                             com_port_config: ComPortConfig,
                             command_queue: Queue,
                             response_queue: Queue,
                             data_queue: Queue) -> None:

    """Запуск асинхронной сессии управления путеизмерительной тележкой.

    Args:
       logger_config:   Конфигурация логирования.
       com_port_config: Конфигурация COM-порта (имя, скорость).
       command_queue:   Очередь для получения команд от родителя.
       response_queue:  Очередь для отправки ответов (HANDSHAKE_DONE, STOP_CALIBRATION...).
       data_queue:      Очередь для отправки пакетов TelegaData.
    """

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
    # Запуск сессии.
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

def start_telega_session(_logger_config: LoggerConfig,
                          _com_port_config: ComPortConfig,
                          _command_queue: Queue,
                          _response_queue: Queue,
                          _data_queue: Queue):
    """Функция, запускаемая в отдельном процессе
    (точка входа для мультипроцессорной реализации)."""

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