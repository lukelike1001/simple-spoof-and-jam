from __future__ import annotations

from attack.gps_attack import GpsAttack


class JammingAttack(GpsAttack):
    """Common base for effect-level jamming.

    Jamming manipulates the *quality or availability* of the authentic
    navigation solution. It never constructs an attacker-selected trajectory;
    any navigation content it delivers is derived from the nominal/authentic
    GPS state. Concrete models implement ``apply``:

        J(nominal) -> degraded-authentic GpsInputState  OR  None

    Returning None denies GPS entirely (complete loss); returning a state
    delivers authentic content at degraded quality.
    """

    def __init__(self, attack_type: str, spawn_location: str):
        super().__init__(attack_type, spawn_location)
        self._from_yaml(attack_type, spawn_location)
