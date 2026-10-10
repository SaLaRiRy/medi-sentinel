"""本地交叉编码器重排（TICKET-AC-04）：bge-reranker-base 的 ONNX 推理。

本机实测（CPU）：

| 项 | 实测值 |
|---|---|
| 模型目录 | `C:\\Users\\87590\\models\\models\\BAAI--bge-reranker-base\\snapshots\\master` |
| ONNX 文件 | `onnx/model.onnx`，1112.5 MB，自带权重、单文件 |
| 加载耗时 | 2504 ms（一次性） |
| 推理耗时 | 单对 29.8 ms / 3 对 52.9 ms |
| 输入 | 只要 `input_ids` + `attention_mask`（连 `token_type_ids` 都不需要） |
| 输出 | `logits`，形状 `[batch, 1]` |

**`onnxruntime` / `tokenizers` 只允许出现在这里**（都在模块内部按需导入）：
`server/regression/ports.py` 有一条 AST 断言，回放路径不得引入外部依赖。

重排是**增强**：模型缺失、加载失败或推理异常时，调用方保持原序继续
（SPEC.md 3.6「降级不阻断」），绝不翻成 503/504——那是生成才能有的失败。
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class Reranker(Protocol):
    """把 `(query, documents)` 打成相关性分数，分数越大越相关。"""

    def score(self, query: str, documents: Sequence[str]) -> Sequence[float]: ...


class OnnxReranker:
    """懒加载的 ONNX 交叉编码器；构造时不碰磁盘，首次 `score` 才加载。"""

    def __init__(self, model_dir: str, *, max_length: int = 512) -> None:
        self._dir = Path(model_dir)
        self._max_length = max_length
        self._tokenizer = None
        self._session = None

    @property
    def model_path(self) -> Path:
        return self._dir / "onnx" / "model.onnx"

    def _ensure_loaded(self) -> None:
        if self._session is not None:
            return
        import onnxruntime as ort
        from tokenizers import Tokenizer

        tokenizer = Tokenizer.from_file(str(self._dir / "tokenizer.json"))
        tokenizer.enable_truncation(max_length=self._max_length)
        tokenizer.enable_padding(pad_id=0, pad_token="[PAD]")
        session = ort.InferenceSession(
            str(self.model_path), providers=["CPUExecutionProvider"]
        )
        self._tokenizer = tokenizer
        self._session = session

    def score(self, query: str, documents: Sequence[str]) -> list[float]:
        """一次前向算完整批（逐对调用会把固定开销乘 N 倍）。"""
        import numpy as np

        texts = list(documents)
        if not texts:
            return []
        self._ensure_loaded()
        encoded = [self._tokenizer.encode(query, text) for text in texts]
        width = max(len(item.ids) for item in encoded)
        input_ids = np.zeros((len(encoded), width), dtype=np.int64)
        attention_mask = np.zeros((len(encoded), width), dtype=np.int64)
        for row, item in enumerate(encoded):
            input_ids[row, : len(item.ids)] = item.ids
            attention_mask[row, : len(item.attention_mask)] = item.attention_mask
        logits = self._session.run(
            None, {"input_ids": input_ids, "attention_mask": attention_mask}
        )[0]
        return [float(value) for value in logits.reshape(-1)]

    def close(self) -> None:
        self._session = None
        self._tokenizer = None
