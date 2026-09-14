from contextlib import ExitStack
from dataclasses import replace
from unittest.mock import MagicMock, patch

from attack.jamming_attack import JammingAttack
from drone.gps_input_state import GpsInputState
from spoofer.sdr import SoftwareDefinedRadio


def _nominal():
    return GpsInputState(
        lat=35.9305, lon=-84.3107, alt=25.0, vn=0.0, ve=0.0, vd=0.0,
        fix_type=3, satellites_visible=12, hdop=1.0, vdop=1.0,
        horizontal_accuracy=0.5, vertical_accuracy=2.0, speed_accuracy=0.5,
    )


def _run_loop(activation: bool):
    """Run the injection loop once with activation forced on/off; return the
    patched send_gps_input mock."""
    attack = JammingAttack("jamming", "ornl")
    sdr = SoftwareDefinedRadio(attack)
    sdr.config = replace(sdr.config, attack_duration_seconds=0.5)
    clock = {"t": 0.0}
    receiver = MagicMock()
    receiver.nominal_gps_state.return_value = _nominal()
    connection = MagicMock()
    connection.poll_armed.return_value = None

    with ExitStack() as stack:
        send_gps_input = stack.enter_context(patch.object(sdr, "send_gps_input"))
        stack.enter_context(patch.object(attack, "check_activation_altitude", return_value=activation))
        stack.enter_context(patch("spoofer.sdr.time.monotonic", side_effect=lambda: clock["t"]))
        stack.enter_context(patch(
            "spoofer.sdr.time.sleep",
            side_effect=lambda s: clock.__setitem__("t", clock["t"] + s),
        ))
        sdr.activate_gps_attack(receiver, connection)
    return send_gps_input


class TestJammingAttack:

    def test_apply_returns_none(self):
        attack = JammingAttack("jamming", "ornl")
        assert attack.apply(_nominal(), MagicMock(), elapsed_seconds=10.0) is None

    def test_no_gps_input_sent_when_activation_has_fired(self):
        send_gps_input = _run_loop(activation=True)
        send_gps_input.assert_not_called()

    def test_gps_input_sent_before_activation(self):
        send_gps_input = _run_loop(activation=False)
        assert send_gps_input.call_count > 0
