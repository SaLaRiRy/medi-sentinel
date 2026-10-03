"""递归字符分块（TICKET-013，规则见 `FUNCTIONAL_SPEC.md` 5.5）。

块长 500 字符、重叠 80 字符，分隔符优先级 `\\n\\n → \\n → 。 → ！ → ？ → ； → 空格 → 空串`。
纯 CPU、无 I/O，因此可在不启动向量索引或嵌入服务的前提下单独测试
（`SPEC.md` 4.1 B-2）。

确定性规则：

- 按优先级找到文本中出现的第一个分隔符，把分隔符**留在前一段末尾**；
- 任一段仍超过块长时，用更低优先级的分隔符继续切；没有分隔符可用时按块长硬切；
- 相邻小段贪心合并到块长上限；新块以「前一块末尾至多 `chunk_overlap` 个字符」
  作为重叠开头。若这样会让新块超过块长，则放弃重叠（保证任何块都不超长）。
"""

from __future__ import annotations

from collections.abc import Sequence

CHUNK_SIZE = 500
CHUNK_OVERLAP = 80
DEFAULT_SEPARATORS: tuple[str, ...] = (
    "\n\n",
    "\n",
    "。",
    "！",
    "？",
    "；",
    " ",
    "",
)


def split_text(
    text: str,
    *,
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
    separators: Sequence[str] = DEFAULT_SEPARATORS,
) -> list[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size 必须为正整数")
    if not 0 <= chunk_overlap < chunk_size:
        raise ValueError("chunk_overlap 必须满足 0 ≤ overlap < chunk_size")
    if not text:
        return []
    pieces = _split_by_separators(text, tuple(separators), chunk_size)
    return _merge_pieces(pieces, chunk_size, chunk_overlap)


def _pick_separator(
    text: str, separators: Sequence[str]
) -> tuple[str, tuple[str, ...]]:
    for index, separator in enumerate(separators):
        if separator == "":
            return "", ()
        if separator in text:
            return separator, tuple(separators[index + 1 :])
    return "", ()


def _split_by_separators(
    text: str, separators: Sequence[str], chunk_size: int
) -> list[str]:
    if not text:
        return []
    separator, rest = _pick_separator(text, separators)
    if separator == "":
        return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]

    raw = text.split(separator)
    pieces = [part + separator for part in raw[:-1]] + [raw[-1]]
    out: list[str] = []
    for piece in pieces:
        if not piece:
            continue
        if len(piece) <= chunk_size:
            out.append(piece)
        elif rest:
            out.extend(_split_by_separators(piece, rest, chunk_size))
        else:
            out.extend(
                piece[i : i + chunk_size] for i in range(0, len(piece), chunk_size)
            )
    return out


def _merge_pieces(
    pieces: Sequence[str], chunk_size: int, chunk_overlap: int
) -> list[str]:
    chunks: list[str] = []
    current = ""
    for piece in pieces:
        if current and len(current) + len(piece) > chunk_size:
            chunks.append(current)
            current = _overlap_tail(current, chunk_overlap) + piece
            if len(current) > chunk_size:
                current = piece
        else:
            current += piece
    if current:
        chunks.append(current)
    return chunks


def _overlap_tail(text: str, chunk_overlap: int) -> str:
    return text[-chunk_overlap:] if chunk_overlap > 0 else ""
