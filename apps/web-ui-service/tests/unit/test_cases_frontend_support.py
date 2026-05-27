from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


WEB_UI_ROOT = Path(__file__).resolve().parents[2]
if str(WEB_UI_ROOT) not in sys.path:
    sys.path.insert(0, str(WEB_UI_ROOT))

CASES_SUPPORT_PATH = WEB_UI_ROOT / "app" / "static" / "cases_support.js"
CASES_PRESENTER_PATH = WEB_UI_ROOT / "app" / "static" / "cases_presenter.js"


def _run_node_json(script: str) -> dict[str, object]:
    completed = subprocess.run(
        ["node", "-e", script],
        cwd=WEB_UI_ROOT.parents[1],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(completed.stdout)


def test_build_search_input_from_context_reconstructs_single_search_expression() -> None:
    script = f"""
const fs = require("fs");
const vm = require("vm");
global.window = {{}};
global.Event = class Event {{
  constructor(type, options = {{}}) {{
    this.type = type;
    this.bubbles = Boolean(options.bubbles);
  }}
}};
vm.runInThisContext(fs.readFileSync({json.dumps(str(CASES_SUPPORT_PATH))}, "utf8"), {{ filename: "cases_support.js" }});
const result = window.CasesSupport.buildSearchInputFromContext({{
  keyword: "订单回归",
  test_type: "api",
  status: "active",
  creator: "qa team",
  last_result: "failed",
}});
console.log(JSON.stringify({{ result }}));
"""
    payload = _run_node_json(script)

    assert payload["result"] == '订单回归 类型:api 状态:启用 创建人:"qa team" 结果:失败'


def test_clear_search_context_key_updates_search_input_and_dispatches_event() -> None:
    script = f"""
const fs = require("fs");
const vm = require("vm");
global.window = {{}};
global.Event = class Event {{
  constructor(type, options = {{}}) {{
    this.type = type;
    this.bubbles = Boolean(options.bubbles);
  }}
}};
vm.runInThisContext(fs.readFileSync({json.dumps(str(CASES_SUPPORT_PATH))}, "utf8"), {{ filename: "cases_support.js" }});
const events = [];
const els = {{
  searchInput: {{
    value: "",
    dispatchEvent(event) {{
      events.push({{ type: event.type, bubbles: event.bubbles }});
    }},
  }},
  filterProductLine: {{ value: "会员体系" }},
  filterModule: {{ value: "认证服务" }},
  sortDir: {{ value: "desc" }},
  sortKey: {{ value: "updated_at" }},
}};
const state = {{
  searchContext: {{
    keyword: "订单回归",
    test_type: "api",
    status: "active",
    creator: "qa team",
    last_result: "failed",
    product_line: "会员体系",
    module: "认证服务",
  }},
}};
window.CasesSupport.clearSearchContextKey(els, state, "creator");
console.log(JSON.stringify({{
  searchInput: els.searchInput.value,
  events,
  productLine: els.filterProductLine.value,
  module: els.filterModule.value,
}}));
"""
    payload = _run_node_json(script)

    assert payload["searchInput"] == "订单回归 类型:api 状态:启用 结果:失败"
    assert payload["events"] == [{"type": "input", "bubbles": True}]
    assert payload["productLine"] == "会员体系"
    assert payload["module"] == "认证服务"


def test_clear_search_context_key_clears_tree_selection_together() -> None:
    script = f"""
const fs = require("fs");
const vm = require("vm");
global.window = {{}};
global.Event = class Event {{
  constructor(type, options = {{}}) {{
    this.type = type;
    this.bubbles = Boolean(options.bubbles);
  }}
}};
vm.runInThisContext(fs.readFileSync({json.dumps(str(CASES_SUPPORT_PATH))}, "utf8"), {{ filename: "cases_support.js" }});
const els = {{
  searchInput: {{
    value: "订单回归",
    dispatchEvent() {{}},
  }},
  filterProductLine: {{ value: "会员体系" }},
  filterModule: {{ value: "认证服务" }},
  sortDir: {{ value: "desc" }},
  sortKey: {{ value: "updated_at" }},
}};
const state = {{ searchContext: {{ product_line: "会员体系", module: "认证服务" }} }};
window.CasesSupport.clearSearchContextKey(els, state, "product_line");
console.log(JSON.stringify({{
  productLine: els.filterProductLine.value,
  module: els.filterModule.value,
  searchInput: els.searchInput.value,
}}));
"""
    payload = _run_node_json(script)

    assert payload["productLine"] == ""
    assert payload["module"] == ""
    assert payload["searchInput"] == "订单回归"


def test_search_context_markup_contains_remove_and_clear_actions() -> None:
    script = f"""
const fs = require("fs");
const vm = require("vm");
global.window = {{}};
vm.runInThisContext(fs.readFileSync({json.dumps(str(CASES_PRESENTER_PATH))}, "utf8"), {{ filename: "cases_presenter.js" }});
const markup = window.CasesPresenter.searchContextMarkup({{
  keyword: "订单回归",
  test_type: "api",
  status: "active",
}});
console.log(JSON.stringify({{ markup }}));
"""
    payload = _run_node_json(script)
    markup = str(payload["markup"])

    assert 'data-clear-all-context="true"' in markup
    assert 'data-remove-key="keyword"' in markup
    assert 'data-remove-key="test_type"' in markup
    assert 'data-remove-key="status"' in markup
