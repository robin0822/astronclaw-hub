import ast
from pathlib import Path


def test_non_dev_write_routes_record_audit_trail():
    source = Path("app/api/v1/routes.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    audit_markers = {
        "audit",
        "record_sensitive_event",
        "channel_audit",
        "LoginLog",
        "record_permission_denied",
        "record_seat_event",
    }
    missing = []
    for node in module.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        route_decorators = []
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            if not isinstance(decorator.func, ast.Attribute):
                continue
            if decorator.func.attr not in {"post", "put", "delete", "patch"}:
                continue
            path = decorator.args[0].value if decorator.args and isinstance(decorator.args[0], ast.Constant) else ""
            route_decorators.append((decorator.func.attr.upper(), path))
        if not route_decorators:
            continue
        if all(path.startswith("/dev/") for _, path in route_decorators):
            continue
        names = {item.id for item in ast.walk(node) if isinstance(item, ast.Name)}
        if not (names & audit_markers):
            missing.extend(f"{method} {path} -> {node.name}:{node.lineno}" for method, path in route_decorators)

    assert not missing
