from actions.assert_url import assert_url_action
from actions.assert_count import assert_count_action
from actions.assert_metric import assert_metric_action
from actions.click import click_action
from actions.fill import fill_action
from actions.goto import goto_action
from actions.wait_for import wait_for_action
from actions.assert_visible import assert_visible_action
from actions.login import login_action


ACTION_DEFINITIONS = {
    "click": {"handler": click_action, "requires_target": True},
    "fill": {"handler": fill_action, "requires_target": True},
    "input": {"handler": fill_action, "requires_target": True},
    "type": {"handler": fill_action, "requires_target": True},
    "wait_for": {"handler": wait_for_action, "requires_target": True},
    "assert_visible": {"handler": assert_visible_action, "requires_target": True},
    "assert_count": {"handler": assert_count_action, "requires_target": True},
    "assert_metric": {"handler": assert_metric_action, "requires_target": True},
    "login": {"handler": login_action, "requires_target": False},
    "assert_url": {"handler": assert_url_action, "requires_target": False},
    "goto": {"handler": goto_action, "requires_target": False},
}


ACTION_REGISTRY = {
    action_name: definition["handler"]
    for action_name, definition in ACTION_DEFINITIONS.items()
}
