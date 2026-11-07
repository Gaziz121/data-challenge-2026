"""Offline guard for model-facing strict JSON schemas. No network, no dependency.

`strict_issues` checks the structural subset our wire schemas rely on, using only
keywords already accepted by the live strict Responses API in this project
(`const` is not listed in the docs but was accepted in the 5d256ac call) and the
published limits, verified 2026-11-07 at
https://developers.openai.com/api/docs/guides/structured-outputs#supported-schemas :
5000 object properties, 10 nesting levels, 1000 enum values, 120000 characters of
property/definition names plus enum/const values. It cannot prove provider
acceptance; it prevents an obviously invalid schema from consuming an authorized
paid call. `conforms` is a small validator for exactly that subset.
"""

KEYWORDS = {"type", "properties", "required", "additionalProperties", "items", "anyOf", "enum",
            "const", "$ref", "$defs", "minItems", "maxItems", "minLength", "title", "description"}
# maxItems is documented as supported (verified 2026-11-07); first live use is atomic-v5.
LIMITS = {"properties": 5000, "depth": 10, "enum_values": 1000, "string_chars": 120000}


def _resolve(schema, root):
    while "$ref" in schema:
        name = schema["$ref"].split("/")[-1]
        schema = root["$defs"][name]
    return schema


def strict_issues(root):
    issues, totals = [], {"properties": 0, "enum_values": 0, "string_chars": 0}
    if root.get("type") != "object" or "anyOf" in root:
        issues.append("Root must be a plain object schema")
    totals["string_chars"] += sum(len(n) for n in root.get("$defs", {}))

    def walk(node, path):
        if not isinstance(node, dict):
            issues.append(f"{path}: schema must be an object")
            return
        unknown = set(node) - KEYWORDS
        if unknown:
            issues.append(f"{path}: unsupported keywords {sorted(unknown)}")
        if "$ref" in node and (len(node) > 1 or not node["$ref"].startswith("#/$defs/")
                               or node["$ref"].split("/")[-1] not in root.get("$defs", {})):
            issues.append(f"{path}: $ref must stand alone and resolve locally")
        if node.get("type") == "object":
            props = node.get("properties", {})
            totals["properties"] += len(props)
            totals["string_chars"] += sum(len(k) for k in props)
            if node.get("additionalProperties") is not False:
                issues.append(f"{path}: objects need additionalProperties=false")
            if node.get("required") != list(props):
                issues.append(f"{path}: every property must be required, in order")
            for key, value in props.items():
                walk(value, f"{path}.{key}")
        if node.get("type") == "array" and "items" not in node:
            issues.append(f"{path}: arrays need items")
        if "items" in node:
            walk(node["items"], f"{path}[]")
        for i, option in enumerate(node.get("anyOf", [])):
            walk(option, f"{path}|{i}")
        if "enum" in node:
            if not node["enum"]:
                issues.append(f"{path}: empty enum")
            totals["enum_values"] += len(node["enum"])
            totals["string_chars"] += sum(len(str(v)) for v in node["enum"])
        if "const" in node:
            totals["string_chars"] += len(str(node["const"]))

    walk({k: v for k, v in root.items() if k != "$defs"}, "$")
    for name, definition in root.get("$defs", {}).items():
        walk(definition, f"$defs.{name}")

    def depth(node, seen=()):
        node = _resolve(node, root) if "$ref" in node else node
        here = 1 if node.get("type") == "object" else 0
        children = list(node.get("properties", {}).values()) + node.get("anyOf", []) + (
            [node["items"]] if "items" in node else [])
        refs = tuple(seen) + ((id(node),) if here else ())
        return here + max((depth(c, refs) for c in children if id(c) not in seen), default=0)

    if depth(root) > LIMITS["depth"]:
        issues.append("Object nesting exceeds strict-mode depth")
    for key in ("properties", "enum_values", "string_chars"):
        if totals[key] > LIMITS[key]:
            issues.append(f"{key}={totals[key]} exceeds published limit {LIMITS[key]}")
    return issues


def conforms(instance, schema, root=None):
    root = root or schema
    schema = _resolve(schema, root)
    if "anyOf" in schema:
        return any(conforms(instance, option, root) for option in schema["anyOf"])
    kind = schema.get("type")
    checks = {"object": lambda v: isinstance(v, dict), "array": lambda v: isinstance(v, list),
              "string": lambda v: isinstance(v, str), "null": lambda v: v is None,
              "boolean": lambda v: isinstance(v, bool),
              "integer": lambda v: type(v) is int, "number": lambda v: type(v) in (int, float)}
    if kind is not None and not checks[kind](instance):
        return False
    if "enum" in schema and not any(type(instance) is type(v) and instance == v for v in schema["enum"]):
        return False
    if "const" in schema and not (type(instance) is type(schema["const"]) and instance == schema["const"]):
        return False
    if kind == "string" and len(instance) < schema.get("minLength", 0):
        return False
    if kind == "object":
        props = schema.get("properties", {})
        if set(instance) != set(props) and (schema.get("additionalProperties") is False or not set(props) <= set(instance)):
            return False
        return all(conforms(instance[k], v, root) for k, v in props.items())
    if kind == "array":
        return schema.get("minItems", 0) <= len(instance) <= schema.get("maxItems", len(instance)) and all(conforms(i, schema["items"], root) for i in instance)
    return True
