"""口令确认规则（`FUNCTIONAL_SPEC.md` 5.9「修改口令（管理员改他人）」）。

管理员为他人新建/改口令时，口令与确认口令必须同时提供且一致：缺确认口令 →
400「请填写确认密码」，两者不一致 → 400「两次密码输入不一致」。新建时两项由
请求 Schema 强制必填，这里的缺省分支只在更新（口令可选）时可达。
"""

from core.errors import ApiError


def ensure_password_confirmation(
    password: str, confirm_password: str | None
) -> None:
    if confirm_password is None:
        raise ApiError(400, "请填写确认密码")
    if password != confirm_password:
        raise ApiError(400, "两次密码输入不一致")
