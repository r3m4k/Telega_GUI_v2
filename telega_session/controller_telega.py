# System imports
import asyncio
import logging
from typing import Any, Optional
from enum import IntEnum

# External imports

# User imports
from async_mc_controller.signal_bus import McBus
from async_mc_controller.logger import McLogger
from async_mc_controller.byte_source.read_error import ReadError
from async_mc_controller.controller import Controller

#########################

_RESPONSE_TIMEOUT: float = 2.0    # Таймаут выставления событий

# ----------------------------------------------------------------

class TelegaStatusCode(IntEnum):
    SUCCESS = 0
    UNKNOWN_ERROR = 1
    READ_ERROR = 2
    HANDSHAKE_ERROR = 3
    DEVICE_LOST = 4
    COMMAND_ACK_TIMEOUT = 5
    COMMAND_REJECTED = 6

# ----------------------------------------------------------------

class UnknownTelegaStatusCode(KeyError):
    def __init__(self, status_code: TelegaStatusCode, message: str = None):
        self.status_code = status_code
        self.message = message or f"Неизвестный код статуса: {status_code.name} // {status_code.value}"
        super().__init__(self.message)

    def __str__(self) -> str:
        return self.message

# ----------------------------------------------------------------

class TelegaStatusCodeMessages:
    def __init__(self):
        self.__messages: dict[TelegaStatusCode, str] = {
            TelegaStatusCode.SUCCESS:             "Корректное завершение работы",
            TelegaStatusCode.UNKNOWN_ERROR:       "Неизвестная ошибка",
            TelegaStatusCode.READ_ERROR:          "Ошибка чтения данных",
            TelegaStatusCode.HANDSHAKE_ERROR:     "Ошибка процедуры рукопожатия",
            TelegaStatusCode.DEVICE_LOST:         "Потеря связи с устройством",
            TelegaStatusCode.COMMAND_ACK_TIMEOUT: "Таймаут ожидания подтверждения команды",
            TelegaStatusCode.COMMAND_REJECTED:    "Команда не распознана устройством",
        }

    def __getitem__(self, status_code: TelegaStatusCode) -> str:
        if status_code in self.__messages.keys():
            return self.__messages[status_code]
        else:
            raise UnknownTelegaStatusCode(status_code)

    def __setitem__(self, key, value):
        raise TypeError("TelegaStatusCodeMessage is read-only")

# ----------------------------------------------------------------

