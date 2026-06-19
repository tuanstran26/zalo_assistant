from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Mapping

import yaml

from engines.context import Context
from engines.registry import NodeRegistry


logger = logging.getLogger(__name__)


class WorkflowExecutor:
    def __init__(
        self,
        workflow_path: str | Path,
        registry: NodeRegistry | None = None,
        context: Context | None = None,
    ):
        with open(workflow_path, "r", encoding="utf-8") as f:
            self.workflow = yaml.safe_load(f)
        self.steps = {step["id"]: step for step in self.workflow["steps"]}
        self.context = context or Context()
        self.registry = registry or NodeRegistry()

    def run(
        self,
        start_step_id: str,
        initial_input: Mapping[str, Any] | None = None,
    ) -> Context:
        initial_input = initial_input or {}
        self.context.update(initial_input)
        self._append_user_message(initial_input.get("user_question"))

        step_id = start_step_id
        while step_id and step_id != "end":
            step = self.steps.get(step_id)
            if not step:
                raise ValueError(f"Step '{step_id}' not found.")

            node_type = step["type"]
            node_handler = self.registry.get(node_type)
            output, next_step = node_handler.run(step, self.context)

            logger.debug("Step %s (%s) output: %s", step.get("id"), node_type, output)
            self.context.update(output)
            step_id = next_step

        return self.context

    def _append_user_message(self, user_question: Any) -> None:
        if not user_question:
            return

        history = self.context.get("conversation_history", [])
        if not isinstance(history, list):
            history = []
        history.append({"role": "user", "content": str(user_question)})
        self.context.set("conversation_history", history)
