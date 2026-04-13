import nodes.llm_node_handler as llm_node_handler
import nodes.switch_node_handler as switch_node_handler
import nodes.vector_search_node_handler as vector_search_node_handler
import nodes.function_node_handler as function_node_handler
import nodes.excel_vector_search_node_handler as excel_vector_search_node_handler
import nodes.supabase_query_node_handler as supabase_query_node_handler


class NodeRegistry [self]:
    def __init__(self):
        self.NODE_REGISTRY = {
            "llm": llm_node_handler,
            "switch": switch_node_handler,
            "vector_search": vector_search_node_handler,
            "function": function_node_handler,
            "excel_search": excel_vector_search_node_handler,
            "supabase": supabase_query_node_handler,
        }

    def get(self, node_type):
        if node_type not in self.NODE_REGISTRY:
            raise Exception(f"Node type '{node_type}' not supported.")
        return self.NODE_REGISTRY[node_type]
