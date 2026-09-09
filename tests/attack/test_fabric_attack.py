import pytest
from unittest.mock import MagicMock

from attack.fabric_attack import FabricAttack


@pytest.fixture
def fabric_attack():
    return FabricAttack("fabric", "ornl")


@pytest.fixture
def receiver():
    r = MagicMock()
    r.get_velocity.return_value = (1.0, 2.0, -0.5)
    r.get_position.return_value = (35.9305, -84.3107, 25.0)
    return r


class TestFabricAttack:

    def test_load_nonexistent_spawn_location_raises_key_error(self):
        with pytest.raises(KeyError):
            FabricAttack("fabric", "paris")

    def test_compute_spoofed_position_returns_fabric_coords(self, fabric_attack, receiver):
        lat, lon, alt = fabric_attack.compute_spoofed_position(receiver, elapsed_seconds=10.0)
        assert lat == fabric_attack.fabric_lat
        assert lon == fabric_attack.fabric_lon
        assert alt == fabric_attack.fabric_alt

    def test_compute_spoofed_velocity_returns_receiver_velocity_unchanged(
        self, fabric_attack, receiver
    ):
        result = fabric_attack.compute_spoofed_velocity(receiver, elapsed_seconds=10.0)
        assert result == receiver.get_velocity()

    def test_activation_waits_until_cruise_altitude(self, fabric_attack, receiver):
        receiver.get_position.return_value = (35.9305, -84.3107, 5.0)
        assert fabric_attack.check_activation_altitude(receiver, 0.0) is False
        receiver.get_position.return_value = (35.9305, -84.3107, 25.0)
        assert fabric_attack.check_activation_altitude(receiver, 1.0) is False
        assert fabric_attack.check_activation_altitude(receiver, 6.0) is True
