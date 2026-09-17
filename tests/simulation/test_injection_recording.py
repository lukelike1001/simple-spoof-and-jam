import math
from unittest.mock import MagicMock

import pytest

from attack.complete_loss_attack import CompleteLossAttack
from attack.static_attack import StaticAttack
from drone.gps_input_state import GpsInputState
from spoofer.sdr import METRES_PER_DEG_LAT, SoftwareDefinedRadio


def _nominal(lat=35.9305, lon=-84.3107):
    return GpsInputState(
        lat=lat, lon=lon, alt=50.0, vn=1.0, ve=2.0, vd=-0.5,
        fix_type=3, satellites_visible=12, hdop=1.0, vdop=1.0,
        horizontal_accuracy=0.5, vertical_accuracy=2.0, speed_accuracy=0.5,
    )


@pytest.fixture
def sdr():
    return SoftwareDefinedRadio(StaticAttack("static", "ornl"))


def _receiver(truth_lat=35.9300, truth_lon=-84.3100):
    r = MagicMock()
    r.truth_lat = truth_lat
    r.truth_lon = truth_lon
    return r


class TestRecordInjection:

    def test_sent_spoof_records_content_and_e_inject(self, sdr):
        state = _nominal(lat=36.0, lon=-84.0)
        receiver = _receiver(truth_lat=35.9, truth_lon=-84.3)
        sdr._record_injection(1.0, activated=True, state=state, gps_receiver=receiver)
        row = sdr.injection_records[-1]
        assert row["gps_sent"] == 1
        assert row["activated"] == 1
        assert row["inj_lat"] == 36.0 and row["inj_lon"] == -84.0
        expected = math.hypot(
            (36.0 - 35.9) * METRES_PER_DEG_LAT,
            (-84.0 + 84.3) * METRES_PER_DEG_LAT * math.cos(math.radians(35.9)),
        )
        assert row["e_inject_h_m"] == pytest.approx(expected)

    def test_withheld_records_nan_and_not_sent(self, sdr):
        receiver = _receiver()
        sdr._record_injection(1.0, activated=True, state=None, gps_receiver=receiver)
        row = sdr.injection_records[-1]
        assert row["gps_sent"] == 0
        assert math.isnan(row["inj_lat"])
        assert math.isnan(row["e_inject_h_m"])

    def test_e_inject_nan_when_truth_unavailable(self, sdr):
        receiver = MagicMock()
        receiver.truth_lat = None
        receiver.truth_lon = None
        sdr._record_injection(1.0, activated=False, state=_nominal(), gps_receiver=receiver)
        row = sdr.injection_records[-1]
        assert row["gps_sent"] == 1
        assert math.isnan(row["e_inject_h_m"])

    def test_truth_alt_is_nan_when_unavailable(self, sdr):
        # SIMSTATE carries no altitude, so truth_alt is honestly NaN.
        receiver = _receiver()
        sdr._record_injection(1.0, activated=True, state=_nominal(), gps_receiver=receiver)
        assert math.isnan(sdr.injection_records[-1]["truth_alt"])


class TestCompleteLossRecording:

    def test_records_gps_sent_zero(self):
        sdr = SoftwareDefinedRadio(CompleteLossAttack("complete_loss", "ornl"))
        sdr._record_injection(1.0, activated=True, state=None, gps_receiver=_receiver())
        assert sdr.injection_records[-1]["gps_sent"] == 0
