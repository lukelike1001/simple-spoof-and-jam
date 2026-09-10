import math

from attack.spoofing_attack import SpoofingAttack
from drone.gps_receiver import GpsReceiver

METRES_PER_DEG_LAT = 111_320.0


class DriftAttack(SpoofingAttack):
    ATTACK_TYPE = "drift"

    def __init__(self, attack_type: str, spawn_location: str):
        super().__init__(attack_type, spawn_location)
        self._from_yaml(attack_type, spawn_location)
        self.drift_rate_north = self.config["drift_rate_north"]
        self.drift_rate_east = self.config["drift_rate_east"]


    def compute_spoofed_position(
            self, gps_receiver: GpsReceiver, elapsed_seconds: float
    ) -> tuple[float, float, float]:
        """Offset the reported position by north/east metres accumulated since activation."""
        t = self.seconds_since_activation(elapsed_seconds)
        lat = gps_receiver.truth_lat if isinstance(gps_receiver.truth_lat, (int, float)) else gps_receiver.lat
        lon = gps_receiver.truth_lon if isinstance(gps_receiver.truth_lon, (int, float)) else gps_receiver.lon
        north_m = self.drift_rate_north * t
        east_m = self.drift_rate_east * t
        dlat = north_m / METRES_PER_DEG_LAT
        dlon = east_m / (METRES_PER_DEG_LAT * math.cos(math.radians(lat)))
        return (lat + dlat, lon + dlon, gps_receiver.alt)

    def compute_spoofed_velocity(
            self, gps_receiver: GpsReceiver, elapsed_seconds: float
    ) -> tuple[float, float, float]:
        """Truth NED velocity plus the configured drift rates, so the EKF sees a consistent spoof."""
        vn, ve, vd = gps_receiver.get_velocity()
        if isinstance(gps_receiver.truth_velocity_north, (int, float)):
            vn = gps_receiver.truth_velocity_north
            ve = gps_receiver.truth_velocity_east
            vd = gps_receiver.truth_velocity_down or 0.0
        return (
            vn + self.drift_rate_north,
            ve + self.drift_rate_east,
            vd,
        )