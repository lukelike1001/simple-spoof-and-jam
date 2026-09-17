import pytest
from unittest.mock import MagicMock
from drone.gps_receiver import GpsReceiver


@pytest.fixture
def receiver():
    r = GpsReceiver()
    r.update_position(35.9305, -84.3107, 50.0)
    r.update_velocity(1.0, 2.0, -0.5)
    return r


class TestGpsReceiver:

    def test_update_position(self, receiver):
        receiver.update_position(10.0, 20.0, 100.0)
        assert receiver.get_position() == (10.0, 20.0, 100.0)

    def test_update_velocity(self, receiver):
        receiver.update_velocity(3.0, 4.0, -1.0)
        assert receiver.get_velocity() == (3.0, 4.0, -1.0)

    def test_get_position_returns_set_values(self, receiver):
        assert receiver.get_position() == (35.9305, -84.3107, 50.0)

    def test_get_velocity_returns_set_values(self, receiver):
        assert receiver.get_velocity() == (1.0, 2.0, -0.5)

    def test_normalize_position(self, receiver):
        norm_lat, norm_lon, norm_alt = receiver.normalize_position(359305000, -843107000, 50000)
        assert norm_lat == pytest.approx(35.9305)
        assert norm_lon == pytest.approx(-84.3107)
        assert norm_alt == pytest.approx(50.0)

    def test_normalize_velocity(self, receiver):
        norm_vx, norm_vy, norm_vz = receiver.normalize_velocity(100, 200, -50)
        assert norm_vx == pytest.approx(1.0)
        assert norm_vy == pytest.approx(2.0)
        assert norm_vz == pytest.approx(-0.5)

    def test_get_signal_quality_params(self, receiver):
        params = receiver.get_signal_quality_params()
        assert isinstance(params["fix_type_3d"], int)
        assert isinstance(params["satellites_visible_count"], int)
        assert isinstance(params["hdop"], float)
        assert isinstance(params["vdop"], float)
        assert isinstance(params["speed_accuracy"], float)
        assert isinstance(params["horizontal_accuracy"], float)
        assert isinstance(params["vertical_accuracy"], float)

    def test_sync_updates_position_and_velocity_from_global_position_int(self, receiver):
        msg = MagicMock()
        msg.lat = 359305000
        msg.lon = -843107000
        msg.alt = 50000
        msg.relative_alt = 50000
        msg.vx = 100
        msg.vy = 200
        msg.vz = -50
        connection = MagicMock()
        connection.last_message.side_effect = (
            lambda name: msg if name == "GLOBAL_POSITION_INT" else None
        )

        receiver.sync_position_and_velocity_to_sitl(connection)

        assert receiver.get_position() == pytest.approx((35.9305, -84.3107, 50.0))
        assert receiver.get_velocity() == pytest.approx((1.0, 2.0, -0.5))
        assert receiver.relative_alt == pytest.approx(50.0)

    def test_sync_leaves_state_when_no_message_is_ready(self, receiver):
        connection = MagicMock()
        connection.last_message.return_value = None

        receiver.sync_position_and_velocity_to_sitl(connection)

        assert receiver.get_position() == pytest.approx((35.9305, -84.3107, 50.0))


class TestNominalGpsStateTruthTracking:

    def _receiver_with_reported(self):
        r = GpsReceiver()
        r.update_position(10.0, 20.0, 100.0)   # reported (EKF) values
        r.update_velocity(1.0, 2.0, -0.5)
        return r

    def test_uses_truth_position_and_horizontal_velocity_when_available(self):
        r = self._receiver_with_reported()
        r.truth_lat = 35.0
        r.truth_lon = -84.0
        r.truth_velocity_north = 3.0
        r.truth_velocity_east = 4.0
        s = r.nominal_gps_state()
        assert s.lat == 35.0 and s.lon == -84.0
        assert s.vn == 3.0 and s.ve == 4.0

    def test_alt_and_vd_stay_reported_even_when_truth_present(self):
        # No SIMSTATE altitude / no real truth vertical velocity exist.
        r = self._receiver_with_reported()
        r.truth_lat = 35.0
        r.truth_lon = -84.0
        r.truth_velocity_north = 3.0
        r.truth_velocity_east = 4.0
        r.truth_velocity_down = 0.0
        s = r.nominal_gps_state()
        assert s.alt == 100.0      # reported
        assert s.vd == -0.5        # reported vertical velocity, not the 0.0 placeholder

    def test_falls_back_to_reported_before_truth_is_synced(self):
        r = self._receiver_with_reported()  # truth_* still None from __init__
        s = r.nominal_gps_state()
        assert (s.lat, s.lon) == (10.0, 20.0)
        assert (s.vn, s.ve) == (1.0, 2.0)

    def test_quality_fields_unchanged(self):
        r = self._receiver_with_reported()
        r.truth_lat, r.truth_lon = 35.0, -84.0
        s = r.nominal_gps_state()
        q = r.signal_quality_params
        assert s.fix_type == q["fix_type_3d"]
        assert s.horizontal_accuracy == q["horizontal_accuracy"]
