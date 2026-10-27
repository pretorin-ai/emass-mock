"""Validation derived from the vendored MITRE eMASS OpenAPI document.

Every stateful handler validates its request body against the spec operation
it implements, and the test suite validates the mock's own responses the same
way. Nothing about the eMASS contract is hand-written here: the schemas come
from ``spec/eMASSRestOpenApi.yaml`` (a byte-identical copy of
``vendor/emass_client/eMASSRestOpenApi.yaml``, kept in the package so an
installed wheel carries it).

The document is OpenAPI 3.0.3, which is not quite JSON Schema. ``_to_jsonschema``
bridges the gap:

* ``nullable: true`` becomes ``type: [T, "null"]`` (and ``null`` joins ``enum``).
* ``allOf`` of plain property bags (``ControlsRequiredFields`` and friends)
  is merged into one object schema. Left as ``allOf``, an
  ``additionalProperties: false`` on any branch would reject every property
  declared by the other branches.
* The spec puts ``required`` and ``additionalProperties: false`` on the
  *array* request bodies, where JSON Schema ignores them. They are hoisted
  into ``items`` so they bind to each row, which is what the authors meant.
* A field that is listed in ``required`` but not declared under
  ``properties`` is added as an unconstrained property so the strict
  ``additionalProperties: false`` cannot contradict ``required``.

Unknown fields are rejected by default (``EMASS_MOCK_UNKNOWN_FIELDS=reject``).
Set ``EMASS_MOCK_UNKNOWN_FIELDS=allow`` to only enforce types, enums, and
required fields. See ``docs/live-api-observations.md`` for where the live API
is known or suspected to differ from the spec.
"""

from __future__ import annotations

import copy
import os
from collections.abc import Iterable
from functools import cache, lru_cache
from importlib import resources
from typing import Any

import yaml
from jsonschema import Draft7Validator
from jsonschema.exceptions import ValidationError

SPEC_FILENAME = "eMASSRestOpenApi.yaml"

# ``Errors`` in the spec is capped at 25 items; keep our messages within that.
MAX_ERRORS = 25

_HTTP_METHODS = {"get", "post", "put", "delete", "patch"}

# OpenAPI-only or documentation-only keys that JSON Schema must not see.
_DROP_KEYS = frozenset(
    {"x-faker", "example", "examples", "title", "description", "format", "default", "xml"}
)
# Keys that make an ``allOf`` branch a mergeable property bag.
_BAG_KEYS = frozenset({"properties", "required", "type", "additionalProperties", "nullable"})


def spec_path() -> str:
    """Location of the OpenAPI document; ``EMASS_MOCK_SPEC_PATH`` overrides the packaged copy."""
    override = os.getenv("EMASS_MOCK_SPEC_PATH")
    if override:
        return override
    return str(resources.files("emass_mock") / "spec" / SPEC_FILENAME)


@lru_cache(maxsize=1)
def load_spec() -> dict[str, Any]:
    loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
    with open(spec_path(), encoding="utf-8") as handle:
        return yaml.load(handle, Loader=loader)


def spec_version() -> str:
    """The eMASS API version the vendored document declares (``info.version``)."""
    return str(load_spec()["info"]["version"])


@lru_cache(maxsize=1)
def _operations() -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for path, item in load_spec()["paths"].items():
        for method, op in item.items():
            if method in _HTTP_METHODS and isinstance(op, dict) and op.get("operationId"):
                found[op["operationId"]] = {
                    "path": path,
                    "method": method.upper(),
                    "op": op,
                    "path_item": item,
                }
    return found


def operation(operation_id: str) -> dict[str, Any]:
    """Look up an operation by ``operationId``; raises ``KeyError`` for an unknown id."""
    try:
        return _operations()[operation_id]
    except KeyError:
        raise KeyError(f"operationId {operation_id!r} is not in the vendored spec") from None


def operation_ids() -> list[str]:
    return sorted(_operations())


# ---------------------------------------------------------------------------
# $ref inlining and OpenAPI → JSON Schema normalization
# ---------------------------------------------------------------------------


