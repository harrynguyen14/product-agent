from __future__ import annotations

import asyncio
from typing import Any, Callable, Coroutine

from pydantic import BaseModel, ConfigDict

from infrastructure.logging import get_logger

logger = get_logger("action_graph")


class GraphNode(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    node_id: str
    fn: Callable[..., Coroutine[Any, Any, Any]]
    dependent_ids: list[str] = []


class ActionGraph:
    def __init__(self):
        self._nodes: dict[str, GraphNode] = {}

    def add_node(self, node: GraphNode) -> "ActionGraph":
        self._nodes[node.node_id] = node
        return self

    def topological_layers(self) -> list[list[str]]:
        in_degree: dict[str, int] = {nid: 0 for nid in self._nodes}
        for node in self._nodes.values():
            in_degree[node.node_id] += len(node.dependent_ids)

        layers: list[list[str]] = []
        ready = [nid for nid, deg in in_degree.items() if deg == 0]

        while ready:
            layers.append(ready)
            next_ready: list[str] = []
            for nid in ready:
                for node in self._nodes.values():
                    if nid in node.dependent_ids:
                        in_degree[node.node_id] -= 1
                        if in_degree[node.node_id] == 0:
                            next_ready.append(node.node_id)
            ready = next_ready

        return layers

    async def run(self) -> dict[str, Any]:
        completed: dict[str, Any] = {}

        for layer_idx, layer in enumerate(self.topological_layers(), 1):
            logger.info("graph_layer", layer=layer_idx, nodes=layer)

            async def _run_node(nid: str) -> tuple[str, Any]:
                node = self._nodes[nid]
                upstream = {
                    dep_id: completed[dep_id]
                    for dep_id in node.dependent_ids
                    if dep_id in completed
                }
                return nid, await node.fn(upstream)

            for nid, result in await asyncio.gather(*[_run_node(nid) for nid in layer]):
                completed[nid] = result

        logger.info("graph_complete", total=len(completed))
        return completed
