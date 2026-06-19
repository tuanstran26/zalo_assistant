from __future__ import annotations

from types import ModuleType
from typing import Mapping

import nodes.excel_vector_search_node_handler as excel_vector_search_node_handler
import nodes.function_node_handler as function_node_handler
import nodes.llm_node_handler as llm_node_handler
import nodes.supabase_query_node_handler as supabase_query_node_handler
import nodes.switch_node_handler as switch_node_handler
import nodes.vector_search_node_handler as vector_search_node_handler


DEFAULT_NODE_HANDLERS: dict[str, ModuleType] = {
    "llm": llm_node_handler,
    "switch": switch_node_handler,
    "vector_search": vector_search_node_handler,
    "function": function_node_handler,
    "excel_search": excel_vector_search_node_handler,
    "supabase": supabase_query_node_handler,
}


class NodeRegistry:
    def __init__(self, handlers: Mapping[str, ModuleType] | None = None):
        self._handlers = dict(handlers or DEFAULT_NODE_HANDLERS)

    def get(self, node_type: str) -> ModuleType:
        try:
            return self._handlers[node_type]
        except KeyError as exc:
            supported = ", ".join(sorted(self._handlers))
            raise ValueError(
                f"Node type '{node_type}' is not supported. Supported types: {supported}"
            ) from exc
