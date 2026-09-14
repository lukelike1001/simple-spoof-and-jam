import pytest
from unittest.mock import MagicMock

from attack.degradation_attack import DegradationAttack
from drone.gps_input_state import GpsInputState


@pytest.fixture
def attack():
    a = DegradationAttack("degradation", "ornl")
    # Pin activation so seconds_since_activation == elapsed_seconds in tests.
    a.activated_at = 0.0
    return a


def _nominal():
    return GpsInputState(
        lat=35.9305, lon=-84.3107, alt=50.0, vn=1.0, ve=2.0, vd=-0.5,
        fix_type=3, satellites_visible=12, hdop=1.0, vdop=1.0,
        horizontal_accuracy=0.5, vertical_accuracy=2.0, speed_accuracy=0.5,
    )


CONTENT_FIELDS = ("lat", "lon", "alt", "vn", "ve", "vd")
QUALITY_FIELDS = (
    "fix_type", "satellites_visible", "hdop", "vdop",
    "horizontal_accuracy", "vertical_accuracy", "speed_accuracy",
)


class TestDegradationAttack:

    def test_load_nonexistent_spawn_location_raises_key_error(self):
        with pytest.raises(KeyError):
            DegradationAttack("degradation", "paris")

    def test_never_returns_none(self, attack):
        assert attack.apply(_nominal(), MagicMock(), elapsed_seconds=1000.0) is not None

    def test_preserves_position_and_velocity_content(self, attack):
        nominal = _nominal()
        for t in (0.0, 5.0, 30.0, 100.0):
            state = attack.apply(nominal, MagicMock(), elapsed_seconds=t)
            for field in CONTENT_FIELDS:
                assert getattr(state, field) == getattr(nominal, field)

    def test_alpha_zero_is_nominal_quality(self, attack):
        nominal = _nominal()
        state = attack.apply(nominal, MagicMock(), elapsed_seconds=0.0)
        for field in QUALITY_FIELDS:
            assert getattr(state, field) == pytest.approx(getattr(nominal, field))

    def test_only_intended_fields_change(self, attack):
        nominal = _nominal()
        state = attack.apply(nominal, MagicMock(), elapsed_seconds=15.0)
        # Every changed field must be a quality/availability field.
        for field in nominal.__dataclass_fields__:
            if getattr(state, field) != getattr(nominal, field):
                assert field in QUALITY_FIELDS

    def test_continuous_quality_degrades_monotonically(self, attack):
        nominal = _nominal()
        times = [0.0, 5.0, 10.0, 20.0, 30.0]
        states = [attack.apply(nominal, MagicMock(), elapsed_seconds=t) for t in times]
        # accuracies and DOPs are non-decreasing (worse); sats non-increasing.
        for worse in ("horizontal_accuracy", "vertical_accuracy", "speed_accuracy", "hdop", "vdop"):
            vals = [getattr(s, worse) for s in states]
            assert vals == sorted(vals)
        sats = [s.satellites_visible for s in states]
        assert sats == sorted(sats, reverse=True)

    def test_fix_type_holds_nominal_until_full_severity(self, attack):
        nominal = _nominal()
        assert attack.apply(nominal, MagicMock(), elapsed_seconds=0.0).fix_type == 3
        assert attack.apply(nominal, MagicMock(), elapsed_seconds=29.9).fix_type == 3
        # ramp_seconds default is 30 -> alpha == 1 at t >= 30 -> downgrade to 2D.
        assert attack.apply(nominal, MagicMock(), elapsed_seconds=30.0).fix_type == attack.worst["fix_type"]
        assert attack.apply(nominal, MagicMock(), elapsed_seconds=60.0).fix_type == 2

    def test_full_severity_hits_configured_worst_values(self, attack):
        nominal = _nominal()
        state = attack.apply(nominal, MagicMock(), elapsed_seconds=100.0)
        assert state.horizontal_accuracy == pytest.approx(attack.worst["horizontal_accuracy"])
        assert state.vertical_accuracy == pytest.approx(attack.worst["vertical_accuracy"])
        assert state.speed_accuracy == pytest.approx(attack.worst["speed_accuracy"])
        assert state.satellites_visible == attack.worst["satellites_visible"]
