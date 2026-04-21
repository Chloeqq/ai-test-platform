# mypy: ignore-errors

from playwright.sync_api import Page

from runner.action_registry import ACTION_DEFINITIONS
from runner.locator_resolver import resolve_locator
from runner.variable_resolver import resolve_variables


class YamlExecutor:
    def __init__(self, page: Page, username: str, password: str, base_url: str):
        self.page = page
        self.username = username
        self.password = password
        self.base_url = base_url

    def execute(self, test_case: dict) -> None:
        execution = test_case.get("execution")
        if not execution:
            raise ValueError(
                f"Missing execution section in test case: {test_case.get('id')}"
            )

        page_name = execution.get("page")
        steps = execution.get("steps", [])
        variables = execution.get("variables", {})
        data_context = test_case.get("_data", {})

        resolved_context = self._build_context(variables, data_context)

        for index, step in enumerate(steps, start=1):
            self._execute_step(
                step,
                step_index=index,
                default_page_name=page_name,
                context=resolved_context,
            )

    def _build_context(self, variables: dict, data_context: dict) -> dict:
        """
        把 execution.variables 和 data_expander 传入的 _data 合并成最终上下文
        例如：
        variables:
          search_keyword: "{{keyword}}"

        _data:
          keyword: 手机

        最终得到：
          {
            "keyword": "手机",
            "search_keyword": "手机"
          }
        """
        context = dict(data_context)

        for key, value in variables.items():
            if isinstance(value, str):
                context[key] = resolve_variables(value, context)
            else:
                context[key] = value

        return context

    def _resolve_step_page_name(self, default_page_name: str, step: dict, step_index: int) -> str:
        page_name = str(step.get("page") or default_page_name or "").strip()
        if not page_name:
            raise ValueError(f"Step {step_index} cannot resolve page name")
        return page_name

    def _execute_step(
        self,
        step: dict,
        *,
        step_index: int,
        default_page_name: str,
        context: dict,
    ) -> None:
        action = step.get("action")
        action_definition = ACTION_DEFINITIONS.get(action)
        page_name = self._resolve_step_page_name(default_page_name, step, step_index)

        if not action_definition:
            raise ValueError(f"Unsupported action at step {step_index}: {action}")

        target = step.get("target")
        locator = None

        if action_definition["requires_target"]:
            if not target:
                raise ValueError(
                    f"Step {step_index} requires target for action '{action}' on page '{page_name}'"
                )
            selector = str(step.get("selector") or "").strip()
            locator_type = str(step.get("locator_type") or "").strip()
            role = str(step.get("role") or "").strip()
            if not selector or not locator_type:
                raise ValueError(
                    f"Step {step_index} requires compiled selector binding for action '{action}' on page '{page_name}'"
                )
            locator = resolve_locator(
                self.page,
                {
                    "locator_type": locator_type,
                    "locator_value": selector,
                    "role": role,
                },
            )
        elif target:
            selector = str(step.get("selector") or "").strip()
            locator_type = str(step.get("locator_type") or "").strip()
            role = str(step.get("role") or "").strip()
            if selector and locator_type:
                locator = resolve_locator(
                    self.page,
                    {
                        "locator_type": locator_type,
                        "locator_value": selector,
                        "role": role,
                    },
                )
            else:
                raise ValueError(
                    f"Step {step_index} references target '{target}' without compiled selector binding"
                )

        action_definition["handler"](
            page=self.page,
            locator=locator,
            step=step,
            context=context,
            username=self.username,
            password=self.password,
            base_url=self.base_url,
        )
