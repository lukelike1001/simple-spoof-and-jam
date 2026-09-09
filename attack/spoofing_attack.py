from __future__ import annotations

from abc import ABC, abstractmethod

from attack.gps_attack import GpsAttack
from drone.gps_receiver import GpsReceiver


class SpoofingAttack(GpsAttack, ABC):
    """Abstract GPS spoofing attack: injects a fabricated position/velocity."""

    @abstractmethod
    def compute_spoofed_position(
        self, gps_receiver: GpsReceiver, elapsed_seconds: float
    ) -> tuple[float, float, float]:
        """Given a drone and the elapsed time, calculate the new spoofed location."""

    @abstractmethod
    def compute_spoofed_velocity(
        self, gps_receiver: GpsReceiver, elapsed_seconds: float
    ) -> tuple[float, float, float]:
        """Given a drone and the elapsed time, calculate the new spoofed velocity (NED)."""
