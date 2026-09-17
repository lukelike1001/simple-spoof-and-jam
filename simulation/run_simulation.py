from __future__ import annotations

import argparse
import importlib
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
import yaml

from communication.sitl_connection_config import ConnectionConfig
from communication.sitl_connection import SitlConnection
from drone.drone import Drone
from spoofer.sdr import SoftwareDefinedRadio
from simulation.injection_log import write_injection_csv, write_run_metadata

SPAWN_LOOKUP_PATH = "plans/spawn_point_lookup.yaml"

class GpsSpoofingSimulation:

    connection: SitlConnection
    drone: Drone
    sdr: SoftwareDefinedRadio

    def __init__(self):
        pass


    def _instantiate_attack(self, attack_type: str, spawn_location: str):
        module = importlib.import_module(f"attack.{attack_type}_attack")
        class_name = "".join(part.capitalize() for part in attack_type.split("_")) + "Attack"
        cls = getattr(module, class_name)
        return cls(attack_type, spawn_location)


    def initialize_spoofing_simulation_components(self, attack_type: str, spawn_location: str):
        connection_config = ConnectionConfig.from_yaml()
        self.connection = SitlConnection(connection_config)
        self.drone = Drone()
        gps_attack = self._instantiate_attack(attack_type, spawn_location)
        self.sdr = SoftwareDefinedRadio(gps_attack)

    
    def find_spawn_coordinates(self, spawn_location: str):
        lookup_path = Path(SPAWN_LOOKUP_PATH)
        with lookup_path.open() as f:
            spawn_data = yaml.safe_load(f)
        spawn_coordinates = spawn_data[spawn_location]
        return (spawn_coordinates["lat"], spawn_coordinates["lon"], spawn_coordinates["alt"])
    

    def configure_ardupilot_connection(self, attack_type: str):
        print("Connecting to ArduPilot SITL...")
        self.connection.connect()
        self.connection.set_all_ardupilot_parameters(attack_type)
        print("Rebooting ArduPilot SITL...")
        self.connection.reboot()
        print("Sucessfully rebooted!")


    def run_spoofing_simulation(
        self, attack_type: str, spawn_location: str, output_dir: str | None = None
    ):
        start_ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        print(f"Run start (UTC): {start_ts}")

        # All artifacts for a run land in one folder. run_simulation.sh passes
        # --output-dir so its .bin/vehicle.csv share the folder; when run
        # standalone we default to a start-stamped folder.
        run_dir = Path(output_dir) if output_dir else Path("logs") / f"{attack_type}_{spawn_location}_{start_ts}"

        self.initialize_spoofing_simulation_components(attack_type, spawn_location)
        self.configure_ardupilot_connection(attack_type)

        gps_receiver = self.drone.get_gps_receiver()
        spawn_lat, spawn_lon, spawn_alt = self.find_spawn_coordinates(spawn_location)
        gps_receiver.update_position(spawn_lat, spawn_lon, spawn_alt)
        gps_receiver.update_velocity(0.0, 0.0, 0.0)

        print("Activating GPS Spoofing Attack...")
        print("Waiting for the flight to finish (arm, then disarm)...")
        self.sdr.activate_gps_attack(gps_receiver, self.connection)
        time.sleep(2)
        self.save_injection_log(attack_type, spawn_location, start_ts, run_dir)
        # The DataFlash .bin copy and its vehicle-metrics CSV are produced by
        # run_simulation.sh *after* it stops SITL, so the log is fully flushed.
        # Copying here (while SITL still runs) yields a truncated .bin.
        self.connection.close()

    def save_injection_log(
        self, attack_type: str, spawn_location: str, start_ts: str, run_dir: Path
    ) -> None:
        """Write the per-tick injection CSV and the run-metadata sidecar.

        These record what the attack injected/withheld (e_inject side), kept
        separate from the downstream vehicle metrics (e_vehicle side).
        """
        attack = self.sdr.attack
        activated_at = getattr(attack, "activated_at", math.inf)

        # Activation-relative time shared with the vehicle CSV's attack_time_s:
        # 0 at activation, <0 before, >0 after. From the loop's own known clock.
        records = self.sdr.injection_records
        for r in records:
            r["attack_time_s"] = (
                r["elapsed_s"] - activated_at if math.isfinite(activated_at) else float("nan")
            )
        write_injection_csv(records, run_dir / "injection.csv")
        meta = {
            "attack_type": attack_type,
            "spawn_location": spawn_location,
            "start_utc": start_ts,
            "gps_input_rate_hz": self.sdr.config.gps_input_rate_hz,
            "attack_duration_seconds": self.sdr.config.attack_duration_seconds,
            "activation_elapsed_s": activated_at if math.isfinite(activated_at) else None,
            "attack_params": getattr(attack, "config", None),
        }
        write_run_metadata(meta, run_dir / "metadata.json")
        print(f"Saved injection log: {run_dir / 'injection.csv'} ({len(records)} rows)")


    @staticmethod
    def parse_args() -> argparse.Namespace:
        """Parse command-line arguments."""
        parser = argparse.ArgumentParser(
            description="Set ArduPilot SITL parameters for GPS spoofing experiment"
        )
        parser.add_argument(
            "--attack-type",
            choices=["passthrough", "static", "drift", "complete_loss", "degradation"],
            default="passthrough",
            help="GPS attack type to apply (default: passthrough, no attack)",
        )
        parser.add_argument(
            "--spawn-location",
            choices=["ornl", "canberra"],
            default="ornl",
            help="Preset that loads the initial spawn location for the drone",
        )
        parser.add_argument(
            "--output-dir",
            default=None,
            help="Folder for this run's artifacts (default: logs/{attack}_{spawn}_{start})",
        )
        return parser.parse_args()
    

if __name__ == "__main__":
    simulation = GpsSpoofingSimulation()
    args = simulation.parse_args()
    try:
        simulation.run_spoofing_simulation(args.attack_type, args.spawn_location, args.output_dir)
    except (ConnectionError, FileNotFoundError, KeyError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
