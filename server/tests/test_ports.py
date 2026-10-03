"""B-3: the three narrow ports that make 'was the LLM called at all?' countable."""

from skills.ports import GraphPort, LlmPort, RetrievalPort
from tests.doubles import (
    CountingGraphPort,
    CountingRetrievalPort,
    HitsGraphPort,
    ThrowingGraphPort,
    ThrowingLlmPort,
)


def test_counting_fakes_satisfy_the_port_contracts():
    assert isinstance(CountingGraphPort(), GraphPort)
    assert isinstance(HitsGraphPort(), GraphPort)
    assert isinstance(ThrowingGraphPort(), GraphPort)
    assert isinstance(CountingRetrievalPort(), RetrievalPort)
    assert isinstance(ThrowingLlmPort(), LlmPort)


async def test_graph_port_records_what_was_asked():
    port = CountingGraphPort()

    await port.infer_diseases(["头痛"])
    await port.neighbors("高血压", depth=2)

    assert port.calls == [("infer_diseases", ("头痛",)), ("neighbors", "高血压", 2)]
