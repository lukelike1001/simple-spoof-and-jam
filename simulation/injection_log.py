"""Write the per-tick GPS injection log and its run-metadata sidecar.

The injection log records what SimpleSpoofAndJam *injects* (or withholds) at the
GPS_INPUT boundary, independent of whatever ArduPilot subsequently accepts.

    e_inject_h_m : did the attack deliberately inject false navigation content?
                   (horizontal distance between injected position and truth)

This is deliberately kept separate from the downstream vehicle/estimator error
(see simulation/extract_vehicle_metrics.py). Vehicle-position error produced
during jamming must never be read as attacker-selected content.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

# Column order for the injection CSV. Rows are the dicts built by
# SoftwareDefinedRadio._record_injection().
INJECTION_COLUMNS = [
    "elapsed_s",
    "attack_time_s",
    "activated",
    "gps_sent",
    "inj_lat",
    "inj_lon",
    "inj_alt",
    "inj_vn",
    "inj_ve",
    "inj_vd",
    "fix_type",
    "h_acc",
    "v_acc",
    "s_acc",
    "truth_lat",
    "truth_lon",
    "truth_alt",
    "e_inject_h_m",
]


def write_injection_csv(records: list[dict], csv_path: Path) -> None:
    """Write injection records to CSV in the fixed INJECTION_COLUMNS order."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=INJECTION_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in records:
            writer.writerow(row)


def write_run_metadata(meta: dict, meta_path: Path) -> None:
    """Write the run-metadata sidecar as JSON."""
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    with meta_path.open("w") as f:
        json.dump(meta, f, indent=2, sort_keys=True)