def _resolve_ref(ref: str) -> Any:
    if not ref.startswith("#/"):
        raise ValueError(f"only local $ref values are supported, got {ref!r}")
    node: Any = load_spec()
    for part in ref[2:].split("/"):
        node = node[part.replace("~1", "/").replace("~0", "~")]
    return node


def _inline(node: Any, depth: int = 0) -> Any:
    if depth > 64:
        raise RecursionError("$ref cycle while inlining the eMASS spec")
    if isinstance(node, dict):
        if "$ref" in node:
            target = _resolve_ref(node["$ref"])
            merged = {**target, **{k: v for k, v in node.items() if k != "$ref"}}
            return _inline(merged, depth + 1)
        return {key: _inline(value, depth + 1) for key, value in node.items()}
    if isinstance(node, list):
        return [_inline(value, depth + 1) for value in node]
    return node


def _merge_all_of(node: dict[str, Any]) -> dict[str, Any]:
    branches = node["allOf"]
    if not all(isinstance(b, dict) and set(b) <= _BAG_KEYS for b in branches):
        return node
    merged = {key: value for key, value in node.items() if key != "allOf"}
    properties: dict[str, Any] = dict(merged.get("properties", {}))
    required = set(merged.get("required", []))
    for branch in branches:
        properties.update(branch.get("properties", {}))
        required.update(branch.get("required", []))
        if branch.get("additionalProperties") is False:
            merged["additionalProperties"] = False
    merged["properties"] = properties
    if required:
        merged["required"] = sorted(required)
    merged.setdefault("type", "object")
    return merged


def _to_jsonschema(node: Any) -> Any:
    if isinstance(node, list):
        return [_to_jsonschema(value) for value in node]
    if not isinstance(node, dict):
        return node

    node = {key: value for key, value in node.items() if key not in _DROP_KEYS}
    if "allOf" in node:
        node = _merge_all_of(node)

    if node.pop("nullable", False) and "type" in node:
        declared = node["type"]
        types = [declared] if isinstance(declared, str) else list(declared)
        if "null" not in types:
            types.append("null")
        node["type"] = types
        if "enum" in node and None not in node["enum"]:
            node["enum"] = [*node["enum"], None]

    if node.get("type") == "array" and isinstance(node.get("items"), dict):
        hoisted_required = node.pop("required", None)
        hoisted_additional = node.pop("additionalProperties", None)
        items = dict(node["items"])
        if hoisted_required:
            items["required"] = sorted(set(items.get("required", [])) | set(hoisted_required))
        if hoisted_additional is not None and "additionalProperties" not in items:
            items["additionalProperties"] = hoisted_additional
        node["items"] = items

    out: dict[str, Any] = {}
    for key, value in node.items():
        if key == "properties":
            out[key] = {name: _to_jsonschema(schema) for name, schema in value.items()}
        elif key in {"items", "additionalProperties", "not"} and isinstance(value, dict):
            out[key] = _to_jsonschema(value)
        elif key in {"allOf", "anyOf", "oneOf"}:
            out[key] = [_to_jsonschema(branch) for branch in value]
        else:
            out[key] = value

    if "properties" in out or out.get("required"):
        out.setdefault("type", "object")
        if out.get("additionalProperties") is False:
            properties = dict(out.get("properties", {}))
            for name in out.get("required", []):
                properties.setdefault(name, {})
            out["properties"] = properties
    return out


def _relax_unknown_fields(schema: Any) -> Any:
    """Drop every ``additionalProperties: false`` so unknown fields pass."""
    if isinstance(schema, dict):
        return {
            key: _relax_unknown_fields(value)
            for key, value in schema.items()
            if not (key == "additionalProperties" and value is False)
        }
    if isinstance(schema, list):
        return [_relax_unknown_fields(value) for value in schema]
    return schema


def compile_schema(openapi_schema: dict[str, Any], *, strict: bool = True) -> dict[str, Any]:
    """Turn an OpenAPI 3.0 schema fragment into a Draft 7 JSON Schema."""
    schema = _to_jsonschema(_inline(copy.deepcopy(openapi_schema)))
    if not strict:
        schema = _relax_unknown_fields(schema)
    Draft7Validator.check_schema(schema)
    return schema


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------


