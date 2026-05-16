# -*- coding: utf-8 -*-
"""Модуль для хранения и сохранения данных, полученных от МК тележки.

Содержит класс DataStorage, который накапливает пакеты TelegaData в памяти,
позволяет задать файл для сохранения и очищает данные при смене файла.
"""

# System imports
import csv
from pathlib import Path
from typing import List, Optional

# External imports

# User imports
from telega_session import TelegaData

##########################################################

class DataStorage:
    """Хранилище данных TelegaData с возможностью записи в CSV-файл.

    При смене целевого файла (через set_file) внутренний список данных очищается.
    Данные можно добавлять методом add_package().
    Явное сохранение в файл выполняется методом save_to_file().

    Attributes:
        received_data (List[TelegaData]): Накопленные пакеты данных.
        file_path (Optional[Path]): Путь к файлу для сохранения.
    """

    def __init__(self) -> None:
        """Инициализирует пустое хранилище без файла для сохранения."""
        self.received_data: List[TelegaData] = []
        self.file_path: Optional[Path] = None

    def set_file(self, file_path: Path) -> None:
        """Задаёт файл для сохранения данных и очищает текущие данные.

        Если нужно сохранить старые данные перед очисткой,
        вызовите save_to_file() перед вызовом set_file().

        Args:
            file_path: Путь к CSV-файлу (расширение .csv рекомендуется).

        Raises:
            TypeError: Если file_path не является экземпляром Path.
        """
        if not isinstance(file_path, Path):
            raise TypeError(f"Ожидается Path, получен {type(file_path)}")
        self.file_path = file_path
        self.clear()

    def clear(self) -> None:
        """Очищает внутренний список данных."""
        self.received_data.clear()

    def add_package(self, package: TelegaData) -> None:
        """Добавляет новый пакет данных в хранилище.

        Args:
            package: Объект TelegaData, полученный от МК.
        """
        self.received_data.append(package)

    def save_received_data(self, filepath: Path, sep: str = ' ') -> None:
        """Сохраняет все накопленные данные декодера в CSV-файл.

        Формат: PackageNum, DppCode, AccX, AccY, AccZ, GyroX, GyroY, GyroZ.
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
                f'PackageNum{sep}DppCode{sep}'
                f'AccX{sep}AccY{sep}AccZ{sep}'
                f'GyroX{sep}GyroY{sep}GyroZ\n'
            )
            for data in self.received_data:
                file.write(
                    f'{data.package_num}{sep}'
                    f'{data.dpp_code}{sep}'
                    f'{data.dpp_code}{sep}'
                    f'{data.acc.x_coord}{sep}{data.acc.y_coord}{sep}{data.acc.z_coord}{sep}'
                    f'{data.gyro.x_coord}{sep}{data.gyro.y_coord}{sep}{data.gyro.z_coord}\n'
                )

    @property
    def count(self) -> int:
        """Возвращает количество хранящихся пакетов данных."""
        return len(self.received_data)