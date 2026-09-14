from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GpsInputState:
    """Effect-level GPS state this simulator honestly controls via GPS_INPUT.

    Mirrors the position, velocity, and quality/availability fields the SDR
    sends through ``gps_input_send``. Time fields and protocol fields
    (``gps_id``, ``ignore_flags``, ``yaw``) are intentionally excluded; the
    SDR owns those as clock/protocol concerns, not attack effects.

    Velocity is NED (m/s); ``alt`` is height above mean sea level (m).
    """

    # position
    lat: float
    lon: float
    alt: float
    # velocity (NED, m/s)
    vn: float
    ve: float
    vd: float
    # quality / availability
    fix_type: int
    satellites_visible: int
    hdop: float
    vdop: float
    horizontal_accuracy: float
    vertical_accuracy: float
    speed_accuracy: float
