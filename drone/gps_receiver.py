import math
import time
from pathlib import Path

import yaml

from communication.sitl_connection import SitlConnection
from drone.gps_input_state import GpsInputState

GPS_RECEIVER_CONFIG_PATH = Path(__file__).parent / "configs" / "gps_receiver_params.yaml"

class GpsReceiver:
    """Software representation of the drone's GPS receiver, which stores
    its position and velocity value read from GLOBAL_POSITION_INT.

    Velocity is in the NED frame (m/s), matching GPS_INPUT's vn/ve/vd fields.
    `alt` is height above mean sea level
    """

    lat: float
    lon: float
    alt: float
    velocity_north: float
    velocity_east: float
    velocity_down: float

    def __init__(self, config_path: Path = GPS_RECEIVER_CONFIG_PATH):
        """Initialization the normalization constants and the initial position/velocity"""
        self._from_yaml(config_path)
        self.relative_alt = 0.0
        self.truth_lat = None
        self.truth_lon = None
        self.truth_velocity_north = None
        self.truth_velocity_east = None
        self.truth_velocity_down = None
        self._truth_time = None


    def _from_yaml(self, config_path: Path) -> None:
        """Load the config from YAML and store the signal and """
        with config_path.open() as file:
            data = yaml.safe_load(file)
        self.signal_quality_params = data["signal_quality_params"]
        self.norms = data["norm_params"]


    def update_position(self, new_lat: float, new_lon: float, new_alt: float):
        """Helper method that updates the drone's new position"""
        self.lat = new_lat
        self.lon = new_lon
        self.alt = new_alt


    def update_velocity(self, new_velocity_north: float,
                        new_velocity_east: float, new_velocity_down: float):
        """Helper method that updates the drone's new NED velocity"""
        self.velocity_north = new_velocity_north
        self.velocity_east = new_velocity_east
        self.velocity_down = new_velocity_down


    def get_position(self):
        """Returns the drone's current position"""
        return (self.lat, self.lon, self.alt)
    

    def get_velocity(self):
        """Returns the drone's current velocity NED (north, east, down)"""
        return (self.velocity_north, self.velocity_east, self.velocity_down)
    

    def normalize_position(self, lat: float, lon: float, alt: float) -> tuple[float, float, float]:
        """Normalize the position based on pre-set normalization factors"""
        norm_lat = lat / self.norms["lat_factor"]
        norm_lon = lon / self.norms["lon_factor"]
        norm_alt = alt / self.norms["alt_factor"]
        return (norm_lat, norm_lon, norm_alt)
    
    
    def normalize_velocity(self, vx: float, vy: float, vz: float) -> tuple[float, float, float]:
        """Normalize the velocities based on pre-set normalization factors"""
        norm_vx = vx / self.norms["vx_factor"]
        norm_vy = vy / self.norms["vy_factor"]
        norm_vz = vz / self.norms["vz_factor"]
        return (norm_vx, norm_vy, norm_vz)
    
    
    def sync_position_and_velocity_to_sitl(self, connection: SitlConnection):
        """Update from the last drained GLOBAL_POSITION_INT and SITL SIMSTATE."""
        msg = connection.last_message("GLOBAL_POSITION_INT")
        if msg is not None and not (msg.lat == 0 and msg.lon == 0):
            # IMPORTANT: Don't remove this "Null Island" fix.
            # "Null Island": the EKF hasn't ingested a GPS fix yet and has
            # no origin set, so GLOBAL_POSITION_INT reports (0, 0).
            norm_lat, norm_lon, norm_alt = self.normalize_position(msg.lat, msg.lon, msg.alt)
            norm_vx, norm_vy, norm_vz = self.normalize_velocity(msg.vx, msg.vy, msg.vz)
            self.update_position(norm_lat, norm_lon, norm_alt)
            self.update_velocity(norm_vx, norm_vy, norm_vz)
            self.relative_alt = msg.relative_alt / self.norms["alt_factor"]

        sim = connection.last_message("SIMSTATE")
        if sim is not None and getattr(sim, "lat", 0) != 0:
            lat = sim.lat / self.norms["lat_factor"]
            lon = sim.lng / self.norms["lon_factor"]
            now = time.monotonic()
            if self._truth_time is not None and now > self._truth_time:
                dt = now - self._truth_time
                self.truth_velocity_north = (lat - self.truth_lat) * 111_320.0 / dt
                self.truth_velocity_east = (
                    (lon - self.truth_lon)
                    * 111_320.0
                    * math.cos(math.radians(lat))
                    / dt
                )
                self.truth_velocity_down = 0.0
            self.truth_lat = lat
            self.truth_lon = lon
            self._truth_time = now
    

    def nominal_gps_state(self) -> GpsInputState:
        """Build the authentic/nominal effect-level GPS state from current
        position, velocity, and the configured signal quality params.

        This is the state an attack receives and may modify or withhold.
        """
        q = self.signal_quality_params
        return GpsInputState(
            lat=self.lat,
            lon=self.lon,
            alt=self.alt,
            vn=self.velocity_north,
            ve=self.velocity_east,
            vd=self.velocity_down,
            fix_type=q["fix_type_3d"],
            satellites_visible=q["satellites_visible_count"],
            hdop=q["hdop"],
            vdop=q["vdop"],
            horizontal_accuracy=q["horizontal_accuracy"],
            vertical_accuracy=q["vertical_accuracy"],
            speed_accuracy=q["speed_accuracy"],
        )

    def get_signal_quality_params(self):
        """Returns the signal quality params used for sending GPS input messages via MAVLink.
        
        MAJOR DISCLAIMER: In a real-world GPS spoofing attack, the GPS doesn't ask the drone's
        GPS receiver for values like the HDOP, vertical accuracy, and so on. However, to
        simplify the simulation's design before expanding the complexity, we will use this
        shortcut for now. A real spoof would use an ephemeris file and simulate the satellites.
        """
        return self.signal_quality_params