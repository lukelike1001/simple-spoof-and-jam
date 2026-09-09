from unittest.mock import MagicMock

from attack.jamming_attack import JammingAttack
from attack.passthrough_attack import PassthroughAttack


def _receiver(alt: float):
    r = MagicMock()
    r.get_position.return_value = (35.9305, -84.3107, alt)
    return r


class TestCheckActivationAltitude:

    def test_passthrough_without_activation_alt_is_immediately_active(self):
        attack = PassthroughAttack("passthrough", "ornl")
        assert attack.check_activation_altitude(_receiver(0.0), 0.0) is True

    def test_stays_inactive_below_activation_altitude(self):
        attack = JammingAttack("jamming", "ornl")
        assert attack.check_activation_altitude(_receiver(5.0), 0.0) is False
        assert attack.check_activation_altitude(_receiver(5.0), 30.0) is False

    def test_fires_after_delay_once_altitude_is_reached(self):
        attack = JammingAttack("jamming", "ornl")
        receiver = _receiver(25.0)
        assert attack.check_activation_altitude(receiver, 0.0) is False
        assert attack.check_activation_altitude(receiver, 5.0) is True