def request_body_schema(
    operation_id: str, content_type: str | None = None
) -> dict[str, Any] | None:
    """Raw OpenAPI schema of an operation's request body, or ``None`` if it has none."""
    body = operation(operation_id)["op"].get("requestBody")
    if not body:
        return None
    body = _inline(body)
    content = body.get("content", {})
    if content_type is not None:
        media = content.get(content_type)
    else:
        media = next(iter(content.values()), None)
    if not media or "schema" not in media:
        return None
    return media["schema"]


def multipart_file_parts(operation_id: str) -> list[str]:
    """Names of the binary parts a multipart operation declares (``filename`` in v3.22)."""
    schema = request_body_schema(operation_id, "multipart/form-data")
    if not schema:
        return []
    return [
        name
        for name, prop in schema.get("properties", {}).items()
        if isinstance(prop, dict) and prop.get("format") == "binary"
    ]


@cache
def _request_validator(operation_id: str, strict: bool) -> Draft7Validator | None:
    schema = request_body_schema(operation_id, "application/json")
    if schema is None:
        return None
    return Draft7Validator(compile_schema(schema, strict=strict))


def validate_request(operation_id: str, payload: Any, *, strict: bool | None = None) -> list[str]:
    """Validate a JSON request body; returns human-readable messages, empty when valid."""
    if strict is None:
        strict = unknown_fields_rejected()
    validator = _request_validator(operation_id, strict)
    if validator is None:
        return []
    return format_errors(validator.iter_errors(payload))


def unknown_fields_rejected() -> bool:
    return os.getenv("EMASS_MOCK_UNKNOWN_FIELDS", "reject").strip().lower() != "allow"


# ---------------------------------------------------------------------------
# Responses (used by the test suite to keep the mock honest)
# ---------------------------------------------------------------------------


def response_schema(operation_id: str, status: int = 200) -> dict[str, Any] | None:
    responses = operation(operation_id)["op"].get("responses", {})
    response = responses.get(str(status))
    if response is None:
        return None
    response = _inline(response)
    media = response.get("content", {}).get("application/json")
    if not media or "schema" not in media:
        return None
    return media["schema"]


@cache
def _response_validator(operation_id: str, status: int) -> Draft7Validator | None:
    schema = response_schema(operation_id, status)
    if schema is None:
        return None
    return Draft7Validator(compile_schema(schema, strict=True))


def validate_response(operation_id: str, body: Any, status: int = 200) -> list[str]:
    """Validate a response body against the spec's declared response schema."""
    validator = _response_validator(operation_id, status)
    if validator is None:
        return [f"{operation_id} declares no application/json schema for status {status}"]
    return format_errors(validator.iter_errors(body))


# ---------------------------------------------------------------------------
# Parameters
# ---------------------------------------------------------------------------


def parameters(operation_id: str) -> dict[str, dict[str, Any]]:
    """Query and path parameters by name, path-item level merged with operation level."""
    found = operation(operation_id)
    merged: dict[str, dict[str, Any]] = {}
    for source in (found["path_item"].get("parameters", []), found["op"].get("parameters", [])):
        for raw in source:
            param = _inline(raw)
            merged[param["name"]] = param
    return merged


def query_enum(operation_id: str, name: str) -> list[Any] | None:
    param = parameters(operation_id).get(name)
    if not param:
        return None
    return param.get("schema", {}).get("enum")


# ---------------------------------------------------------------------------
# Error formatting
# ---------------------------------------------------------------------------


def format_errors(errors: Iterable[ValidationError]) -> list[str]:
    messages: list[str] = []
    for err in sorted(errors, key=lambda e: [str(p) for p in e.absolute_path]):
        location = "/".join(str(part) for part in err.absolute_path) or "$"
        messages.append(f"{location}: {err.message}")
        if len(messages) >= MAX_ERRORS:
            break
    return messages
