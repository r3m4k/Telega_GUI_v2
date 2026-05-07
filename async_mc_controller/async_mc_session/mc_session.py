# System imports
import asyncio

# External imports

# User imports
from async_mc_controller.logger import app_logger
from async_mc_controller.byte_source.bytes_source import AsyncBytesSource
from async_mc_controller.byte_source.com_port.com_port_error import ComPortReadError
from async_mc_controller.signal_bus import bus

#########################

class MCSession:
    def __init__(self):
        ...

    async def __aenter__(self):
        ...

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False

