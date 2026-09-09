from attack.spoofing_attack import SpoofingAttack
from drone.gps_receiver import GpsReceiver

class PassthroughAttack(SpoofingAttack):
    ATTACK_TYPE = "passthrough"

    def __init__(self, attack_type: str, spawn_location: str):
        pass


    def compute_spoofed_position(
            self, gps_receiver: GpsReceiver, elapsed_seconds: float
    ) -> tuple[float, float, float]:
        """Given a drone and the elapsed time, return the coordinates without any spoofing."""
        return gps_receiver.get_position()
    

    def compute_spoofed_velocity(
            self, gps_receiver: GpsReceiver, elapsed_seconds: float
    ) -> tuple[float, float, float]:
        """By definition, passthrough does not affect the drone's velocity"""
        return gps_receiver.get_velocity()