import os
from pathlib import Path

import pytest
import yaml
from playwright.sync_api import expect

CASE = {
  "version": "v4",
  "id": "tc-product-GEN-001",
  "title": "商品页-列表展示-基础生成-执行验证-关键元素可见",
  "module": "product",
  "priority": "P1",
  "tags": [
    "product"
  ],
  "owner": "qa-team",
  "status": "automated",
  "description": "根据需求自动生成的商品列表测试用例。",
  "requirement": [
    "验证商品列表展示",
    "[P2] 验证商品列表展示",
    "原始需求: 验证商品列表展示\n整体优先级: P2\n结构化测试点:\n- [intent-01](functional/P2) 验证商品列表展示; steps=open:product,assert; deps=-; sources=source-01\n请基于以上测试点生成稳定可执行 YAML。"
  ],
  "data": {},
  "execution": {
    "runner": "playwright",
    "page": "product",
    "variables": {},
    "steps": [
      {
        "action": "login"
      },
      {
        "action": "assert_visible",
        "target": "product_list_title"
      }
    ]
  }
}

def _load_page_object(page_name: str) -> dict:
    repo_root = Path(__file__).resolve().parents[2]
    page_object_path = repo_root / 'assets' / 'page-objects' / 'web' / f'{page_name}.page-object.yaml'
    return yaml.safe_load(page_object_path.read_text(encoding='utf-8')) or {}

def _resolve_locator(page, element: dict):
    locator_type = str(element.get('locator_type', '')).strip()
    locator_value = element.get('locator_value')
    role = element.get('role')
    if locator_type == 'placeholder':
        return page.get_by_placeholder(locator_value)
    if locator_type == 'text':
        return page.get_by_text(locator_value)
    if locator_type == 'css':
        return page.locator(locator_value)
    if locator_type == 'role':
        return page.get_by_role(role, name=locator_value)
    raise ValueError(f'Unsupported locator_type: {locator_type}')

def _login(page):
    login_url = os.getenv('BASE_URL', 'http://localhost:5173/login#/login')
    username = os.getenv('TEST_USERNAME', 'admin')
    password = os.getenv('TEST_PASSWORD', 'macro123')
    page.goto(login_url, wait_until='domcontentloaded', timeout=60000)
    page.get_by_placeholder('请输入用户名').fill(username)
    page.get_by_placeholder('请输入密码').fill(password)
    page.get_by_role('button', name='登录').click()

@pytest.mark.generated
def test_atp_web_prod_gen_fn_ai_0001(page):
    execution = CASE.get('execution', {})
    page_name = execution.get('page')
    page_object = _load_page_object(page_name)
    elements = page_object.get('elements', {})
    for step in execution.get('steps', []):
        action = step.get('action')
        target = step.get('target')
        value = step.get('value')
        if action == 'login':
            _login(page)
            continue
        if action == 'goto':
            page.goto(str(value), wait_until='domcontentloaded', timeout=60000)
            continue
        if action == 'assert_url':
            expect(page).to_have_url(str(value))
            continue
        if target not in elements:
            raise ValueError(f'Missing target in page object: {target}')
        locator = _resolve_locator(page, elements[target])
        if action == 'click':
            locator.click()
        elif action == 'fill':
            locator.fill(str(value))
        elif action == 'wait_for':
            expect(locator).to_be_visible(timeout=10000)
        elif action == 'assert_visible':
            expect(locator).to_be_visible(timeout=10000)
        else:
            raise ValueError(f'Unsupported action: {action}')
