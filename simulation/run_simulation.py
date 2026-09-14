from __future__ import annotations

import argparse
import importlib
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
import yaml

from communication.sitl_connection_config import ConnectionConfig
from communication.sitl_connection import SitlConnection
from drone.drone import Drone
from spoofer.sdr import SoftwareDefinedRadio

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


    def run_spoofing_simulation(self, attack_type: str, spawn_location: str):
        start_ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        print(f"Run start (UTC): {start_ts}")
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
        self.save_flight_log(attack_type, spawn_location, start_ts)
        self.connection.close()


    def save_flight_log(self, attack_type: str, spawn_location: str, start_ts: str) -> None:
        """Copy the newest DataFlash .BIN; UTC start/end are in the filename."""
        Path("logs").mkdir(parents=True, exist_ok=True)
        end_ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        logs_dir = Path("logs")
        stem = f"{attack_type}_{spawn_location}_{start_ts}_{end_ts}"
        bins = sorted(logs_dir.glob("*.BIN"), key=lambda p: p.stat().st_mtime, reverse=True)
        if bins:
            dest = logs_dir / f"{stem}.bin"
            shutil.copy(bins[0], dest)
            print(f"Saved flight log: {dest}")
            print(f"Run start (UTC): {start_ts}")
            print(f"Run end   (UTC): {end_ts}")
        else:
            print("WARNING: no DataFlash .BIN found in logs/")
    

    @staticmethod
    def parse_args() -> argparse.Namespace:
        """Parse command-line arguments."""
        parser = argparse.ArgumentParser(
            description="Set ArduPilot SITL parameters for GPS spoofing experiment"
        )
        parser.add_argument(
            "--attack-type",
            choices=["passthrough", "fabric", "drift", "complete_loss", "degradation"],
            default="passthrough",
            help="GPS attack type to apply (default: passthrough, no attack)",
        )
        parser.add_argument(
            "--spawn-location",
            choices=["ornl", "canberra"],
            default="ornl",
            help="Preset that loads the initial spawn location for the drone",
        )
        return parser.parse_args()
    

if __name__ == "__main__":
    simulation = GpsSpoofingSimulation()
    args = simulation.parse_args()
    try:
        simulation.run_spoofing_simulation(args.attack_type, args.spawn_location)
    except (ConnectionError, FileNotFoundError, KeyError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
