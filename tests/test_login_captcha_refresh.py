from pathlib import Path


LOGIN_VIEW = Path(__file__).resolve().parents[1] / "web" / "src" / "views" / "login" / "index.vue"


def test_registration_modal_close_refreshes_login_captcha():
    source = LOGIN_VIEW.read_text(encoding="utf-8")

    assert "async function refreshLoginCaptcha()" in source
    assert "await refreshLoginCaptcha()" in source
    assert "loginInfo.value.captcha_code = ''" in source


def test_login_without_agreement_confirms_and_continues():
    source = LOGIN_VIEW.read_text(encoding="utf-8")

    assert "$dialog.confirm({" in source
    assert "content: '请阅读并同意用户服务协议与隐私政策后继续登录'" in source
    assert "loginAgree.value = true" in source
    assert "return handleLogin()" in source
