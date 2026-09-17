import pytest
from unittest.mock import MagicMock

from attack.passthrough_attack import PassthroughAttack
from drone.gps_input_state import GpsInputState


def _nominal():
    return GpsInputState(
        lat=35.9305, lon=-84.3107, alt=50.0, vn=1.0, ve=2.0, vd=-0.5,
        fix_type=3, satellites_visible=12, hdop=1.0, vdop=1.0,
        horizontal_accuracy=0.5, vertical_accuracy=2.0, speed_accuracy=0.5,
    )


@pytest.fixture
def passthrough_attack():
    return PassthroughAttack("passthrough", "ornl")


class TestPassthroughAttack:

    def test_apply_returns_nominal_state_unchanged(self, passthrough_attack):
        nominal = _nominal()
        assert passthrough_attack.apply(nominal, MagicMock(), elapsed_seconds=10.0) is nominal
