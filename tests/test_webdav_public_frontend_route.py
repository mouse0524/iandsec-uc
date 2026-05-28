from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_SHARE_DOWNLOAD_ROUTE = "/public/webdav/share/download"


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_public_webdav_share_download_route_is_available_without_login():
    routes = _read("web/src/router/routes/index.js")
    auth_guard = _read("web/src/router/guard/auth-guard.js")

    assert PUBLIC_SHARE_DOWNLOAD_ROUTE in routes
    assert PUBLIC_SHARE_DOWNLOAD_ROUTE in auth_guard
    assert "export const WHITE_LIST" in auth_guard
    assert "const isWhiteListed = WHITE_LIST.includes(to.path)" in auth_guard
    assert "if (isWhiteListed) return true" in auth_guard

    router = _read("web/src/router/index.js")
    assert "import { WHITE_LIST } from './guard/auth-guard'" in router
    assert "if (isNullOrWhitespace(token))" in router
    assert "if (WHITE_LIST.includes(currentPath)) return" in router


def test_login_page_can_still_load_dynamic_routes_after_public_whitelist_change():
    router = _read("web/src/router/index.js")
    login_page = _read("web/src/views/login/index.vue")

    assert "await addDynamicRoutes()" in login_page
    assert router.index("const token = getToken()") < router.index("if (WHITE_LIST.includes(currentPath)) return")
    assert router.index("if (WHITE_LIST.includes(currentPath)) return") < router.index("router.addRoute(EMPTY_ROUTE)")


def test_share_record_copies_public_frontend_download_url():
    share_page = _read("web/src/views/system/webdav-share/index.vue")

    assert PUBLIC_SHARE_DOWNLOAD_ROUTE in share_page
    assert "return `${window.location.origin}/public/webdav/share/download${parsedUrl.search}`" in share_page


def test_settings_page_does_not_default_file_base_to_frontend_origin():
    settings_page = _read("web/src/views/system/settings/index.vue")

    assert "webdav_public_base_url" not in settings_page
    assert "公开下载 Base URL" not in settings_page
    assert "webdav_public_base_url: window.location.origin" not in settings_page
    assert "res.data?.webdav_public_base_url || window.location.origin" not in settings_page


def test_backend_generated_share_urls_use_public_frontend_route():
    webdav_api = _read("app/api/v1/webdav/webdav.py")

    assert 'PUBLIC_SHARE_DOWNLOAD_PATH = "/public/webdav/share/download"' in webdav_api
    assert '_build_public_share_download_url(str(data.get("code") or ""), sign_data)' in webdav_api
    assert '_build_public_share_download_url(str(item_dict.get("code") or ""), sign_data)' in webdav_api
