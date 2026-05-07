"""
Пакет асинхронной сигнальной шины
"""

__version__ = '1.0.0'
__author__ = 'Roman Romanovskiy'

# --------------------------------------------------------

from .signals import Signals
from .signal_bus import SignalBus, Subscriber
from .subscribers import (
    NewByteSubscriber,
    PackageReadySubscriber,
    StartMeasuringSubscriber,
    StopMeasuringSubscriber,
    InterruptMeasuringSubscriber,
    ReadErrorSubscriber,
    HandshakeInitSubscriber,
    HandshakeDoneSubscriber,
    HeartbeatSentSubscriber,
    HeartbeatAckSubscriber,
    HandshakeFailedSubscriber,
    DeviceLostSubscriber,
    CommandSentSubscriber,
    CommandAckSubscriber,
    CommandAckTimeoutSubscriber,
    CommandRejectedSubscriber,
)
from .app_bus import McBus

# Глобальный экземпляр шины для использования во всём приложении
bus = McBus()

# --------------------------------------------------------

__all__ = [
    # Универсальный механизм
    'SignalBus',
    'Subscriber',
    'Signals',

    # Типизированная обёртка и глобальный экземпляр
    'McBus',
    'bus',

    # Протоколы подписчиков
    'NewByteSubscriber',
    'PackageReadySubscriber',
    'StartMeasuringSubscriber',
    'StopMeasuringSubscriber',
    'InterruptMeasuringSubscriber',
    'ReadErrorSubscriber',
    'HandshakeInitSubscriber',
    'HandshakeDoneSubscriber',
    'HeartbeatSentSubscriber',
    'HeartbeatAckSubscriber',
    'HandshakeFailedSubscriber',
    'DeviceLostSubscriber',
    'CommandSentSubscriber',
    'CommandAckSubscriber',
    'CommandAckTimeoutSubscriber',
    'CommandRejectedSubscriber',
]

# --------------------------------------------------------