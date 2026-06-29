## 2026-06-29 - Task: WebDAV public share Apple download fallback
### What was done
- Added Apple-device handling for public WebDAV share downloads: Apple user agents now receive a streamed backend response, while other devices keep the existing WebDAV direct redirect.
- Added focused tests for the Apple streaming path and the non-Apple redirect path.
- Documented the public share download behavior split for future operation and collaboration.

### Testing
- `python -m pytest tests\test_webdav_public_download.py` passed: 2 tests passed.
- `python -m compileall app` passed.

### Notes
- `app/api/v1/webdav/webdav.py`: added Apple user-agent detection and streamed response handling for public share downloads.
- `tests/test_webdav_public_download.py`: added regression tests for Apple streaming and non-Apple redirect behavior. Current `.gitignore` ignores `tests/*`, so this file will need explicit include handling or forced add if it must be committed.
- `docs/webdav-public-share-download.md`: documented the device-specific public download behavior and remaining credential-exposure boundary.
- Rollback: revert the changes to `app/api/v1/webdav/webdav.py`, remove `tests/test_webdav_public_download.py`, remove `docs/webdav-public-share-download.md`, and remove this `progress.md` entry if rolling back the task entirely.

## 2026-06-29 - Task: Include WebDAV public download regression test
### What was done
- Updated the test ignore allowlist so the WebDAV public download regression test can be tracked with the feature change.

### Testing
- `git check-ignore -v tests\test_webdav_public_download.py` returns no ignore match.
- `python -m pytest tests\test_webdav_public_download.py` passed: 2 tests passed.

### Notes
- `.gitignore`: added `tests/test_webdav_public_download.py` to the explicit allowlist under the ignored `tests/*` rule.
- `progress.md`: appended this review-fix record.
- Rollback: remove the `.gitignore` allowlist entry and this `progress.md` entry.

## 2026-06-29 - Task: Fix Apple WebDAV stream filename header
### What was done
- Fixed Apple-device WebDAV share streaming when the upstream WebDAV response provides a non-Latin `Content-Disposition` filename.
- The streamed download now always generates a safe RFC 5987 `filename*` header from the share file path instead of forwarding an upstream header that Starlette cannot encode.
- Added a regression test for Chinese filenames in Apple-device streaming downloads.

### Testing
- `python -m pytest tests\test_webdav_public_download.py` passed: 3 tests passed.
- `python -m compileall app` passed.

### Notes
- `app/api/v1/webdav/webdav.py`: stopped forwarding upstream `Content-Disposition` in the Apple streaming response and always emits an encoded download filename.
- `tests/test_webdav_public_download.py`: added a regression case for non-Latin upstream download filenames.
- `progress.md`: appended this production-error fix record.
- Rollback: restore upstream `Content-Disposition` passthrough in `_download_headers`, remove the new non-Latin filename test, and remove this `progress.md` entry.

## 2026-06-29 - Task: Add project management module
### What was done
- Added project and project activity backend models, controller validation, authenticated APIs, dynamic menu initialization, and role permission backfill for 管理员/客服/技术.
- Added configurable project products, project statuses, and project activity types under system settings/public config.
- Added frontend project list and activity record pages, including create/edit, status flow, assignment, and count links to ticket/activity details.
- Linked project issue/requirement counts to existing tickets by customer company and issue type instead of adding duplicate issue/requirement tables.

### Testing
- `python -m compileall app` passed.
- `python -m pytest tests\test_project_management.py` passed: 2 tests passed.
- `cd web && pnpm.cmd run build` passed with existing Vite chunk-size/UnoCSS deprecation warnings.
- `git diff --check` reported only Windows LF-to-CRLF working-copy warnings.

### Notes
- `docs/project-management.md`: documents permissions, configurable values, and ticket linkage rules.
- `.gitignore`: allowlisted `tests/test_project_management.py` so the focused regression test can be tracked.
- Rollback: remove the `project` API/router/pages/tests/docs, remove the project menu/API permission additions, and remove project-related settings/model fields.

## 2026-06-29 - Task: Adjust project fields
### What was done
- Removed the project-level customer company field from the project management flow.
- Split project version into server version and client version.
- Changed project products to a multi-select product-points list so each selected product has its own point count.
- Kept ticket linkage by matching existing ticket `company_name` against the project name.

### Testing
- `python -m py_compile app\models\admin.py app\schemas\projects.py app\controllers\project.py app\api\v1\projects\projects.py app\core\init_app.py` passed.
- `python -m pytest tests\test_project_management.py` passed: 2 tests passed.
- `cd web && pnpm.cmd run build` passed with existing Vite chunk-size/UnoCSS deprecation warnings.

### Notes
- Existing project table compatibility is handled by adding nullable `product_points`, `server_version`, and `client_version` columns if the earlier table already exists.
- Old project columns are intentionally not dropped during startup.
