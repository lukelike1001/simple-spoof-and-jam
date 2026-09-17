import json
import math

from simulation.injection_log import (
    INJECTION_COLUMNS,
    write_injection_csv,
    write_run_metadata,
)


def _row(**over):
    base = {c: 0.0 for c in INJECTION_COLUMNS}
    base.update(over)
    return base


class TestInjectionCsv:

    def test_header_matches_schema_order(self, tmp_path):
        out = tmp_path / "inject.csv"
        write_injection_csv([_row()], out)
        header = out.read_text().splitlines()[0]
        assert header == ",".join(INJECTION_COLUMNS)

    def test_writes_one_row_per_record(self, tmp_path):
        out = tmp_path / "inject.csv"
        write_injection_csv([_row(elapsed_s=0.0), _row(elapsed_s=0.2)], out)
        assert len(out.read_text().splitlines()) == 3  # header + 2

    def test_nan_is_written_for_withheld_fields(self, tmp_path):
        out = tmp_path / "inject.csv"
        write_injection_csv([_row(gps_sent=0, inj_lat=float("nan"), e_inject_h_m=float("nan"))], out)
        body = out.read_text().splitlines()[1]
        assert "nan" in body.lower()

    def test_empty_records_writes_only_header(self, tmp_path):
        out = tmp_path / "inject.csv"
        write_injection_csv([], out)
        assert out.read_text().splitlines() == [",".join(INJECTION_COLUMNS)]


class TestRunMetadata:

    def test_metadata_roundtrips(self, tmp_path):
        out = tmp_path / "meta.json"
        meta = {"attack_type": "drift", "activation_elapsed_s": 5.0, "attack_params": {"drift_rate_north": 0.02}}
        write_run_metadata(meta, out)
        assert json.loads(out.read_text()) == meta
