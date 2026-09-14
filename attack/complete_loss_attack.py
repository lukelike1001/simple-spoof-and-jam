from __future__ import annotations

from attack.jamming_attack import JammingAttack
from drone.gps_input_state import GpsInputState
from drone.gps_receiver import GpsReceiver


class CompleteLossAttack(JammingAttack):
    """Complete denial of usable GPS input: J_loss(x) = None.

    Once activation has fired, no GPS_INPUT is delivered, so ArduPilot's
    MAVLink GPS backend loses lock. This is the previous JammingAttack
    behavior, preserved unchanged.
    """

    ATTACK_TYPE = "complete_loss"

    def apply(
        self,
        nominal: GpsInputState,
        receiver: GpsReceiver,
        elapsed_seconds: float,
    ) -> None:
        return None
