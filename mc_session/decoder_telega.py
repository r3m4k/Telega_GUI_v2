# System imports
import asyncio
from typing import NamedTuple
import logging
from pathlib import Path

# External imports

# User imports
from async_mc_controller.signal_bus import McBus
from async_mc_controller.logger import McLogger
from async_mc_controller.decoding import DeviceDecoder, TriaxialData

#########################

class TelegaData(NamedTuple):
    package_num: int
    acc: TriaxialData
    gyro: TriaxialData

    def __str__(self):
        return (f'PackageNum: {self.package_num}\n\n'

                f'Acc:  {self.acc.x_coord}\n'
                f'      {self.acc.y_coord}\n'
                f'      {self.acc.z_coord}\n\n'

                f'Gyro: {self.gyro.x_coord}\n'
                f'      {self.gyro.y_coord}\n'
                f'      {self.gyro.z_coord}\n')

# ------------------------------------------

# Описание начала индексов данных внутри посылки
class TelegaDataIndexes:
    """Смещения начала полей данных внутри бинарного пакета.
    Индексы отсчитываются от начала всей посылки, включая заголовок.
    """
    package_num = 4
    acc_index = 8
    gyro_index = 20

# ------------------------------------------

class DecoderTelega(DeviceDecoder[TelegaData]):

    # TODO: заполнить сообщения согласно протоколу
    # Получаемые текстовые сообщения от МК
    _handshake_ack: str = "" # Ожидаемое сообщение рукопожатия
    _heartbeat_ack: str = "" # Ожидаемое сообщение heartbeat
    _command_ack: str = "" # Ожидаемое подтверждение команды
    _command_rejected_msg: str = "" # Отказ МК: команда не распознана

    # Константы форматов пакетов протокола
    _DataFormatBt: bytes = b'\x01'       # Пакет с данными
    _MessageFormatBt: bytes = b'\xCD'    # Текстовое сообщение

    def save_received_data(self, filepath: Path, sep: str = ' ') -> None:
        """Сохраняет все накопленные данные декодера в CSV-файл.

        Формат: PackageNum, AccX, AccY, AccZ, GyroX, GyroY, GyroZ.
        Числа с плавающей точкой записываются с точкой как десятичным
        разделителем — поэтому разделитель полей по умолчанию пробел.

        Args:
            filepath (Path): Путь к файлу сохранения.
            sep (str):       Разделитель полей. По умолчанию пробел.

        Raises:
            ValueError: Если нет данных для сохранения.
        """
        if not self.received_data:
            raise ValueError('Нет данных для сохранения. Список received_data пуст.')

        file_path = Path(filepath)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(
                f'PackageNum{sep}'
                f'AccX{sep}AccY{sep}AccZ{sep}'
                f'GyroX{sep}GyroY{sep}GyroZ\n'
            )
            for data in self.received_data:
                file.write(
                    f'{data.package_num}{sep}'
                    f'{data.acc.x_coord}{sep}{data.acc.y_coord}{sep}{data.acc.z_coord}{sep}'
                    f'{data.gyro.x_coord}{sep}{data.gyro.y_coord}{sep}{data.gyro.z_coord}\n'
                )

    def _bytes_to_protocol_data(self, byte_list: list[bytes]) -> TelegaData:
        """ Декодирование байтов в пакет данных TelegaData """
        ...