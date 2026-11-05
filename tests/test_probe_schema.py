import json
from pathlib import Path

PROBES = Path(__file__).resolve().parent / "probes" / "probes.json"
FIELDS = {
    "id", "phenomenon", "question", "context", "answer",
    "must_not_accept", "must_accept", "expected_contradicted", "rationale",
}


def test_probe_file_is_well_formed():
    data = json.loads(PROBES.read_text(encoding="utf-8"))
    probes = data["probes"]
    ids = [probe["id"] for probe in probes]

    assert len(ids) == len(set(ids))
    for probe in probes:
        assert set(probe) == FIELDS, probe["id"]
        assert all(probe[key].strip() for key in ("question", "context", "answer", "rationale"))
        assert isinstance(probe["must_not_accept"], bool)
        assert isinstance(probe["must_accept"], bool)
        assert not (probe["must_not_accept"] and probe["must_accept"]), probe["id"]
        assert probe["expected_contradicted"] in (True, False, None)
        if probe["expected_contradicted"] is True:
            assert probe["must_not_accept"], probe["id"]
