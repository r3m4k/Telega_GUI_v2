# System imports
import asyncio

# External imports

# User imports
from async_mc_controller.signal_bus import McBus
from async_mc_controller.logger import McLogger
from async_mc_controller.byte_source.com_port import AsyncComPortDevice
from .packet_builders import PacketBuilderTelegaText, PacketBuilderTelegaBytes

#########################

class ComPortTelega(AsyncComPortDevice):
    # Команды, отправляемые на МК
    _handshake_req_command: bytes = PacketBuilderTelegaText.build_text_command('HANDSHAKE_ACK')
    _heartbeat_req_command: bytes = PacketBuilderTelegaText.build_text_command('HEARTBEAT_ACK')

    _restart_command: bytes = PacketBuilderTelegaBytes.build_byte_command(bytes([0xFF, 0xFF]))

    _set_foo_stage_command:         bytes = PacketBuilderTelegaBytes.build_byte_command(bytes([0xAA, 0x00]))
    _set_calibration_stage_command: bytes = PacketBuilderTelegaBytes.build_byte_command(bytes([0xAA, 0x01]))
    _set_measure_stage_command:     bytes = PacketBuilderTelegaBytes.build_byte_command(bytes([0xAA, 0x02]))
    _set_static_init_stage_command: bytes = PacketBuilderTelegaBytes.build_byte_command(bytes([0xAA, 0x03]))

    def __init__(self, port_name: str, baudrate: int,
                 bus: McBus, mc_logger: McLogger):
        super().__init__(port_name, baudrate, bus, mc_logger)

        self._telega_mc_logger = mc_logger.get_child_logger("ComPort.Device.Telega")

        # Подпишемся на нужные сигналы
        self._bus.stop_measuring.subscribe(self)
        self._bus.start_measuring.subscribe(self)
        self._bus.start_calibration.subscribe(self)
        self._bus.start_static_init.subscribe(self)

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Перед выходом из контекстного менеджера отправим команду _set_foo_stage_command
        await self._send_command_with_ack(self._set_foo_stage_command)

        # Отпишемся от событий шины
        self._bus.stop_measuring.unsubscribe(self)
        self._bus.start_measuring.unsubscribe(self)
        self._bus.start_calibration.unsubscribe(self)
        self._bus.start_static_init.unsubscribe(self)

        await super().__aexit__(exc_type, exc_val, exc_tb)

        return False

    async def on_stop_measuring(self) -> None:
        self._telega_mc_logger.debug('Остановка чтения данных')
        await self._send_command_with_ack(self._set_foo_stage_command)

    async def on_start_calibration(self) -> None:
        self._telega_mc_logger.debug('Начало калибровки')
        await self._send_command_with_ack(self._set_calibration_stage_command)

    async def on_start_measuring(self) -> None:
        self._telega_mc_logger.debug('Начало чтения данных')
        await self._send_command_with_ack(self._set_measure_stage_command)

    async def on_start_static_init(self) -> None:
        self._telega_mc_logger.debug('Начало набора статического буфера')
        await self._send_command_with_ack(self._set_static_init_stage_command)

