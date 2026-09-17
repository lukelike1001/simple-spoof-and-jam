import math

import pytest
from unittest.mock import MagicMock

from attack.drift_attack import METRES_PER_DEG_LAT, DriftAttack
from drone.gps_input_state import GpsInputState


@pytest.fixture
def drift_attack():
    return DriftAttack("drift", "ornl")


@pytest.fixture
def receiver():
    # No truth_* values set to numbers, so apply() falls back to the nominal state.
    r = MagicMock()
    r.truth_lat = None
    r.truth_lon = None
    r.truth_velocity_north = None
    r.truth_velocity_east = None
    r.truth_velocity_down = None
    return r


def _nominal(lat=35.9305, lon=-84.3107, alt=50.0, vn=1.0, ve=2.0, vd=-0.5):
    return GpsInputState(
        lat=lat, lon=lon, alt=alt, vn=vn, ve=ve, vd=vd,
        fix_type=3, satellites_visible=12, hdop=1.0, vdop=1.0,
        horizontal_accuracy=0.5, vertical_accuracy=2.0, speed_accuracy=0.5,
    )


class TestDriftAttack:

    def test_load_nonexistent_spawn_location_raises_key_error(self):
        with pytest.raises(KeyError):
            DriftAttack("drift", "paris")

    def test_apply_position_applies_metre_drift_rates(self, drift_attack, receiver):
        elapsed = 10.0
        nominal = _nominal()
        state = drift_attack.apply(nominal, receiver, elapsed)
        dlat = drift_attack.drift_rate_north * elapsed / METRES_PER_DEG_LAT
        dlon = drift_attack.drift_rate_east * elapsed / (
            METRES_PER_DEG_LAT * math.cos(math.radians(nominal.lat))
        )
        assert state.lat == pytest.approx(nominal.lat + dlat)
        assert state.lon == pytest.approx(nominal.lon + dlon)
        assert state.alt == nominal.alt
        north_m = (state.lat - nominal.lat) * METRES_PER_DEG_LAT
        east_m = (state.lon - nominal.lon) * METRES_PER_DEG_LAT * math.cos(
            math.radians(nominal.lat)
        )
        assert north_m == pytest.approx(drift_attack.drift_rate_north * elapsed)
        assert east_m == pytest.approx(drift_attack.drift_rate_east * elapsed)

    def test_apply_velocity_adds_drift_rates(self, drift_attack, receiver):
        nominal = _nominal()
        state = drift_attack.apply(nominal, receiver, elapsed_seconds=10.0)
        assert state.vn == pytest.approx(1.0 + drift_attack.drift_rate_north)
        assert state.ve == pytest.approx(2.0 + drift_attack.drift_rate_east)
        assert state.vd == pytest.approx(-0.5)

    def test_apply_uses_truth_position_when_available(self, drift_attack, receiver):
        receiver.truth_lat = 36.0
        receiver.truth_lon = -84.0
        nominal = _nominal(lat=1.0, lon=1.0)
        state = drift_attack.apply(nominal, receiver, elapsed_seconds=0.0)
        assert state.lat == pytest.approx(36.0)
        assert state.lon == pytest.approx(-84.0)

    def test_apply_returns_state_not_none(self, drift_attack, receiver):
        assert drift_attack.apply(_nominal(), receiver, elapsed_seconds=10.0) is not None

    def test_apply_leaves_quality_fields_unchanged(self, drift_attack, receiver):
        nominal = _nominal()
        state = drift_attack.apply(nominal, receiver, elapsed_seconds=10.0)
        for field in (
            "fix_type", "satellites_visible", "hdop", "vdop",
            "horizontal_accuracy", "vertical_accuracy", "speed_accuracy",
        ):
            assert getattr(state, field) == getattr(nominal, field)

    def test_apply_changes_only_navigation_content_fields(self, drift_attack, receiver):
        nominal = _nominal()
        state = drift_attack.apply(nominal, receiver, elapsed_seconds=10.0)
        for field in nominal.__dataclass_fields__:
            if getattr(state, field) != getattr(nominal, field):
                assert field in ("lat", "lon", "alt", "vn", "ve", "vd")
