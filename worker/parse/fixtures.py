from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[2] / "testdata" / "acquisition"
    fixtures = sorted([*root.glob("*.pdf"), *root.glob("*.xbrl")])
    if len(fixtures) != 6:
        raise SystemExit(f"Expected 6 acquisition fixtures, found {len(fixtures)}")
    print(f"Offline acquisition fixtures ready: {len(fixtures)} files.")


if __name__ == "__main__":
    main()