class TelegaController(Controller):
    def __init__(self, bus: McBus, mc_logger: McLogger):
        super().__init__(bus, mc_logger)

        # Используемый в TelegaController логгер
        self._telega_controller_logger: logging.Logger = mc_logger.get_child_logger("Controller.TelegaController")

        # Необходимые события
        self._handshake_done_event: asyncio.Event = asyncio.Event()     # Событие выполнения рукопожатия
        self._calibration_done_event: asyncio.Event = asyncio.Event()   # Событие завершения калибровки
        self._static_init_done_event: asyncio.Event = asyncio.Event()   # Событие завершения сбора статического буфера

        # Таска для пайплайна сбора данных
        self._measuring_pipeline_task: Optional[asyncio.Task] = None

        # Код завершения работы с МК и предопределённые текстовые сообщения
        self._telega_status_code: TelegaStatusCode = TelegaStatusCode.SUCCESS
        self._telega_status_code_messages = TelegaStatusCodeMessages()

    # =============================================================
    # ======= Методы для работы в контекстном менеджере ===========
    # =============================================================

    async def __aenter__(self) -> 'Controller':
        """ Самостоятельная подписка на специфичные события шины """
        await super().__aenter__()

        self._bus.stop_calibration.subscribe(self)
        self._bus.stop_static_init.subscribe(self)
        self._bus.interrupt_measuring.subscribe(self)

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        """ Отписка от специфичных сигналов шины """

        self._bus.stop_calibration.unsubscribe(self)
        self._bus.stop_static_init.unsubscribe(self)

        await self._cancel_task(self._measuring_pipeline_task)

        if self._telega_status_code == TelegaStatusCode.SUCCESS:
            self._telega_controller_logger.debug(
                f'\nКод завершения работы с устройством: {self._telega_status_code}\n'
                f'// {self._telega_status_code_messages[self._telega_status_code]}'
            )

        return await super().__aexit__(exc_type, exc_val, exc_tb)

    # =============================================================
    # ===================== Публичные методы ======================
    # =============================================================

    async def run_measuring_pipeline(self) -> None:
        """ Запуск пайплайна по сбору данных """
        self._measuring_pipeline_task = asyncio.create_task(self._measuring_pipeline())
        try:
            await self._measuring_pipeline_task
        except Exception as e:
            self._telega_controller_logger.exception(f"Ошибка пайплайне измерений: {e}")

    async def start_calibration(self) -> None:
        """ Запуск калибровки датчиков """
        await self._bus.start_calibration.emit()

    async def start_static_init(self) -> None:
        """ Запуск набора статического буфера """
        await self._bus.start_static_init.emit()

    async def start_measuring(self) -> None:
        """ Запуск измерений """
        await self._bus.start_measuring.emit()

    async def stop_measuring(self) -> None:
        """ Остановка измерений """
        await self._bus.stop_measuring.emit()

    # =============================================================
    # =================== Внутренняя логика =======================
    # =============================================================

    async def _measuring_pipeline(self) -> None:
        """ Последовательный запуск всех этапов для сбора данных """
        try:
            # 1. Рукопожатие
            self._handshake_done_event.clear()
            await self._bus.handshake_init.emit()
            await self._handshake_done_event.wait()

            # 2. Запуск калибровки датчиков
            self._calibration_done_event.clear()
            await self.start_calibration()
            await self._calibration_done_event.wait()

            # 3. Запуск набора статического буфера
            self._static_init_done_event.clear()
            await self.start_static_init()
            await self._static_init_done_event.wait()

            # 4. Запуск измерений
            await self._bus.start_measuring.emit()
            await asyncio.sleep(10)

            # 5. Завершение измерений
            await self._bus.stop_measuring.emit()

        except asyncio.CancelledError:
            self._telega_controller_logger.debug(f'_measuring_pipeline остановлен!')
            raise

    # =============================================================
    # =================== Обработчики сигналов ====================
    # =============================================================

    async def on_package_ready(self, data: Any) -> None:
        """Обработчик сигнала PACKAGE_READY — выводит номер пакета в консоль.

        Печать через `\\r` без перевода строки — каждый следующий вывод
        перезаписывает предыдущий.
        Финальный `\\n` после остановки — ответственность вызывающего
        кода.

        Args:
            data: Объект с атрибутом `package_num`.
        """
        try:
            print(f'\rПринят пакет #{data.package_num}', end='', flush=True)
        except AttributeError:
            self._telega_controller_logger.error(
                f"Полученный пакет данных типа {type(data)} не имеет поле package_num!"
            )

    async def on_handshake_done(self) -> None:
        """Обработчик сигнала HANDSHAKE_DONE от декодера.

        Устанавливает событие _handshake_done_event.
        """
        self._handshake_done_event.set()

    async def on_stop_calibration(self) -> None:
        """ Обработчик сигнала STOP_CALIBRATION от декодера.

        Устанавливает событие _calibration_done_event.
        """
        self._calibration_done_event.set()

    async def on_stop_static_init(self) -> None:
        """ Обработчик сигнала STOP_STATIC_INIT от декодера.

        Устанавливает событие _static_init_done_event.
        """
        self._static_init_done_event.set()

    async def on_interrupt_measuring(self) -> None:
        """ Обработчик сигнала STOP_STATIC_INIT от декодера.

        Отмена _measuring_pipeline_task.
        """
        await self._cancel_task(self._measuring_pipeline_task)

    async def on_read_error(self, err: ReadError) -> None:
        """Обработчик сигнала READ_ERROR.

        Отменим self._measuring_pipeline_task, установим TelegaStatusCode.READ_ERROR
        и вызовем родительский обработчик сигнала.

        Args:
            err (ReadError): Исключение, которое привело к остановке чтения.
        """
        await self._cancel_task(self._measuring_pipeline_task)
        self._telega_status_code = TelegaStatusCode.READ_ERROR
        await super().on_read_error(err)

    async def on_handshake_failed(self) -> None:
        """Обработчик сигнала HANDSHAKE_FAILED.

        Отменим self._measuring_pipeline_task, установим TelegaStatusCode.HANDSHAKE_ERROR
        и вызовем родительский обработчик сигнала.
        """
        await self._cancel_task(self._measuring_pipeline_task)
        self._telega_status_code = TelegaStatusCode.HANDSHAKE_ERROR
        await super().on_handshake_failed()

    async def on_device_lost(self) -> None:
        """Обработчик сигнала DEVICE_LOST.

        Отменим self._measuring_pipeline_task, установим TelegaStatusCode.DEVICE_LOST
        и вызовем родительский обработчик сигнала.
        """
        await self._cancel_task(self._measuring_pipeline_task)
        self._telega_status_code = TelegaStatusCode.DEVICE_LOST
        await super().on_device_lost()

    async def on_command_ack_timeout(self) -> None:
        """Обработчик сигнала COMMAND_ACK_TIMEOUT.

        Отменим self._measuring_pipeline_task, установим TelegaStatusCode.COMMAND_ACK_TIMEOUT
        и вызовем родительский обработчик сигнала.
        """
        await self._cancel_task(self._measuring_pipeline_task)
        self._telega_status_code = TelegaStatusCode.COMMAND_ACK_TIMEOUT
        await super().on_command_ack_timeout()

    async def on_command_rejected(self) -> None:
        """Обработчик сигнала COMMAND_REJECTED.

        Отменим self._measuring_pipeline_task, установим TelegaStatusCode.COMMAND_REJECTED
        и вызовем родительский обработчик сигнала.
        """
        await self._cancel_task(self._measuring_pipeline_task)
        self._telega_status_code = TelegaStatusCode.COMMAND_REJECTED
        await super().on_command_rejected()
