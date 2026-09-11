"""Plot GPS log asymmetry: a spoofed track vs a jamming health drop.

Reads two ArduPilot DataFlash .bin logs and writes a two-panel figure. No display.
Fields: GPS.Lat, GPS.Lng (local East/North metres) and GPS.Status.
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import LineCollection
from pymavlink import DFReader

METRES_PER_DEG_LAT = 111_320.0
GPS_OK_FIX_3D = 3
STATUS_TICKS = (0, 1, 2, 3, 4, 5, 6)
STATUS_LABELS = ("NO_GPS", "NO_FIX", "2D", "3D", "DGPS", "RTK_F", "RTK")


def read_gps(bin_path: Path) -> dict[str, np.ndarray]:
    """Load GPS instance 0 from a DataFlash log."""
    if not bin_path.is_file():
        raise FileNotFoundError(f"Log not found: {bin_path}")

    log = DFReader.DFReader_binary(str(bin_path))
    rows: list[tuple[int, float, float, int]] = []
    while True:
        msg = log.recv_match(type="GPS")
        if msg is None:
            break
        if getattr(msg, "I", 0) != 0:
            continue
        rows.append((int(msg.TimeUS), float(msg.Lat), float(msg.Lng), int(msg.Status)))

    if not rows:
        raise ValueError(f"No GPS messages in {bin_path}")

    time_us, lat, lon, status = (np.array(col) for col in zip(*rows))
    return {
        "t_s": (time_us - time_us[0]) / 1e6,
        "lat": lat,
        "lon": lon,
        "status": status,
    }


def latlon_to_local_metres(
    lat: np.ndarray, lon: np.ndarray, origin_lat: float, origin_lon: float
) -> tuple[np.ndarray, np.ndarray]:
    north = (lat - origin_lat) * METRES_PER_DEG_LAT
    east = (lon - origin_lon) * METRES_PER_DEG_LAT * math.cos(math.radians(origin_lat))
    return east, north


def valid_fix_mask(lat: np.ndarray, lon: np.ndarray, status: np.ndarray) -> np.ndarray:
    return (status >= GPS_OK_FIX_3D) & ~((lat == 0.0) & (lon == 0.0))


def as_local(
    gps: dict[str, np.ndarray],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """East/North metres and a 3D-fix mask, origin = first valid fix."""
    mask = valid_fix_mask(gps["lat"], gps["lon"], gps["status"])
    if np.any(mask):
        origin_lat, origin_lon = float(gps["lat"][mask][0]), float(gps["lon"][mask][0])
    else:
        origin_lat, origin_lon = float(gps["lat"][0]), float(gps["lon"][0])
    east, north = latlon_to_local_metres(gps["lat"], gps["lon"], origin_lat, origin_lon)
    return east, north, mask


def _apply_style() -> None:
    plt.rcParams.update(
        {
            "font.size": 9,
            "axes.titlesize": 10,
            "axes.labelsize": 9,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "legend.fontsize": 8,
            "axes.linewidth": 0.8,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "savefig.dpi": 300,
            "savefig.bbox": "tight",
            "savefig.facecolor": "white",
        }
    )


def _plot_colored_track(ax: plt.Axes, east: np.ndarray, north: np.ndarray, t_s: np.ndarray):
    points = np.column_stack([east, north]).reshape(-1, 1, 2)
    segments = np.concatenate([points[:-1], points[1:]], axis=1)
    norm = plt.Normalize(float(t_s[0]), float(t_s[-1]))
    lines = LineCollection(segments, cmap="viridis", norm=norm, linewidths=1.6)
    lines.set_array(t_s[:-1])
    ax.add_collection(lines)
    ax.scatter(east[0], north[0], s=28, c="k", zorder=3, label="Start")
    ax.scatter(east[-1], north[-1], s=28, c="k", marker="^", zorder=3, label="End")
    return lines


def plot_asymmetry(
    left: dict[str, np.ndarray],
    right: dict[str, np.ndarray],
    output_path: Path,
    left_title: str = "Spoofing",
    right_title: str = "Jamming",
) -> None:
    _apply_style()
    left_east, left_north, _ = as_local(left)
    right_east, right_north, right_ok = as_local(right)

    fig = plt.figure(figsize=(10.0, 4.2))
    grid = fig.add_gridspec(
        2, 2, width_ratios=[1.05, 1.0], height_ratios=[1.0, 0.72],
        wspace=0.34, hspace=0.08,
    )
    ax_track = fig.add_subplot(grid[:, 0])
    ax_pos = fig.add_subplot(grid[0, 1])
    ax_status = fig.add_subplot(grid[1, 1], sharex=ax_pos)

    lines = _plot_colored_track(ax_track, left_east, left_north, left["t_s"])
    ax_track.set_aspect("equal", adjustable="datalim")
    ax_track.autoscale()
    ax_track.set_xlabel("East (m)")
    ax_track.set_ylabel("North (m)")
    ax_track.set_title(left_title)
    ax_track.legend(loc="upper left", frameon=False)
    cbar = fig.colorbar(lines, ax=ax_track, fraction=0.046, pad=0.04)
    cbar.set_label("Time (s)")

    ax_pos.plot(
        right["t_s"], np.where(right_ok, right_east, np.nan),
        color="#2166ac", lw=1.4, label="East",
    )
    ax_pos.plot(
        right["t_s"], np.where(right_ok, right_north, np.nan),
        color="#4daf4a", lw=1.4, label="North",
    )
    ax_pos.set_ylabel("Position (m)")
    ax_pos.set_title(right_title)
    ax_pos.legend(loc="upper right", frameon=False, ncol=2)
    ax_pos.tick_params(labelbottom=False)

    ax_status.step(right["t_s"], right["status"], where="post", color="#b2182b", lw=1.6)
    ax_status.set_yticks(STATUS_TICKS)
    ax_status.set_yticklabels(STATUS_LABELS)
    ax_status.set_ylim(-0.4, 6.6)
    ax_status.set_xlabel("Time (s)")
    ax_status.set_ylabel("GPS.Status")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path)
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot a spoofing GPS track next to a jamming GPS.Status drop"
    )
    parser.add_argument("left_log", type=Path, help="Spoofing (or other) DataFlash .bin")
    parser.add_argument("right_log", type=Path, help="Jamming (or other) DataFlash .bin")
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=Path("logs/attack_asymmetry.pdf"),
        help="Output figure path (.pdf or .png)",
    )
    parser.add_argument("--left-title", default="Spoofing")
    parser.add_argument("--right-title", default="Jamming")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        plot_asymmetry(
            read_gps(args.left_log),
            read_gps(args.right_log),
            args.output,
            left_title=args.left_title,
            right_title=args.right_title,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
