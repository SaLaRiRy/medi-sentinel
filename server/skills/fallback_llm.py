"""备用模型故障转移（TICKET-AC-08）。

**这不是"降级"**：`SPEC.md` 5.2 的原文是「大模型生成不可用无法降级」——那份约束
针对的是「生成能力消失」（只能 503 / 504）。本模块做的是**故障转移**：主执行单元
连不上时换成同一家 API 的另一个模型名，**生成能力一直都在**，所以既有的错误契约
（超时 → 504、不可用 → 503、`done`/`error` 互斥）一个字都不改。

切换的前提是**主模型一个字都没吐**：`orchestration/skill.py` 边收边推，已经推出的
分块无法收回，中途换模型会让前端看到两段拼接的回答，因此那种情况直接外抛。
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from skills.ports import LlmPort


class FallbackLlmAdapter:
    """主模型失败且**尚未吐字**时切到备用模型。"""

    def __init__(self, primary: LlmPort, secondary: LlmPort) -> None:
        self._primary = primary
        self._secondary = secondary

    async def stream(self, prompt: str) -> AsyncIterator[str]:
        emitted = False
        try:
            async for chunk in self._primary.stream(prompt):
                emitted = True
                yield chunk
            return
        except Exception:  # noqa: BLE001 - 主执行单元失败的统一下场
            if emitted:
                # 已经吐字：不能换模型（前端会看到拼接内容），如实外抛。
                raise
        async for chunk in self._secondary.stream(prompt):
            yield chunk

    async def close(self) -> None:
        for adapter in (self._primary, self._secondary):
            close = getattr(adapter, "close", None)
            if callable(close):
                await close()
