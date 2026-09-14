from __future__ import annotations

import math
from dataclasses import replace

from attack.spoofing_attack import SpoofingAttack
from drone.gps_input_state import GpsInputState
from drone.gps_receiver import GpsReceiver

METRES_PER_DEG_LAT = 111_320.0


class DriftAttack(SpoofingAttack):
    ATTACK_TYPE = "drift"

    def __init__(self, attack_type: str, spawn_location: str):
        super().__init__(attack_type, spawn_location)
        self._from_yaml(attack_type, spawn_location)
        self.drift_rate_north = self.config["drift_rate_north"]
        self.drift_rate_east = self.config["drift_rate_east"]

    def apply(
        self,
        nominal: GpsInputState,
        receiver: GpsReceiver,
        elapsed_seconds: float,
    ) -> GpsInputState:
        """Offset position/velocity by north/east drift accumulated since activation.

        Uses the SITL truth position/velocity when available so the EKF sees a
        consistent spoof, falling back to the nominal state otherwise.
        """
        t = self.seconds_since_activation(elapsed_seconds)
        lat = (
            receiver.truth_lat
            if isinstance(receiver.truth_lat, (int, float))
            else nominal.lat
        )
        lon = (
            receiver.truth_lon
            if isinstance(receiver.truth_lon, (int, float))
            else nominal.lon
        )
        north_m = self.drift_rate_north * t
        east_m = self.drift_rate_east * t
        dlat = north_m / METRES_PER_DEG_LAT
        dlon = east_m / (METRES_PER_DEG_LAT * math.cos(math.radians(lat)))

        vn, ve, vd = nominal.vn, nominal.ve, nominal.vd
        if isinstance(receiver.truth_velocity_north, (int, float)):
            vn = receiver.truth_velocity_north
            ve = receiver.truth_velocity_east
            vd = receiver.truth_velocity_down or 0.0

        return replace(
            nominal,
            lat=lat + dlat,
            lon=lon + dlon,
            vn=vn + self.drift_rate_north,
            ve=ve + self.drift_rate_east,
            vd=vd,
        )
