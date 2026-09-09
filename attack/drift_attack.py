from attack.spoofing_attack import SpoofingAttack
from drone.gps_receiver import GpsReceiver

class DriftAttack(SpoofingAttack):
    ATTACK_TYPE = "drift"

    def __init__(self, attack_type: str, spawn_location: str):
        super().__init__(attack_type, spawn_location)
        self._from_yaml(attack_type, spawn_location)
        self.drift_rate_lat = self.config["drift_rate_lat"]
        self.drift_rate_lon = self.config["drift_rate_lon"]


    def compute_spoofed_position(
            self, gps_receiver: GpsReceiver, elapsed_seconds: float
    ) -> tuple[float, float, float]:
        """Given a drone and the elapsed time, calculate the new spoofed location."""
        t = self.seconds_since_activation(elapsed_seconds)
        return (
            gps_receiver.lat + self.drift_rate_lat * t,
            gps_receiver.lon + self.drift_rate_lon * t,
            gps_receiver.alt,
        )
    

    def compute_spoofed_velocity(
            self, gps_receiver: GpsReceiver, elapsed_seconds: float
    ) -> tuple[float, float, float]:
        """The drift attack does not affect the drone's velocity"""
        return gps_receiver.get_velocity()