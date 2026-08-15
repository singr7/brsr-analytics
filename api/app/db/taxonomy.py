import re
from itertools import product
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from api.app.models import FieldDef

REPO_ROOT = Path(__file__).resolve().parents[3]
FIELD_KEY_PATTERN = re.compile(r"^(a|b|p[1-9])\.[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")


def load_studio_schema(path: Path | None = None) -> dict[str, Any]:
    source = path or REPO_ROOT / "taxonomy" / "form_schema.yaml"
    document = yaml.safe_load(source.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("form_schema must be a mapping")
    merged = dict(document)
    for relative in document.get("includes", []):
        fragment = yaml.safe_load((source.parent / str(relative)).read_text(encoding="utf-8"))
        if not isinstance(fragment, dict):
            raise ValueError(f"Schema include must be a mapping: {relative}")
        for key, value in fragment.items():
            if isinstance(value, list):
                merged.setdefault(key, []).extend(value)
            elif key not in merged:
                merged[key] = value
    fields = list(merged.get("fields", []))
    for template in merged.get("field_templates", []):
        dimensions = template["items"]
        names = list(dimensions)
        for values in product(*(dimensions[name] for name in names)):
            context: dict[str, object] = {}
            item_data: dict[str, object] = {}
            for name, value in zip(names, values, strict=True):
                if isinstance(value, dict):
                    context[name] = value["key"]
                    item_data.update(value)
                else:
                    context[name] = value
                    if name.endswith("s"):
                        context[name[:-1]] = value
            field_key = str(template["key_pattern"]).format(**context)
            principle = str(template["principle_pattern"]).format(**context)
            fields.append(
                {
                    "field_key": field_key,
                    "principle": principle,
                    "section": template["section"],
                    "label": item_data.get("label", field_key),
                    "dtype": item_data.get("dtype", "text"),
                    "unit_family": item_data.get("unit_family"),
                    "unit": item_data.get("unit"),
                    "core_kpi": bool(item_data.get("core_kpi", False)),
                    "xbrl_concept": "BRSR_" + field_key.replace(".", "_"),
                    "required": item_data.get("required", True),
                    **{
                        key: item_data[key]
                        for key in ("condition", "leadership", "repeating_group")
                        if key in item_data
                    },
                }
            )
    core_fields = set(merged.get("core_fields", []))
    for field in fields:
        if field["field_key"] in core_fields:
            field["core_kpi"] = True
    merged["fields"] = fields
    return merged


def load_form_schema(path: Path | None = None) -> tuple[str, list[dict[str, Any]]]:
    document = load_studio_schema(path)
    version = str(document["schema_version"])
    fields = document["fields"]
    if not isinstance(fields, list):
        raise ValueError("form_schema fields must be a list")
    keys: set[str] = set()
    for field in fields:
        key = str(field["field_key"])
        if not FIELD_KEY_PATTERN.fullmatch(key):
            raise ValueError(f"Invalid field_key: {key}")
        if key in keys:
            raise ValueError(f"Duplicate field_key: {key}")
        keys.add(key)
    database_keys = {
        "field_key",
        "principle",
        "section",
        "label",
        "dtype",
        "unit_family",
        "unit",
        "core_kpi",
        "xbrl_concept",
    }
    return version, [{key: field.get(key) for key in database_keys} for field in fields]


async def upsert_field_defs(session: AsyncSession, path: Path | None = None) -> int:
    version, fields = load_form_schema(path)
    for field in fields:
        values = {**field, "schema_version": version}
        statement = insert(FieldDef).values(**values)
        await session.execute(
            statement.on_conflict_do_update(
                index_elements=[FieldDef.field_key],
                set_={column: values[column] for column in values if column != "field_key"},
            )
        )
    return len(fields)
