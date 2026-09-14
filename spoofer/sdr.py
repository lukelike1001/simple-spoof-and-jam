from attack.gps_attack import GpsAttack
from communication.sitl_connection import SitlConnection
from drone.gps_input_state import GpsInputState
from drone.gps_receiver import GpsReceiver
from spoofer.sdr_config import SdrConfig
import time

class SoftwareDefinedRadio:

    def __init__(self, gps_attack: GpsAttack):
        self.config = SdrConfig.from_yaml()
        self.attack = gps_attack
    

    def activate_gps_attack(self, gps_receiver: GpsReceiver, connection: SitlConnection) -> None:
        """Run a GPS spoofing attack for the specified duration as defined in `self.config.attack_duration_seconds`
        Only called by GpsSpoofingSimulation after the `Drone`, `FlightEnvironment`, and the `SitlConnection have
        already been established."""

        start_time = time.monotonic()
        elapsed_seconds = 0.0
        interval_seconds = 1.0 / self.config.gps_input_rate_hz
        saw_armed = False

        while elapsed_seconds < self.config.attack_duration_seconds:
            elapsed_seconds = time.monotonic() - start_time
            connection.drain()
            armed = connection.poll_armed()
            if armed is True:
                saw_armed = True
            elif armed is False and saw_armed:
                print("Flight finished (disarmed).")
                break
            gps_receiver.sync_position_and_velocity_to_sitl(connection)

            nominal = gps_receiver.nominal_gps_state()
            if not self.attack.check_activation_altitude(gps_receiver, elapsed_seconds):
                # Before activation, deliver the authentic state untouched.
                state = nominal
            else:
                state = self.attack.apply(nominal, gps_receiver, elapsed_seconds)

            # A None state means the attack withholds GPS input (jamming).
            if state is not None:
                self.send_gps_input(state, connection)
            time.sleep(interval_seconds)

            # NOTE: time.sleep accumulates drift over time because it doesn't account for how long
            # send_gps_input took, and should be modified for future tests
    

    def send_gps_input(self, state: GpsInputState, connection: SitlConnection) -> None:
        """Send a single GPS_INPUT message from the effect-level GpsInputState
        returned by the attack's apply() call in `activate_gps_attack()`."""

        # NOTE: We can make later edits to modify the GPS to support spoofed time
        # in addition to just position and velocity
        seconds_since_gps_epoch = time.time() - self.config.gps_epoch_unix
        gps_week, seconds_into_week = divmod(seconds_since_gps_epoch, self.config.seconds_per_week)

        connection.mav.mav.gps_input_send(
            int(time.time() * 1e6),         # time_usec
            0,                              # gps_id
            0,                              # ignore_flags because every field below is valid
            int(seconds_into_week * 1000),  # time_week_ms
            int(gps_week),                  # time_week
            state.fix_type,                 # fix_type
            int(state.lat * 1e7),           # lat, degE7
            int(state.lon * 1e7),           # lon, degE7
            state.alt,                      # alt, m MSL
            state.hdop,
            state.vdop,
            state.vn,
            state.ve,
            state.vd,
            state.speed_accuracy,
            state.horizontal_accuracy,
            state.vertical_accuracy,
            state.satellites_visible,
            0,                          # yaw, 0 = unknown
        )
