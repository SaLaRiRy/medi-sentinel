"""RAG 基础设施：文本分块与向量索引（TICKET-013）。

`chunking` 是纯 CPU 的确定性分块；`store` 是检索端口背后的窄端口；`chroma_adapter`
是本地持久化的 Chroma 适配器（与嵌入服务一起按需导入）。
"""
