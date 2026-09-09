class JammingAttack:
    """Stops GPS_INPUT while active. Sibling of SpoofingAttack, not a subclass."""

    def __init__(self, attack_type: str, spawn_location: str):
        self.active = True
