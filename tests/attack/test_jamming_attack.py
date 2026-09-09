from dataclasses import replace
from unittest.mock import MagicMock, patch

from attack.jamming_attack import JammingAttack
from spoofer.sdr import SoftwareDefinedRadio


class TestJammingAttack:

    def test_does_not_emit_gps_input_when_activation_has_fired(self):
        attack = JammingAttack("jamming", "ornl")
        sdr = SoftwareDefinedRadio(attack)
        sdr.config = replace(sdr.config, attack_duration_seconds=0.5)
        clock = {"t": 0.0}
        receiver = MagicMock()
        receiver.get_position.return_value = (35.9305, -84.3107, 25.0)
        receiver.get_velocity.return_value = (0.0, 0.0, 0.0)
        connection = MagicMock()
        connection.poll_armed.return_value = None

        with patch.object(attack, "check_activation_altitude", return_value=True), \
             patch.object(sdr, "send_gps_input") as send_gps_input, \
             patch.object(sdr, "jam") as jam, \
             patch("spoofer.sdr.time.monotonic", side_effect=lambda: clock["t"]), \
             patch("spoofer.sdr.time.sleep", side_effect=lambda seconds: clock.__setitem__("t", clock["t"] + seconds)):
            sdr.activate_gps_attack(receiver, connection)

        send_gps_input.assert_not_called()
        assert jam.call_count > 0

    def test_passthrough_gps_input_before_activation(self):
        attack = JammingAttack("jamming", "ornl")
        sdr = SoftwareDefinedRadio(attack)
        sdr.config = replace(sdr.config, attack_duration_seconds=0.5)
        clock = {"t": 0.0}
        receiver = MagicMock()
        receiver.get_position.return_value = (35.9305, -84.3107, 5.0)
        receiver.get_velocity.return_value = (0.0, 0.0, 0.0)
        connection = MagicMock()
        connection.poll_armed.return_value = None

        with patch.object(sdr, "send_gps_input") as send_gps_input, \
             patch.object(sdr, "jam") as jam, \
             patch("spoofer.sdr.time.monotonic", side_effect=lambda: clock["t"]), \
             patch("spoofer.sdr.time.sleep", side_effect=lambda seconds: clock.__setitem__("t", clock["t"] + seconds)):
            sdr.activate_gps_attack(receiver, connection)

        assert send_gps_input.call_count > 0
        jam.assert_not_called()
