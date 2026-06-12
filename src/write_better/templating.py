"""Template engine (Features 4 & 5) — versioned prompt configs, not model code.

Templates are YAML files under ``write_better/templates/<category>/*.yaml``,
executed through the existing ``write`` service. Adding a YAML file makes the
template appear in the API, CLI, and UI with **no code change** — the ``fields``
schema drives dynamic forms.

To stay stdlib-only ([VERIFY]: no pyyaml dependency), this parses the constrained
YAML shape these templates use: top-level scalars, a ``fields:`` list of inline
flow-maps, a ``defaults:`` flow-map, a ``prompt: |`` block scalar, and ``variants``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


# --- minimal YAML subset ------------------------------------------------------

def _split_top(s: str) -> list[str]:
    out, depth, cur, q = [], 0, "", None
    for c in s:
        if q:
            cur += c
            if c == q:
                q = None
            continue
        if c in "\"'":
            q = c; cur += c; continue
        if c in "[{":
            depth += 1; cur += c; continue
        if c in "]}":
            depth -= 1; cur += c; continue
        if c == "," and depth == 0:
            out.append(cur); cur = ""; continue
        cur += c
    if cur.strip():
        out.append(cur)
    return out


def _scalar(s: str):
    s = s.strip()
    if not s:
        return ""
    if s[0] in "{[":
        return _flow(s)
    if s.lower() in ("true", "false"):
        return s.lower() == "true"
    if re.fullmatch(r"-?\d+", s):
        return int(s)
    if len(s) >= 2 and s[0] in "\"'" and s[-1] == s[0]:
        return s[1:-1]
    return s


def _flow(s: str):
    s = s.strip()
    if s.startswith("{"):
        d = {}
        for part in _split_top(s[1:-1]):
            if not part.strip():
                continue
            k, _, v = part.partition(":")
            d[k.strip()] = _scalar(v.strip())
        return d
    if s.startswith("["):
        return [_scalar(x) for x in _split_top(s[1:-1])]
    return _scalar(s)


def parse_yaml(text: str) -> dict:
    lines = text.split("\n")
    root: dict = {}
    i, n = 0, len(lines)

    def indent(s):
        return len(s) - len(s.lstrip(" "))

    while i < n:
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#") or indent(line) != 0:
            i += 1
            continue
        key, _, rest = line.strip().partition(":")
        key, rest = key.strip(), rest.strip()
        if rest == "|":
            i += 1
            block = []
            while i < n and (not lines[i].strip() or indent(lines[i]) > 0):
                block.append(lines[i]); i += 1
            base = min((indent(l) for l in block if l.strip()), default=0)
            root[key] = "\n".join(l[base:] if l.strip() else "" for l in block).strip("\n")
            continue
        if rest == "":
            i += 1
            items, mp, is_list = [], {}, None
            while i < n and (not lines[i].strip() or indent(lines[i]) > 0):
                sub = lines[i].strip()
                i += 1
                if not sub or sub.startswith("#"):
                    continue
                if sub.startswith("- "):
                    is_list = True
                    items.append(_scalar(sub[2:].strip()))
                else:
                    is_list = False
                    k, _, v = sub.partition(":")
                    mp[k.strip()] = _scalar(v.strip())
            root[key] = items if is_list else mp
            continue
        root[key] = _scalar(rest)
        i += 1
    return root


# --- templates ----------------------------------------------------------------

@dataclass(frozen=True)
class Template:
    id: str
    name: str
    category: str
    description: str
    fields: tuple
    defaults: dict
    prompt: str
    variants: int

    def schema(self) -> dict:
        return {
            "id": self.id, "name": self.name, "category": self.category,
            "description": self.description, "fields": list(self.fields),
            "defaults": self.defaults, "variants": self.variants,
        }


def _from_yaml(data: dict) -> Template:
    return Template(
        id=data["id"], name=data.get("name", data["id"]),
        category=data.get("category", "general"),
        description=data.get("description", ""),
        fields=tuple(data.get("fields", [])),
        defaults=data.get("defaults", {}) or {},
        prompt=data.get("prompt", ""),
        variants=int(data.get("variants", 1) or 1),
    )


@lru_cache(maxsize=1)
def load_templates() -> dict:
    out = {}
    if _TEMPLATES_DIR.is_dir():
        for path in sorted(_TEMPLATES_DIR.glob("**/*.yaml")):
            data = parse_yaml(path.read_text(encoding="utf-8"))
            if data.get("id"):
                out[data["id"]] = _from_yaml(data)
    return out


def list_templates(category: str | None = None) -> list[dict]:
    tpls = load_templates().values()
    if category:
        tpls = [t for t in tpls if t.category == category]
    return [t.schema() for t in sorted(tpls, key=lambda t: (t.category, t.name))]


def get_template(template_id: str) -> Template | None:
    return load_templates().get(template_id)


class MissingFields(Exception):
    def __init__(self, template: Template, missing: list[str]):
        super().__init__(f"missing required fields: {', '.join(missing)}")
        self.template = template
        self.missing = missing


def validate_and_render(template: Template, values: dict) -> str:
    values = values or {}
    missing = [f["key"] for f in template.fields
               if f.get("required") and not str(values.get(f["key"], "")).strip()]
    if missing:
        raise MissingFields(template, missing)
    # defaults for unset optional fields
    filled = {}
    for f in template.fields:
        v = values.get(f["key"])
        if (v is None or v == "") and "default" in f:
            v = f["default"]
        filled[f["key"]] = "" if v is None else str(v)
    return render_prompt(template.prompt, filled)


def render_prompt(prompt: str, values: dict) -> str:
    def truthy(key):
        return bool(str(values.get(key, "")).strip())

    # {{#key}}...{{/key}} → keep inner if truthy; {{^key}}...{{/key}} → if falsy
    def positive(m):
        return _subst(m.group(2), values) if truthy(m.group(1)) else ""

    def inverted(m):
        return _subst(m.group(2), values) if not truthy(m.group(1)) else ""

    text = re.sub(r"\{\{#(\w+)\}\}(.*?)\{\{/\1\}\}", positive, prompt, flags=re.DOTALL)
    text = re.sub(r"\{\{\^(\w+)\}\}(.*?)\{\{/\1\}\}", inverted, text, flags=re.DOTALL)
    return _subst(text, values).strip()


def _subst(text: str, values: dict) -> str:
    return re.sub(r"\{(\w+)\}", lambda m: str(values.get(m.group(1), m.group(0))), text)
