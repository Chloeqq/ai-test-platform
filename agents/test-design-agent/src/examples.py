EXAMPLE_REQUIREMENT = """
验证商品列表页面可以正常打开：
1. 登录系统
2. 点击商品菜单
3. 页面显示商品列表
"""

EXAMPLE_OUTPUT = {
    "version": "v4",
    "id": "tc-product-001",
    "title": "商品列表页面加载",
    "module": "product",
    "priority": "P0",
    "tags": ["smoke", "product"],
    "owner": "qa-team",
    "status": "automated",
    "description": "登录后进入商品列表页面",
    "requirement": ["商品列表展示"],
    "data": {},
    "execution": {
        "runner": "playwright",
        "page": "product",
        "variables": {},
        "steps": [
            {"action": "login"},
            {"action": "click", "target": "product_menu"},
            {"action": "wait_for", "target": "product_list_title"},
            {"action": "assert_visible", "target": "product_list_title"},
        ],
    },
}