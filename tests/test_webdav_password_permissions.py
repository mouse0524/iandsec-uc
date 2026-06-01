import ast
from pathlib import Path


INIT_APP_PATH = Path("app/core/init_app.py")


def _assigned_path_literals(target_name: str) -> set[str]:
    tree = ast.parse(INIT_APP_PATH.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == target_name for target in node.targets):
            continue
        return {item.value for item in ast.walk(node.value) if isinstance(item, ast.Constant) and isinstance(item.value, str)}
    raise AssertionError(f"{target_name} assignment not found")


def _async_function(name: str) -> ast.AsyncFunctionDef:
    tree = ast.parse(INIT_APP_PATH.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} function not found")


def _called_names(function_name: str) -> set[str]:
    names = set()
    for node in ast.walk(_async_function(function_name)):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            names.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            names.add(node.func.attr)
    return names


def test_regular_webdav_permissions_do_not_include_password_apis():
    webdav_paths = _assigned_path_literals("webdav_apis")

    assert "/api/v1/webdav/ops-password" not in webdav_paths
    assert "/api/v1/webdav/replace-decrypt-password" not in webdav_paths


def test_regular_webdav_menus_do_not_include_password_page():
    webdav_menu_components = _assigned_path_literals("webdav_menus")

    assert "/system/webdav-password" not in webdav_menu_components


def test_init_roles_does_not_scrub_manually_assigned_password_permissions():
    assert "_ensure_webdav_password_admin_only" not in _called_names("init_roles")


def test_password_permission_cleanup_is_not_registered():
    tree = ast.parse(INIT_APP_PATH.read_text(encoding="utf-8"))

    assert not any(
        isinstance(node, ast.AsyncFunctionDef) and node.name == "_ensure_webdav_password_admin_only"
        for node in ast.walk(tree)
    )
