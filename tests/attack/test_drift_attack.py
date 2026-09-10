import math

import pytest
from unittest.mock import MagicMock

from attack.drift_attack import METRES_PER_DEG_LAT, DriftAttack


@pytest.fixture
def drift_attack():
    return DriftAttack("drift", "ornl")


@pytest.fixture
def receiver():
    r = MagicMock()
    r.lat = 35.9305
    r.lon = -84.3107
    r.alt = 50.0
    r.get_velocity.return_value = (1.0, 2.0, -0.5)
    return r


class TestDriftAttack:

    def test_load_nonexistent_spawn_location_raises_key_error(self):
        with pytest.raises(KeyError):
            DriftAttack("drift", "paris")

    def test_compute_spoofed_position_applies_metre_drift_rates(self, drift_attack, receiver):
        elapsed = 10.0
        lat, lon, alt = drift_attack.compute_spoofed_position(receiver, elapsed)
        dlat = drift_attack.drift_rate_north * elapsed / METRES_PER_DEG_LAT
        dlon = drift_attack.drift_rate_east * elapsed / (
            METRES_PER_DEG_LAT * math.cos(math.radians(receiver.lat))
        )
        assert lat == pytest.approx(receiver.lat + dlat)
        assert lon == pytest.approx(receiver.lon + dlon)
        assert alt == receiver.alt
        north_m = (lat - receiver.lat) * METRES_PER_DEG_LAT
        east_m = (lon - receiver.lon) * METRES_PER_DEG_LAT * math.cos(
            math.radians(receiver.lat)
        )
        assert north_m == pytest.approx(drift_attack.drift_rate_north * elapsed)
        assert east_m == pytest.approx(drift_attack.drift_rate_east * elapsed)

    def test_compute_spoofed_velocity_adds_drift_rates(self, drift_attack, receiver):
        vn, ve, vd = drift_attack.compute_spoofed_velocity(receiver, elapsed_seconds=10.0)
        assert vn == pytest.approx(1.0 + drift_attack.drift_rate_north)
        assert ve == pytest.approx(2.0 + drift_attack.drift_rate_east)
        assert vd == pytest.approx(-0.5)
