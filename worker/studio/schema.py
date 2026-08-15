from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from api.app.db.taxonomy import FIELD_KEY_PATTERN, load_studio_schema

VALID_DTYPES = {"text", "number", "integer", "boolean", "date"}


def lint_schema(path: Path | None = None) -> list[str]:
    schema = load_studio_schema(path)
    errors: list[str] = []
    fields = schema.get("fields", [])
    keys = [str(field.get("field_key", "")) for field in fields]
    duplicates = [key for key, count in Counter(keys).items() if count > 1]
    errors.extend(f"duplicate field_key: {key}" for key in sorted(duplicates))
    known = set(keys)
    concepts: set[str] = set()
    for field in fields:
        key = str(field.get("field_key", ""))
        if not FIELD_KEY_PATTERN.fullmatch(key):
            errors.append(f"invalid field_key: {key}")
        if field.get("dtype") not in VALID_DTYPES:
            errors.append(f"invalid dtype for {key}: {field.get('dtype')}")
        concept = field.get("xbrl_concept")
        if not concept:
            errors.append(f"missing xbrl_concept: {key}")
        elif str(concept) in concepts:
            errors.append(f"duplicate xbrl_concept: {concept}")
        concepts.add(str(concept))
        if field.get("unit") and not field.get("unit_family"):
            errors.append(f"unit without unit_family: {key}")
    for relation in schema.get("relations", []):
        for reference in [relation.get("target"), *relation.get("operands", [])]:
            if reference not in known:
                errors.append(
                    f"relation {relation.get('key')} references unknown field: {reference}"
                )
    section_keys = {str(item["key"]) for item in schema.get("sections", [])}
    if not {"a.entity", "b.policy", "core"}.issubset(section_keys):
        errors.append("required Section A, Section B and Core section metadata is missing")
    if len(fields) < 250:
        errors.append(f"full format encode expected at least 250 fields, found {len(fields)}")
    return errors


def schema_stats(path: Path | None = None) -> dict[str, Any]:
    schema = load_studio_schema(path)
    fields = schema["fields"]
    return {
        "schema_version": schema["schema_version"],
        "taxonomy_release": schema["taxonomy"]["release"],
        "sections": len(schema.get("sections", [])),
        "fields": len(fields),
        "relations": len(schema.get("relations", [])),
        "core_fields": sum(bool(field.get("core_kpi")) for field in fields),
    }


def main() -> None:
    errors = lint_schema()
    if errors:
        raise SystemExit("\n".join(errors))
    stats = schema_stats()
    print(
        "Schema {schema_version}: {sections} sections, {fields} fields, "
        "{relations} relations, {core_fields} Core fields".format(**stats)
    )


if __name__ == "__main__":
    main()
