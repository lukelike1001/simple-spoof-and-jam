"""
Manage a MAVLink connection to ArduPilot SITL.

Connects the drone, flight environment, and the SDR to the secondary MAVProxy
UDP port (14551) to avoid conflicting with QGroundControl, which listens on 14550.

All tunable values live in communication/sitl_connection_params.yaml.
"""

import time
from collections.abc import Mapping
from pymavlink import mavutil

from .sitl_connection_config import ConnectionConfig

class SitlConnection:
    """Manages a MAVLink connection to ArduPilot SITL."""

    def __init__(self, config: ConnectionConfig) -> None:
        """Initialise with injected configuration; does not connect immediately."""
        self.config = config
        self._mav = None


    def connect(self) -> None:
        """Open the MAVLink connection and block until a heartbeat is received.

        Raises:
            ConnectionError: If no heartbeat arrives within the configured timeout.
        """
        print(f"Connecting to SITL at {self.config.address} …", flush=True)
        self._mav = mavutil.mavlink_connection(self.config.address)
        if not self._mav.wait_heartbeat(timeout=self.config.heartbeat_timeout_seconds):
            raise ConnectionError(
                f"No heartbeat from SITL within "
                f"{self.config.heartbeat_timeout_seconds}s. "
                "Is sim_vehicle.py running?"
            )
        print(
            f"  system {self._mav.target_system} "
            f"component {self._mav.target_component} online"
        )


    def reboot(self) -> None:
        """Reboot SITL via MAVLink and block until it comes back online.

        Closes the current connection as part of the reboot until the connection
        automatically re-establishes itself. We also open and close a separate,
        temporary connection to confirm that the SITL has come back online.

        This function is the equivalent of typing `reboot` directly into the MAVLink
        terminal, but used for automation without user input such as the master script.

        Raises:
            ConnectionError: If SITL does not re-heartbeat within the configured timeout.
        """
        self.mav.mav.command_long_send(
            self.mav.target_system,
            self.mav.target_component,
            mavutil.mavlink.MAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN,
            0,
            1, 0, 0, 0, 0, 0, 0,
        )

        self.close()
        print("ArduPilot will automatically attempt to reconnect to MAVLink...")
        time.sleep(self.config.reboot_settle_seconds)
        try:
            self.connect()
        except ConnectionError:
            raise ConnectionError("SITL did not come back online after reboot.")
        print("Reconnected successfully!")


    def close(self) -> None:
        """Close the MAVLink connection if one is open."""
        if self._mav:
            self._mav.close()
            self._mav = None


    @property
    def mav(self):
        """Return the active MAVLink handle.

        Raises:
            RuntimeError: If called before connect().
        """
        if not self._mav:
            raise RuntimeError("Call connect() before accessing the MAVLink handle.")
        return self._mav


    def poll_armed(self) -> bool | None:
        """Non-blocking: True/False if a vehicle HEARTBEAT arrived, else None."""
        msg = self.mav.recv_match(type="HEARTBEAT", blocking=False)
        if msg is None or msg.get_srcSystem() != self.mav.target_system:
            return None
        return bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)


    def set_ardupilot_parameter(self, parameter_name: str, parameter_value: float) -> bool:
        """Send a PARAM_SET message and confirm the ACK."""
        for attempt in range(1, self.config.max_retries + 1):
            self.mav.mav.param_set_send(
                self.mav.target_system,
                self.mav.target_component,
                parameter_name.encode("utf-8"),
                float(parameter_value),
                mavutil.mavlink.MAV_PARAM_TYPE_REAL32,
            )
            ack = self.mav.recv_match(
                type="PARAM_VALUE",
                blocking=True,
                timeout=self.config.ack_timeout_seconds,
            )
            if ack and ack.param_id.rstrip("\x00") == parameter_name:
                print(f"  {parameter_name:<24} = {parameter_value}")
                return True
            print(
                f"  {parameter_name}: no ACK "
                f"(attempt {attempt}/{self.config.max_retries})",
                flush=True,
            )
        print(f"  WARNING: could not confirm {parameter_name}")
        return False


    def set_all_ardupilot_parameters(self, mode: str) -> None:
        """Apply a mapping of Ardupilot parameters"""
        ardupilot_parameters = (
            {**self.config.fence_params, **self.config.nav_params, **self.config.gps_passthrough_params}
            if mode == "passthrough"
            else {**self.config.fence_params, **self.config.nav_params, **self.config.gps_attack_params}
        )

        for name, value in ardupilot_parameters.items():
            self.set_ardupilot_parameter(name, value)
