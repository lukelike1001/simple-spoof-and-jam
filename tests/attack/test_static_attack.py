import pytest
from unittest.mock import MagicMock

from attack.static_attack import StaticAttack
from drone.gps_input_state import GpsInputState


QUALITY_FIELDS = (
    "fix_type", "satellites_visible", "hdop", "vdop",
    "horizontal_accuracy", "vertical_accuracy", "speed_accuracy",
)


def _nominal(vn=1.0, ve=2.0, vd=-0.5):
    return GpsInputState(
        lat=35.9305, lon=-84.3107, alt=25.0, vn=vn, ve=ve, vd=vd,
        fix_type=3, satellites_visible=12, hdop=1.0, vdop=1.0,
        horizontal_accuracy=0.5, vertical_accuracy=2.0, speed_accuracy=0.5,
    )


@pytest.fixture
def static_attack():
    return StaticAttack("static", "ornl")


@pytest.fixture
def receiver():
    return MagicMock()


class TestStaticAttack:

    def test_load_nonexistent_spawn_location_raises_key_error(self):
        with pytest.raises(KeyError):
            StaticAttack("static", "paris")

    def test_apply_returns_static_coords(self, static_attack, receiver):
        state = static_attack.apply(_nominal(), receiver, elapsed_seconds=10.0)
        assert state.lat == static_attack.static_lat
        assert state.lon == static_attack.static_lon
        assert state.alt == static_attack.static_alt

    def test_apply_returns_state_not_none(self, static_attack, receiver):
        assert static_attack.apply(_nominal(), receiver, elapsed_seconds=10.0) is not None

    def test_apply_leaves_velocity_unchanged(self, static_attack, receiver):
        nominal = _nominal()
        state = static_attack.apply(nominal, receiver, elapsed_seconds=10.0)
        assert (state.vn, state.ve, state.vd) == (nominal.vn, nominal.ve, nominal.vd)

    def test_apply_leaves_quality_fields_unchanged(self, static_attack, receiver):
        nominal = _nominal()
        state = static_attack.apply(nominal, receiver, elapsed_seconds=10.0)
        for field in QUALITY_FIELDS:
            assert getattr(state, field) == getattr(nominal, field)

    def test_activation_waits_until_cruise_altitude(self, static_attack, receiver):
        receiver.relative_alt = 5.0
        assert static_attack.check_activation_altitude(receiver, 0.0) is False
        receiver.relative_alt = 25.0
        assert static_attack.check_activation_altitude(receiver, 1.0) is False
        assert static_attack.check_activation_altitude(receiver, 6.0) is True
