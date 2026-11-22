"""Check a project registry and optionally export grouped purchasing rows (Python 3.9+)."""
import argparse
import csv
import json
import math
import sys
from collections import defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check_shape(value, rule, path, errors):
    types = {dict: "object", list: "array", str: "string", int: "number",
             float: "number", type(None): "null", bool: "boolean"}
    allowed = rule.get("type")
    if allowed and types.get(type(value)) not in (allowed if isinstance(allowed, list) else [allowed]):
        errors.append(f"{path}: expected {allowed}")
        return
    if "enum" in rule and value not in rule["enum"]:
        errors.append(f"{path}: expected {rule['enum']}")
    if "const" in rule and (type(value) != type(rule["const"]) or value != rule["const"]):
        errors.append(f"{path}: unsupported version")
    if isinstance(value, dict):
        for key in rule.get("required", []):
            if key not in value:
                errors.append(f"{path}.{key}: missing")
        for key, child in rule.get("properties", {}).items():
            if key in value:
                check_shape(value[key], child, f"{path}.{key}", errors)
    if isinstance(value, list):
        if len(value) < rule.get("minItems", 0):
            errors.append(f"{path}: too few items")
        for index, item in enumerate(value):
            check_shape(item, rule["items"], f"{path}[{index}]", errors)
    if isinstance(value, str):
        if len(value.strip()) < rule.get("minLength", 0):
            errors.append(f"{path}: empty text")
        if rule.get("format") == "date":
            try:
                date.fromisoformat(value)
            except ValueError:
                errors.append(f"{path}: invalid date")
    if type(value) in (int, float):
        if not math.isfinite(value) or value < rule.get("minimum", -math.inf) or value <= rule.get("exclusiveMinimum", -math.inf):
            errors.append(f"{path}: invalid number")


def check(p):
    errors = []
    schema = json.loads((ROOT / "references/project.schema.json").read_text(encoding="utf-8"))
    check_shape(p, schema, "project", errors)
    if errors:
        return errors
    def unique(values, where):
        if len(values) != len(set(values)):
            errors.append(f"{where}: duplicate")
    for key in ("components", "materials", "pipelines", "loops", "media", "equipment", "connections"):
        unique([row["id"] for row in p[key]], key)
    parts = {c["id"]: c for c in p["components"]}
    unique([c["tag"].casefold() for c in parts.values()], "component tags")
    unique([m["code"] for m in p["media"]], "medium codes")
    media = {m["id"] for m in p["media"]}
    nodes = {e["id"] for e in p["equipment"]}
    for pipe in p["pipelines"]:
        if pipe["medium"] not in media or any(pipe[k] not in nodes for k in ("from", "to")):
            errors.append(f"{pipe['id']}: unknown medium or process node")
    for key in ("components", "materials"):
        for row in p[key]:
            offer = row["offer"]
            if (offer["status"] == "on_request") != (offer["unit_price"] is None):
                errors.append(f"{row['id']}: inconsistent price status")
    for c in parts.values():
        unique(c["terminals"], c["id"] + " terminals")
    for loop in p["loops"]:
        if set(loop["members"]) - parts.keys():
            errors.append(f"{loop['id']}: unknown loop member")
    for row in p["placement"] + p["labels"]:
        if row["component"] not in parts:
            errors.append(f"{row['component']}: unknown panel component")
    for wire in p["connections"]:
        for side in ("from", "to"):
            end = wire[side]
            if end["terminal"] not in parts.get(end["component"], {}).get("terminals", []):
                errors.append(f"{wire['id']}.{side}: unknown component or terminal")
    return errors


def bom(p, path):
    rows = defaultdict(list)
    for kind in ("components", "materials"):
        for item in p[kind]:
            key = (kind, item["manufacturer"], item["order_code"], item.get("unit", "шт."))
            rows[key].append(item)
    with path.open("w", newline="", encoding="utf-8-sig") as out:
        writer = csv.writer(out, delimiter=";")
        writer.writerow(["Позиції", "Виробник", "Код", "Од.", "Кількість"])
        for (kind, maker, code, unit), items in rows.items():
            tags = ", ".join(i.get("tag", i["id"]) for i in items)
            qty = len(items) if kind == "components" else sum(Decimal(str(i["quantity"])) for i in items)
            writer.writerow([tags, maker, code, unit, qty])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("--bom", type=Path)
    args = parser.parse_args()
    if args.bom and args.bom.resolve() == args.project.resolve():
        parser.error("output must differ from input")
    try:
        data = json.loads(args.project.read_text(encoding="utf-8-sig"))
        errors = check(data)
        if errors:
            print("\n".join(errors), file=sys.stderr)
            return 1
        if args.bom:
            bom(data, args.bom)
        print(f"OK: {len(data['components'])} components, {len(data['connections'])} connections")
        return 0
    except (OSError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
