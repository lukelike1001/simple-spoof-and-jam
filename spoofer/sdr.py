import math
import time

from attack.gps_attack import GpsAttack
from communication.sitl_connection import SitlConnection
from drone.gps_input_state import GpsInputState
from drone.gps_receiver import GpsReceiver
from spoofer.sdr_config import SdrConfig

METRES_PER_DEG_LAT = 111_320.0


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _horizontal_distance_m(lat_a: float, lon_a: float, lat_b: float, lon_b: float) -> float:
    """Equirectangular horizontal distance (m) between two WGS84 points, using
    the reference latitude `lat_b` for the longitude scaling."""
    dnorth = (lat_a - lat_b) * METRES_PER_DEG_LAT
    deast = (lon_a - lon_b) * METRES_PER_DEG_LAT * math.cos(math.radians(lat_b))
    return math.hypot(dnorth, deast)


class SoftwareDefinedRadio:

    def __init__(self, gps_attack: GpsAttack):
        self.config = SdrConfig.from_yaml()
        self.attack = gps_attack
        # Per-tick injection log, populated by activate_gps_attack(). Records
        # what SimpleSpoofAndJam *injects* (or withholds), independent of what
        # ArduPilot later accepts. See simulation/injection_log.py for the schema.
        self.injection_records: list[dict] = []


    def activate_gps_attack(self, gps_receiver: GpsReceiver, connection: SitlConnection) -> None:
        """Run a GPS spoofing attack for the specified duration as defined in `self.config.attack_duration_seconds`
        Only called by GpsSpoofingSimulation after the `Drone`, `FlightEnvironment`, and the `SitlConnection have
        already been established."""

        start_time = time.monotonic()
        elapsed_seconds = 0.0
        interval_seconds = 1.0 / self.config.gps_input_rate_hz
        saw_armed = False
        self.injection_records = []

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
            activated = self.attack.check_activation_altitude(gps_receiver, elapsed_seconds)
            if not activated:
                # Before activation, deliver the authentic state untouched.
                state = nominal
            else:
                state = self.attack.apply(nominal, gps_receiver, elapsed_seconds)

            # A None state means the attack withholds GPS input (jamming).
            if state is not None:
                self.send_gps_input(state, connection)

            self._record_injection(elapsed_seconds, activated, state, gps_receiver)
            time.sleep(interval_seconds)

            # NOTE: time.sleep accumulates drift over time because it doesn't account for how long
            # send_gps_input took, and should be modified for future tests

    def _record_injection(
        self,
        elapsed_seconds: float,
        activated: bool,
        state: GpsInputState | None,
        gps_receiver: GpsReceiver,
    ) -> None:
        """Append one injection-log row for this tick.

        `e_inject_h_m` answers: did SimpleSpoofAndJam deliberately inject false
        navigation *content*? It is the horizontal distance between the injected
        position and SITL truth. When GPS is withheld (state is None), there is
        no injected content, so navigation fields and e_inject_h_m are NaN
        (gps_sent=0) rather than invented.
        """
        nan = float("nan")
        truth_lat = gps_receiver.truth_lat
        truth_lon = gps_receiver.truth_lon
        # SIMSTATE (our in-loop truth source) carries lat/lng but no altitude, so
        # a truth altitude is not honestly available here. It exists only in the
        # DataFlash SIM.Alt field and is left NaN in this log by design.
        truth_alt = getattr(gps_receiver, "truth_alt", None)
        gps_sent = state is not None

        if gps_sent:
            inj = dict(
                inj_lat=state.lat, inj_lon=state.lon, inj_alt=state.alt,
                inj_vn=state.vn, inj_ve=state.ve, inj_vd=state.vd,
                fix_type=state.fix_type,
                h_acc=state.horizontal_accuracy,
                v_acc=state.vertical_accuracy,
                s_acc=state.speed_accuracy,
            )
        else:
            inj = dict(
                inj_lat=nan, inj_lon=nan, inj_alt=nan,
                inj_vn=nan, inj_ve=nan, inj_vd=nan,
                fix_type=nan, h_acc=nan, v_acc=nan, s_acc=nan,
            )

        if gps_sent and _is_number(truth_lat) and _is_number(truth_lon):
            e_inject_h_m = _horizontal_distance_m(state.lat, state.lon, truth_lat, truth_lon)
        else:
            e_inject_h_m = nan

        self.injection_records.append(dict(
            elapsed_s=elapsed_seconds,
            activated=int(bool(activated)),
            gps_sent=int(gps_sent),
            **inj,
            truth_lat=truth_lat if _is_number(truth_lat) else nan,
            truth_lon=truth_lon if _is_number(truth_lon) else nan,
            truth_alt=truth_alt if _is_number(truth_alt) else nan,
            e_inject_h_m=e_inject_h_m,
        ))


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
