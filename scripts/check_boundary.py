"""Compare external cores at cabinet terminals from independent SVS and MKS exports."""
import argparse
import csv
import sys
from pathlib import Path

FIELDS = ("panel", "cable", "core", "strip", "terminal", "circuit")


def read(path):
    result = {}
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, delimiter=";")
        if not set(FIELDS) <= set(reader.fieldnames or []):
            raise ValueError(f"{path}: missing columns {FIELDS}")
        for n, row in enumerate(reader, 2):
            values = tuple((row.get(k) or "").strip() for k in FIELDS)
            key = values[:3]
            if not all(values) or key in result:
                raise ValueError(f"{path}:{n}: incomplete row or duplicate core {key}")
            result[key] = values[3:]
    if not result:
        raise ValueError(f"{path}: no cores to compare")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("svs", type=Path)
    parser.add_argument("mks", type=Path)
    args = parser.parse_args()
    if args.svs.resolve() == args.mks.resolve():
        parser.error("supply independent exports")
    try:
        a, b = read(args.svs), read(args.mks)
    except (OSError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 2
    keys = sorted(a.keys() | b.keys())
    bad = [k for k in keys if a.get(k) != b.get(k)]
    for k in bad:
        print(k, "SVS", a.get(k), "MKS", b.get(k))
    print(f"{len(keys)} cores; {len(bad)} differences")
    return int(bool(bad))


if __name__ == "__main__":
    sys.exit(main())
