# System imports
import asyncio
from pprint import pformat
import logging

# External imports

# User imports
from async_mc_controller.config import McConfig, config_path
from async_mc_controller.logger import McLogger
from async_mc_controller.signal_bus import McBus
from async_mc_controller.byte_source.com_port import AsyncComPortSetting
from async_mc_controller.async_mc_session import McSession
from telega_session import ComPortTelega, DecoderTelega, ControllerTelega

#########################

async def main() -> None:
    # Настроим конфигурацию
    mc_config = McConfig.load(config_path)
    # mc_config.logger_config.log_level = logging.DEBUG
    mc_config.logger_config.log_level = logging.INFO
    mc_config.logger_config.log_filename = 'telega_mc_logger.log'

    # Создадим необходимые экземпляры
    mc_logger: McLogger = McLogger(mc_config)
    bus = McBus(mc_logger)

    setting = AsyncComPortSetting(ComPortTelega, mc_config, mc_logger)
    setting.configure_source()
    com_port: ComPortTelega = setting.get_bytes_source(bus, mc_logger)

    decoder: DecoderTelega = DecoderTelega(bus, mc_logger)

    controller: ControllerTelega = ControllerTelega(bus, mc_logger)

    # ------------------------------------------
    # Запуск работы с МК.
    # Порядок вызова __aenter__ и __aexit__ важен,
    # поэтому стоит использовать McSession!
    # ------------------------------------------
    async with McSession(decoder, com_port, controller):
        mc_logger.debug(pformat(bus.get_subscribers()))

        await controller.run_measuring_pipeline()

    print(decoder)


if __name__ == '__main__':
    asyncio.run(main())
