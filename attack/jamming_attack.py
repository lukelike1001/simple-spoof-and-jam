from attack.gps_attack import GpsAttack


class JammingAttack(GpsAttack):
    """Withhold GPS_INPUT once altitude activation has fired."""

    ATTACK_TYPE = "jamming"

    def __init__(self, attack_type: str, spawn_location: str):
        super().__init__(attack_type, spawn_location)
        self._from_yaml(attack_type, spawn_location)
