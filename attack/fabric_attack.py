from attack.spoofing_attack import SpoofingAttack

class FabricAttack(SpoofingAttack):
    # this is an abstract class that you should NOT call

    def __init__(self, attack_type: str, spawn_location: str):
        self._from_yaml(attack_type, spawn_location)
        self.fabric_lat = self.config["fabric_lat"]
        self.fabric_lon = self.config["fabric_lon"]
        self.fabric_alt = self.config["fabric_alt"]