import math
from pathlib import Path

import pytest

from simulation.extract_vehicle_metrics import (
    VEHICLE_COLUMNS,
    detect_activation,
    extract_rows,
    write_vehicle_csv,
)

DRIFT_BIN = Path("samples/drift_ornl_20260910T165109Z_20260910T165302Z.bin")
JAMMING_BIN = Path("samples/jamming_ornl_20260911T032217Z_20260911T032617Z.bin")


@pytest.mark.skipif(not DRIFT_BIN.is_file(), reason="sample drift log not present")
class TestExtractDrift:

    def test_extracts_rows_with_expected_columns(self):
        rows = extract_rows(DRIFT_BIN)
        assert rows
        assert set(rows[0]) == set(VEHICLE_COLUMNS)

    def test_time_is_monotonic_from_zero(self):
        rows = extract_rows(DRIFT_BIN)
        assert rows[0]["t_s"] == pytest.approx(0.0, abs=1e-6)
        ts = [r["t_s"] for r in rows]
        assert ts == sorted(ts)

    def test_e_vehicle_is_finite_and_nonnegative(self):
        rows = extract_rows(DRIFT_BIN)
        vals = [r["e_vehicle_h_m"] for r in rows]
        assert all(math.isfinite(v) and v >= 0 for v in vals)

    def test_gps_present_mostly_true_for_spoof(self):
        # A spoof keeps sending GPS_INPUT, so GPS should be present most of the run.
        rows = extract_rows(DRIFT_BIN)
        present = sum(r["gps_present"] for r in rows)
        assert present > 0.5 * len(rows)

    def test_write_csv_roundtrips(self, tmp_path):
        out = tmp_path / "vehicle.csv"
        n = write_vehicle_csv(DRIFT_BIN, out)
        text = out.read_text().splitlines()
        assert text[0] == ",".join(VEHICLE_COLUMNS)
        assert len(text) == n + 1


@pytest.mark.skipif(not JAMMING_BIN.is_file(), reason="sample jamming log not present")
class TestExtractJamming:

    def test_gps_drops_out_during_jamming(self):
        # Complete-loss jamming withholds GPS_INPUT, so some POS samples should
        # have no nearby GPS row (gps_present == 0).
        rows = extract_rows(JAMMING_BIN)
        assert any(r["gps_present"] == 0 for r in rows)

    def test_e_vehicle_still_computable_without_gps(self):
        # POS (EKF estimate) vs SIM (truth) is available even when GPS is gone;
        # this is the emergent estimator drift, not injected content.
        rows = extract_rows(JAMMING_BIN)
        no_gps = [r for r in rows if r["gps_present"] == 0]
        assert no_gps
        assert all(math.isfinite(r["e_vehicle_h_m"]) for r in no_gps)


def test_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        extract_rows(Path("logs/does_not_exist.bin"))


PASSTHRU_BIN = Path("samples/passthrough_ornl_20260908T184713Z_20260908T185025Z.bin")


class TestActivationAnchor:

    @pytest.mark.skipif(not JAMMING_BIN.is_file(), reason="sample jamming log not present")
    def test_attack_time_column_present_and_spans_zero(self):
        rows = extract_rows(JAMMING_BIN)
        assert "attack_time_s" in rows[0]
        ats = [r["attack_time_s"] for r in rows]
        # Anchor lies inside the flight -> both pre- and post-activation samples exist.
        assert any(a < 0 for a in ats)
        assert any(a > 0 for a in ats)
        # A sample sits within one GPS interval of t_attack = 0.
        assert min(abs(a) for a in ats) < 0.5

    @pytest.mark.skipif(not JAMMING_BIN.is_file(), reason="sample jamming log not present")
    def test_attack_time_is_monotonic_with_t_s(self):
        rows = extract_rows(JAMMING_BIN)
        offsets = [r["t_s"] - r["attack_time_s"] for r in rows]
        # t_s and attack_time_s differ only by a constant anchor offset.
        assert max(offsets) - min(offsets) < 1e-6


class TestDetectActivation:
    """Fixture-independent unit tests for the anchor detector."""

    @staticmethod
    def _streams(hacc=0.5, pos_offset_m=0.0, gap_at=None):
        from types import SimpleNamespace as NS
        gps, gpa, sim = [], [], []
        dlat = pos_offset_m / 111_320.0
        t = 0
        for i in range(60):
            if gap_at is not None and i == gap_at:
                t += 4_000_000            # 4 s GPS gap (availability loss)
            else:
                t += 200_000              # 5 Hz
            sim.append(NS(TimeUS=t, Lat=35.0, Lng=-84.0))
            # divergence only applies from the second half of the run
            off = dlat if i >= 30 else 0.0
            gps.append(NS(TimeUS=t, Lat=35.0 + off, Lng=-84.0, Status=3, NSats=12, HDop=1.0))
            h = hacc if i < 30 else (hacc if hacc > 0.6 else 0.5)
            gpa.append(NS(TimeUS=t, HAcc=(5.0 if (i >= 30 and hacc > 0.6) else 0.5),
                          VAcc=2.0, SAcc=0.5))
        streams = {"GPS": gps, "GPA": gpa, "SIM": sim, "POS": [], "XKF4": [], "ARM": []}
        times = {k: [int(m.TimeUS) for m in v] for k, v in streams.items()}
        return streams, times

    def test_nominal_has_no_anchor(self):
        s, t = self._streams()
        assert detect_activation(s, t, None) == (None, None)

    def test_detects_quality_ramp(self):
        s, t = self._streams(hacc=5.0)
        anchor, sig = detect_activation(s, t, None)
        assert sig == "quality" and anchor is not None

    def test_detects_content_divergence(self):
        s, t = self._streams(pos_offset_m=50.0)
        anchor, sig = detect_activation(s, t, None)
        assert sig == "content" and anchor is not None

    def test_detects_availability_gap(self):
        s, t = self._streams(gap_at=40)
        anchor, sig = detect_activation(s, t, None)
        assert sig == "availability" and anchor is not None
