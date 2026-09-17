import pytest
from unittest.mock import MagicMock

from attack.fabric_attack import FabricAttack
from drone.gps_input_state import GpsInputState


def _nominal(lat=35.9305, lon=-84.3107, alt=25.0, vn=1.0, ve=2.0, vd=-0.5):
    return GpsInputState(
        lat=lat, lon=lon, alt=alt, vn=vn, ve=ve, vd=vd,
        fix_type=3, satellites_visible=12, hdop=1.0, vdop=1.0,
        horizontal_accuracy=0.5, vertical_accuracy=2.0, speed_accuracy=0.5,
    )


@pytest.fixture
def fabric_attack():
    return FabricAttack("fabric", "ornl")


@pytest.fixture
def receiver():
    return MagicMock()


class TestFabricAttack:

    def test_load_nonexistent_spawn_location_raises_key_error(self):
        with pytest.raises(KeyError):
            FabricAttack("fabric", "paris")

    def test_apply_returns_fabric_coords(self, fabric_attack, receiver):
        nominal = _nominal()
        state = fabric_attack.apply(nominal, receiver, elapsed_seconds=10.0)
        assert state.lat == fabric_attack.fabric_lat
        assert state.lon == fabric_attack.fabric_lon
        assert state.alt == fabric_attack.fabric_alt

    def test_apply_leaves_velocity_unchanged(self, fabric_attack, receiver):
        nominal = _nominal()
        state = fabric_attack.apply(nominal, receiver, elapsed_seconds=10.0)
        assert (state.vn, state.ve, state.vd) == (nominal.vn, nominal.ve, nominal.vd)

    def test_apply_leaves_quality_fields_unchanged(self, fabric_attack, receiver):
        nominal = _nominal()
        state = fabric_attack.apply(nominal, receiver, elapsed_seconds=10.0)
        assert state.fix_type == nominal.fix_type
        assert state.satellites_visible == nominal.satellites_visible
        assert state.hdop == nominal.hdop

    def test_activation_waits_until_cruise_altitude(self, fabric_attack, receiver):
        receiver.relative_alt = 5.0
        assert fabric_attack.check_activation_altitude(receiver, 0.0) is False
        receiver.relative_alt = 25.0
        assert fabric_attack.check_activation_altitude(receiver, 1.0) is False
        assert fabric_attack.check_activation_altitude(receiver, 6.0) is True
