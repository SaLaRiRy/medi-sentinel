# ADR-0002: 迁移脚本目录命名为 `migrations/`

**状态**：已接受
**日期**：2026-10-03
**相关**：TICKET-001（工程骨架与契约 seam）、ADR-0001

## 背景

ADR-0001 选定 Alembic 管理 Schema 迁移。Alembic 的默认约定是把脚本目录命名为 `alembic/`，而本项目的后端测试通过 `pyproject.toml` 里的 `pythonpath = ["."]` 把 `server/` 放进 `sys.path`。

## 决策

迁移脚本目录命名为 `server/migrations/`，不叫 `server/alembic/`。

## 理由

- 目录若叫 `alembic/`，当 `server/` 位于 `sys.path` 上时会**遮蔽真正安装的 `alembic` 包**：`import alembic` 解析到本地目录，随之报出与真实原因无关的导入错误。
- 这个坑会以两种面貌出现——测试收集阶段报错、alembic 自身运行时报导入异常——定位成本远高于规避成本。
- 目录名不影响任何对外命令：`alembic.ini` 用 `%(here)s/migrations` 锚定脚本位置，`alembic upgrade head` 的用法完全不变。

## 后果

- 阅读 Alembic 文档或教程时，示例中的 `alembic/` 与本仓库不一致；**`alembic.ini` 的 `script_location` 是权威位置**。
- 无需在 `sys.path` 上做排除，也无需重命名已安装的包。
