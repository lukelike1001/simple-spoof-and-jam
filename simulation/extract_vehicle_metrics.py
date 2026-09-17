"""Extract focused vehicle/estimator metrics from an ArduPilot DataFlash .bin.

This is the downstream half of the Step-4 instrumentation. It answers:

    e_vehicle_h_m : how far did ArduPilot's navigation estimate (POS) depart
                    from SITL truth (SIM)?

This is intentionally separate from e_inject (see simulation/injection_log.py).
Under jamming, e_vehicle may grow while nothing false was injected: that drift
is an emergent estimator response, NOT attacker-selected navigation content.

Sampling: rows are anchored at POS (EKF estimate) timestamps. SIM/GPS/GPA/XKF4
values are joined by nearest timestamp. GPS/GPA are treated as *present* only if
the nearest sample is within GPS_STALENESS_S; otherwise gps_present=0 (e.g. under
complete-loss jamming, where GPS_INPUT is withheld and GPS rows stop). We do not
pretend the streams are exactly synchronized.
"""
from __future__ import annotations

import argparse
import bisect
import csv
import math
import sys
from pathlib import Path

from pymavlink import DFReader

METRES_PER_DEG_LAT = 111_320.0
# A GPS/GPA sample farther than this from a POS timestamp is treated as absent.
# Nominal GPS_INPUT rate is 5 Hz (0.2 s); 0.5 s tolerates jitter without masking
# a real dropout.
GPS_STALENESS_S = 0.5

VEHICLE_COLUMNS = [
    "t_s",
    "attack_time_s",
    "sim_lat",
    "sim_lon",
    "pos_lat",
    "pos_lon",
    "pos_alt",
    "e_vehicle_h_m",
    "gps_present",
    "gps_age_s",
    "gps_status",
    "gps_nsats",
    "gps_hdop",
    "gps_lat",
    "gps_lon",
    "gps_hacc",
    "gps_vacc",
    "gps_sacc",
    "xkf_fs",
]


def _horizontal_distance_m(lat_a, lon_a, lat_b, lon_b) -> float:
    dnorth = (lat_a - lat_b) * METRES_PER_DEG_LAT
    deast = (lon_a - lon_b) * METRES_PER_DEG_LAT * math.cos(math.radians(lat_b))
    return math.hypot(dnorth, deast)


def _collect(bin_path: Path) -> dict[str, list]:
    """Single pass over the log; collect the message streams we need.

    GPS/GPA/XKF4 are filtered to instance/core 0. ARM is collected to bound the
    analysis to the armed flight window.
    """
    log = DFReader.DFReader_binary(str(bin_path))
    streams: dict[str, list] = {"SIM": [], "POS": [], "GPS": [], "GPA": [], "XKF4": [], "ARM": []}
    wanted = list(streams)
    while True:
        msg = log.recv_match(type=wanted)
        if msg is None:
            break
        t = msg.get_type()
        if t in ("GPS", "GPA") and getattr(msg, "I", 0) != 0:
            continue
        if t == "XKF4" and getattr(msg, "C", 0) != 0:
            continue
        streams[t].append(msg)
    return streams


# Activation-detection thresholds (see detect_activation).
_ACT_GAP_S = 1.0          # GPS inter-sample gap marking availability loss (jamming)
_ACT_HACC = 0.6           # GPA horizontal-accuracy above nominal (~0.5) => degradation
_ACT_POS_M = 3.0          # sustained GPS-vs-truth divergence => content spoof
_ACT_BASELINE_M = 1.0     # near-truth baseline used to walk back to divergence onset
_ACT_SUSTAIN = 5          # samples (~1 s at 5 Hz) a departure must persist to count


def detect_activation(streams: dict, times: dict, cutoff: int | None) -> tuple[int | None, str | None]:
    """Infer the attack activation instant (boot-time TimeUS) from the DataFlash.

    The Python injector's monotonic clock is not logged in the .bin, and
    GPS1_TYPE is set to 14 before the flight (so it does not transition at
    activation). There is therefore no common logged timestamp: the anchor must
    be inferred from the first *effect* the attack has on the injected GPS, taken
    within the armed window. We use the earliest of three sustained departures
    from the authentic/nominal baseline:

      - availability : first GPS inter-sample gap > _ACT_GAP_S  (CompleteLoss)
      - quality      : GPA horizontal accuracy sustained > _ACT_HACC  (Degradation)
      - content      : |GPS - truth| sustained > _ACT_POS_M, then walked back to
                       the last near-baseline sample so a gradual onset (Drift)
                       is anchored at its start, not where it crosses the
                       threshold (Static's step is unaffected).

    Returns (anchor_us, signal_name), or (None, None) when nothing departs from
    nominal (e.g. passthrough, which never activates).
    """
    gps = [m for m in streams["GPS"] if cutoff is None or int(m.TimeUS) <= cutoff]
    gpa = [m for m in streams["GPA"] if cutoff is None or int(m.TimeUS) <= cutoff]
    sim_t, sim_m = times["SIM"], streams["SIM"]

    cands: dict[str, int] = {}

    for i in range(len(gps) - 1):
        if (int(gps[i + 1].TimeUS) - int(gps[i].TimeUS)) / 1e6 > _ACT_GAP_S:
            cands["availability"] = int(gps[i].TimeUS)
            break

    for i in range(len(gpa) - _ACT_SUSTAIN):
        if all(float(gpa[i + k].HAcc) > _ACT_HACC for k in range(_ACT_SUSTAIN)):
            cands["quality"] = int(gpa[i].TimeUS)
            break

    dist = []
    for g in gps:
        s, _ = _nearest(sim_t, sim_m, int(g.TimeUS))
        dist.append(_horizontal_distance_m(g.Lat, g.Lng, s.Lat, s.Lng) if s else 0.0)
    for i in range(len(gps) - _ACT_SUSTAIN):
        if all(dist[i + k] > _ACT_POS_M for k in range(_ACT_SUSTAIN)):
            j = i
            while j > 0 and dist[j] > _ACT_BASELINE_M:
                j -= 1
            cands["content"] = int(gps[j].TimeUS)
            break

    if not cands:
        return None, None
    signal = min(cands, key=cands.get)
    return cands[signal], signal


