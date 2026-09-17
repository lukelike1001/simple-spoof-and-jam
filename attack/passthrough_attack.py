from __future__ import annotations

from attack.spoofing_attack import SpoofingAttack
from drone.gps_input_state import GpsInputState
from drone.gps_receiver import GpsReceiver


class PassthroughAttack(SpoofingAttack):
    ATTACK_TYPE = "passthrough"

    def __init__(self, attack_type: str, spawn_location: str):
        pass

    def apply(
        self,
        nominal: GpsInputState,
        receiver: GpsReceiver,
        elapsed_seconds: float,
    ) -> GpsInputState:
        """Passthrough delivers the nominal state unchanged (no spoofing)."""
        return nominal
