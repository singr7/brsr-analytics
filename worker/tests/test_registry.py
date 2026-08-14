from pathlib import Path

from ops.registry.build_registry import build_rows, load_sector_map


def test_registry_ranks_by_market_cap_and_maps_nic_sector() -> None:
    rows = build_rows(Path("testdata/registry.csv"), Path("taxonomy/sectors.yaml"), limit=2)
    assert [row["ticker"] for row in rows] == ["BETA", "GAMMA"]
    assert rows[0]["sector"] == "Technology & Communications"
    assert rows[1]["sector"] == "Financial Services"
    assert all(row["mcap_band"] == "large" for row in rows)


def test_sector_taxonomy_has_no_duplicate_nic_divisions() -> None:
    mapping, fallback = load_sector_map(Path("taxonomy/sectors.yaml"))
    assert len(mapping) == len(set(mapping))
    assert mapping[35] == "Energy & Utilities"
    assert fallback == "Other / Review Required"