def _disarm_cutoff_us(arms: list) -> int | None:
    """TimeUS of the final disarm (ArmState==0), or None if no disarm is logged.

    The injection loop stops sending GPS_INPUT at disarm, so GPS cadence collapses
    from ~5 Hz to a slow timeout heartbeat while POS keeps logging for a few more
    seconds until SITL is stopped. That post-disarm tail is not part of the flight
    or the attack window, so we clip metrics at disarm to avoid presenting it as a
    GPS availability loss.
    """
    disarms = [int(m.TimeUS) for m in arms if int(getattr(m, "ArmState", -1)) == 0]
    return max(disarms) if disarms else None


def _nearest(times: list[int], msgs: list, t_us: int):
    """Nearest message to t_us and its absolute time delta (seconds)."""
    if not times:
        return None, None
    i = bisect.bisect_left(times, t_us)
    candidates = []
    if i < len(times):
        candidates.append(i)
    if i > 0:
        candidates.append(i - 1)
    best = min(candidates, key=lambda j: abs(times[j] - t_us))
    return msgs[best], abs(times[best] - t_us) / 1e6


def extract_rows(bin_path: Path) -> list[dict]:
    """Return one metrics row per POS sample."""
    if not bin_path.is_file():
        raise FileNotFoundError(f"Log not found: {bin_path}")

    streams = _collect(bin_path)
    if not streams["POS"]:
        raise ValueError(f"No POS (EKF position) messages in {bin_path}")
    if not streams["SIM"]:
        raise ValueError(f"No SIM (truth) messages in {bin_path}")

    times = {name: [int(m.TimeUS) for m in msgs] for name, msgs in streams.items()}
    t0 = int(streams["POS"][0].TimeUS)
    nan = float("nan")

    # Clip to the armed flight window: drop POS samples after the final disarm,
    # which are post-flight tail where GPS_INPUT has stopped (see _disarm_cutoff_us).
    cutoff = _disarm_cutoff_us(streams["ARM"])
    pos_msgs = [m for m in streams["POS"] if cutoff is None or int(m.TimeUS) <= cutoff]

    # Activation-relative time: t_attack = 0 at the inferred attack transition.
    anchor_us, _signal = detect_activation(streams, times, cutoff)

    rows: list[dict] = []
    for pos in pos_msgs:
        t_us = int(pos.TimeUS)
        sim, _ = _nearest(times["SIM"], streams["SIM"], t_us)
        gps, gps_dt = _nearest(times["GPS"], streams["GPS"], t_us)
        gpa, gpa_dt = _nearest(times["GPA"], streams["GPA"], t_us)
        xkf, _ = _nearest(times["XKF4"], streams["XKF4"], t_us)

        gps_present = gps is not None and gps_dt is not None and gps_dt <= GPS_STALENESS_S
        gpa_present = gpa is not None and gpa_dt is not None and gpa_dt <= GPS_STALENESS_S

        e_vehicle = _horizontal_distance_m(pos.Lat, pos.Lng, sim.Lat, sim.Lng) if sim else nan

        rows.append(dict(
            t_s=(t_us - t0) / 1e6,
            attack_time_s=(t_us - anchor_us) / 1e6 if anchor_us is not None else nan,
            gps_age_s=gps_dt if gps_dt is not None else nan,
            sim_lat=sim.Lat if sim else nan,
            sim_lon=sim.Lng if sim else nan,
            pos_lat=pos.Lat,
            pos_lon=pos.Lng,
            pos_alt=pos.Alt,
            e_vehicle_h_m=e_vehicle,
            gps_present=int(gps_present),
            gps_status=int(gps.Status) if gps_present else nan,
            gps_nsats=int(gps.NSats) if gps_present else nan,
            gps_hdop=float(gps.HDop) if gps_present else nan,
            gps_lat=float(gps.Lat) if gps_present else nan,
            gps_lon=float(gps.Lng) if gps_present else nan,
            gps_hacc=float(gpa.HAcc) if gpa_present else nan,
            gps_vacc=float(gpa.VAcc) if gpa_present else nan,
            gps_sacc=float(gpa.SAcc) if gpa_present else nan,
            xkf_fs=int(xkf.FS) if xkf is not None else nan,
        ))
    return rows


def write_vehicle_csv(bin_path: Path, csv_path: Path) -> int:
    """Extract metrics from bin_path and write them to csv_path. Returns row count."""
    rows = extract_rows(bin_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=VEHICLE_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def _default_output(bin_path: Path) -> Path:
    return bin_path.with_name(bin_path.stem + "_vehicle.csv")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract vehicle metrics from a DataFlash .bin")
    parser.add_argument("bin_log", type=Path, help="ArduPilot DataFlash .bin log")
    parser.add_argument(
        "-o", "--output", type=Path, default=None,
        help="Output CSV (default: <bin stem>_vehicle.csv next to the log)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output = args.output or _default_output(args.bin_log)
    try:
        n = write_vehicle_csv(args.bin_log, output)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    print(f"Wrote {output} ({n} rows)")


if __name__ == "__main__":
    main()
