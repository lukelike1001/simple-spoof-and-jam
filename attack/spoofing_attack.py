from __future__ import annotations

from attack.gps_attack import GpsAttack


class SpoofingAttack(GpsAttack):
    """Base class for spoofing attacks: they manipulate the content of the
    reported navigation solution and always return a GpsInputState from
    ``apply`` (never None). Concrete strategies implement ``apply``.
    """
