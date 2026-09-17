from __future__ import annotations

from dataclasses import replace

from attack.jamming_attack import JammingAttack
from drone.gps_input_state import GpsInputState
from drone.gps_receiver import GpsReceiver


class DegradationAttack(JammingAttack):
    """Partial effect-level jamming: progressively degrade GPS *quality*
    while leaving the navigation *content* authentic.

    Severity ramps deterministically from activation:

        alpha(t) = clamp(seconds_since_activation / ramp_seconds, 0, 1)

    Continuous quality fields interpolate monotonically from their nominal
    values toward configured worst values. fix_type stays nominal through the
    ramp and downgrades to the configured degraded endpoint (3D -> 2D) only at
    full severity (alpha == 1).

    Position (lat/lon/alt) and velocity (vn/ve/vd) are copied straight from the
    nominal state: this attack never selects a false trajectory and always
    returns a GpsInputState (never None).

    NOTE (experimental distinction): if ArduPilot's estimated position
    subsequently drifts because the degraded GPS is down-weighted or rejected
    by the EKF, that drift is an emergent estimator response. It is NOT
    navigation content selected or injected by DegradationAttack. Jamming can
    cause navigation error without the attacker selecting what that erroneous
    position should be; spoofing explicitly selects the erroneous content.
    """

    ATTACK_TYPE = "degradation"

    def __init__(self, attack_type: str, spawn_location: str):
        super().__init__(attack_type, spawn_location)
        self.ramp_seconds = self.config["ramp_seconds"]
        self.worst = self.config["worst"]

    def apply(
        self,
        nominal: GpsInputState,
        receiver: GpsReceiver,
        elapsed_seconds: float,
    ) -> GpsInputState:
        alpha = self._severity(self.seconds_since_activation(elapsed_seconds))

        def toward(nominal_value: float, worst_value: float) -> float:
            """Monotonic interpolation nominal -> worst as alpha goes 0 -> 1."""
            return nominal_value + alpha * (worst_value - nominal_value)

        # fix_type is discrete: hold nominal through the ramp, downgrade at full
        # severity only. (Primary availability lever alongside the accuracies.)
        fix_type = nominal.fix_type if alpha < 1.0 else self.worst["fix_type"]

        return replace(
            nominal,
            # primary behavioral fields (drive ArduPilot's EKF fusion / availability)
            horizontal_accuracy=toward(nominal.horizontal_accuracy, self.worst["horizontal_accuracy"]),
            vertical_accuracy=toward(nominal.vertical_accuracy, self.worst["vertical_accuracy"]),
            speed_accuracy=toward(nominal.speed_accuracy, self.worst["speed_accuracy"]),
            fix_type=fix_type,
            # secondary consistency fields (coherent degraded-GPS state; not the
            # in-flight driver of EKF behavior under the GPS_INPUT interface)
            hdop=toward(nominal.hdop, self.worst["hdop"]),
            vdop=toward(nominal.vdop, self.worst["vdop"]),
            satellites_visible=round(toward(nominal.satellites_visible, self.worst["satellites_visible"])),
        )

    def _severity(self, t: float) -> float:
        if self.ramp_seconds <= 0:
            return 1.0
        return max(0.0, min(1.0, t / self.ramp_seconds))
