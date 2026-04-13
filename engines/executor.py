import yaml
from engines.context import Context
from engines.registry import NodeRegistry

class WorkflowExecutor:
    def __init__(self, workflow_path):
        with open(workflow_path, 'r', encoding='utf-8') as f:
            self.workflow = yaml.safe_load(f)
        self.steps = {step['id']: step for step in self.workflow['steps']}
        self.context = Context()
        self.registry = NodeRegistry()

    def run(self, start_step_id, initial_input={}):
        self.context.update(initial_input)

        user_question = initial_input.get("user_question")
        if user_question:
            history = self.context.get("conversation_history", [])
            if not isinstance(history, list):
                history = []
            history.append({"role": "user", "content": user_question})
            self.context.set("conversation_history", history)

        step_id = start_step_id

        while step_id and step_id != "end":
            step = self.steps.get(step_id)
            if not step:
                raise ValueError(f"Step '{step_id}' not found.")

            node_type = step['type']
            node_handler = self.registry.get(node_type)
            output, next_step = node_handler.run(step, self.context)
            print(f"in executor {step["type"]}",output)
            if output:
                self.context.update(output)

            print("📦 Context hiện tại:", self.context.to_dict())
            step_id = next_step
