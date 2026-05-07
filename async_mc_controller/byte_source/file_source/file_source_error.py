# System imports

# External imports

# User imports
from async_mc_controller.byte_source.read_error import ReadError

#########################


class FileReadError(ReadError):
    """Ошибка чтения из файла."""
    pass