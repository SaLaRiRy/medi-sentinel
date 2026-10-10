"""种子语料护栏（TICKET-01 / `.scratch/agentic-consult/issues/01-expand-knowledge-base.md`）。

`server/docs_seed/` 是知识库的种子来源，`scripts/init_knowledge.py` 按**文件名**幂等灌入。
这里只做**纯离线**的文件级断言——不碰数据库、嵌入服务与网络：

- 篇数与单篇长度够大，保证检索池不小于 `RETRIEVAL_TOP_K`（池子只有 3 条时
  `recall@5` 恒等于 100%，评测数字失去意义）；
- 文件名唯一（幂等键就是文件名）；
- 两篇内容完全相同会白白占用向量条目，等价于池子没扩大。

真正的「灌进活库并向量化到状态 2」由 `scripts/init_knowledge.py` 完成，不进测试套件。
"""

from pathlib import Path

SERVER_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = SERVER_ROOT / "docs_seed"

#: 票 01 的验收下限：≥10 篇、每篇 ≥500 字（500 字 ≈ 1 个 chunk，见 rag/chunking.py）。
MIN_DOCUMENTS = 10
MIN_CHARS = 500


def _documents() -> list[Path]:
    return sorted(DOCS_DIR.glob("*.md"))


def test_docs_seed_directory_exists():
    assert DOCS_DIR.is_dir(), f"缺少种子目录：{DOCS_DIR}"


def test_corpus_is_large_enough_for_recall_at_five():
    assert len(_documents()) >= MIN_DOCUMENTS


def test_every_document_has_a_retrievable_body():
    for path in _documents():
        text = path.read_text(encoding="utf-8")

        assert len(text) >= MIN_CHARS, f"{path.name} 只有 {len(text)} 字"


def test_document_names_are_unique_case_insensitively():
    lowered = [path.name.lower() for path in _documents()]

    assert len(lowered) == len(set(lowered))


def test_no_two_documents_share_the_same_body():
    bodies: dict[str, str] = {}
    for path in _documents():
        digest = path.read_text(encoding="utf-8").strip()
        assert digest not in bodies, f"{path.name} 与 {bodies.get(digest)} 正文完全相同"
        bodies[digest] = path.name
