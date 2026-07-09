"""AI 测试质量评估中心 — Seed 数据。

预置 3 个评测数据集，基于登录模块的真实测试场景。
可直接通过 create_dataset API 导入，或用于 Demo 演示。
"""

from __future__ import annotations

SEED_DATASETS: list[dict] = [
    {
        "project_code": "atp",
        "name": "登录模块 AI 生成质量评测 v2",
        "description": "评估 AI 对『手机验证码登录』『账号密码登录』『忘记密码』三条需求的测试用例生成质量",
        "task_type": "test_case_generation",
        "eval_dimensions": [
            "coverage",
            "assertion_quality",
            "executability",
            "consistency",
            "hallucination",
        ],
        "items": [
            {
                "requirement_text": "用户可以使用手机号和验证码登录系统",
                "expected_coverage": [
                    "正确验证码登录成功",
                    "错误验证码提示",
                    "验证码过期重新获取",
                    "手机号格式校验",
                    "60秒发送间隔限制",
                ],
                "expected_assertions": [
                    {"type": "url", "target": "/dashboard"},
                    {"type": "visible", "target": "用户昵称"},
                    {"type": "text", "target": "验证码错误"},
                ],
                "expected_page_codes": ["login", "dashboard"],
                "known_issues": ["弱断言", "缺少验证码过期场景", "未覆盖发送频率限制"],
            },
            {
                "requirement_text": "用户可以使用账号密码登录系统",
                "expected_coverage": [
                    "正确账号密码登录",
                    "密码错误提示",
                    "账号不存在提示",
                    "连续5次失败锁定",
                    "记住密码功能",
                ],
                "expected_assertions": [
                    {"type": "url", "target": "/dashboard"},
                    {"type": "visible", "target": "欢迎文本"},
                    {"type": "text", "target": "账号或密码错误"},
                ],
                "expected_page_codes": ["login", "dashboard"],
                "known_issues": ["弱断言", "未覆盖账号锁定场景"],
            },
            {
                "requirement_text": "用户可以通过忘记密码功能重置密码",
                "expected_coverage": [
                    "发送重置邮件",
                    "邮件链接有效",
                    "新密码设置成功",
                    "旧密码已失效",
                ],
                "expected_assertions": [
                    {"type": "visible", "target": "重置成功提示"},
                    {"type": "text", "target": "邮件已发送"},
                ],
                "expected_page_codes": ["login", "forgot_password", "reset_password"],
                "known_issues": ["缺少旧密码失效验证", "未验证邮件链接时效性"],
            },
        ],
    },
    {
        "project_code": "atp",
        "name": "需求描述鲁棒性评测 v1",
        "description": "测试 AI 在需求文本出现错别字、语序错乱等扰动时，生成质量是否保持稳定",
        "task_type": "test_case_generation",
        "eval_dimensions": ["robustness", "consistency"],
        "items": [
            {
                "requirement_text": "登录页面需要支持手机验证码登录",
                "perturbed_requirement": "登入页棉需要支池手几验证码登入",
                "expected_coverage": ["正确验证码登录成功"],
                "expected_page_codes": ["login"],
                "known_issues": [],
            },
            {
                "requirement_text": "商品搜索支持关键词模糊匹配",
                "perturbed_requirement": "商口搜锁支持关键自摩胡匹配",
                "expected_coverage": ["模糊搜索返回结果", "无匹配结果提示"],
                "expected_page_codes": ["search", "product_list"],
                "known_issues": [],
            },
        ],
    },
    {
        "project_code": "atp",
        "name": "全模块 AI 质量回归评测 v1",
        "description": "覆盖登录、商品浏览、购物车、订单支付的多模块综合评测，用于版本升级前后对比",
        "task_type": "test_case_generation",
        "eval_dimensions": ["coverage", "assertion_quality", "executability", "hallucination"],
        "items": [
            {
                "requirement_text": "用户登录系统后跳转到首页",
                "expected_coverage": ["登录成功跳转", "未登录拦截", "token过期处理"],
                "expected_assertions": [
                    {"type": "url", "target": "/home"},
                    {"type": "visible", "target": "用户信息"},
                ],
                "expected_page_codes": ["login", "home"],
                "known_issues": ["rule_003命中:弱断言"],
            },
            {
                "requirement_text": "用户在商品列表页可以按分类筛选商品",
                "expected_coverage": ["分类筛选展示", "无结果提示", "跨分类切换"],
                "expected_assertions": [
                    {"type": "visible", "target": "商品列表"},
                    {"type": "text", "target": "筛选结果"},
                ],
                "expected_page_codes": ["product_list", "category"],
                "known_issues": [],
            },
            {
                "requirement_text": "用户可以将商品加入购物车并修改数量",
                "expected_coverage": ["加入购物车", "修改数量", "删除商品", "库存不足提示"],
                "expected_assertions": [
                    {"type": "visible", "target": "购物车图标"},
                    {"type": "text", "target": "已加入购物车"},
                ],
                "expected_page_codes": ["product_detail", "cart"],
                "known_issues": ["rule_006命中:未知元素"],
            },
            {
                "requirement_text": "用户提交订单并选择微信支付完成付款",
                "expected_coverage": ["提交订单", "微信支付调起", "支付成功", "支付失败回滚"],
                "expected_assertions": [
                    {"type": "url", "target": "/order/success"},
                    {"type": "visible", "target": "支付成功"},
                ],
                "expected_page_codes": ["checkout", "payment", "order_success"],
                "known_issues": ["rule_008命中:缺少断言"],
            },
        ],
    },
]