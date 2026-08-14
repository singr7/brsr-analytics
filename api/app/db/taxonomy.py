import re
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from api.app.models import FieldDef

REPO_ROOT = Path(__file__).resolve().parents[3]
FIELD_KEY_PATTERN = re.compile(r"^(a|p[1-9])\.[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")


def load_form_schema(path: Path | None = None) -> tuple[str, list[dict[str, Any]]]:
    source = path or REPO_ROOT / "taxonomy" / "form_schema.yaml"
    document = yaml.safe_load(source.read_text(encoding="utf-8"))
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
    return version, fields


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
