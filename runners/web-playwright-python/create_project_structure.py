#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在当前目录（web-playwright-python）一键创建子目录和文件结构"""

import os
import pathlib

# 定义要在当前目录创建的子目录和文件
PROJECT_STRUCTURE = {
    ".": {  # "." 代表当前目录
        # 子目录
        "dirs": [
            "pages",
            "tests"
        ],
        # 当前目录下的文件
        "files": [
            "conftest.py",
            "requirements.txt",
            "pytest.ini"
        ]
    },
    "./pages": {
        "files": [
            "login_page.py",
            "product_page.py",
            "order_page.py"
        ]
    },
    "./tests": {
        "files": [
            "test_login_smoke.py",
            "test_product_smoke.py",
            "test_order_smoke.py"
        ]
    }
}

# 基础文件的模板内容（保证文件可直接使用）
FILE_TEMPLATES = {
    "conftest.py": '''"""pytest 配置文件"""
import pytest
from playwright.sync_api import Playwright


@pytest.fixture(scope="session")
def playwright(playwright: Playwright):
    """全局 Playwright 夹具"""
    yield playwright


@pytest.fixture(scope="function")
def browser(playwright):
    """启动 Chromium 浏览器"""
    browser = playwright.chromium.launch(headless=False)
    yield browser
    browser.close()


@pytest.fixture(scope="function")
def page(browser):
    """创建新页面"""
    context = browser.new_context()
    page = context.new_page()
    yield page
    context.close()
''',

    "requirements.txt": '''playwright>=1.40.0
pytest>=7.4.0
pytest-playwright>=0.3.0
''',

    "pytest.ini": '''[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
''',

    "pages/login_page.py": '''"""登录页面封装"""
from playwright.sync_api import Page


class LoginPage:
    def __init__(self, page: Page):
        self.page = page
        # 定位器
        self.username_input = page.locator("#username")
        self.password_input = page.locator("#password")
        self.login_button = page.locator("button:has-text('登录')")

    def navigate(self):
        """导航到登录页"""
        self.page.goto("/login")

    def login(self, username: str, password: str):
        """执行登录操作"""
        self.username_input.fill(username)
        self.password_input.fill(password)
        self.login_button.click()
        # 等待登录完成
        self.page.wait_for_url("**/dashboard")
''',

    "pages/product_page.py": '''"""商品页面封装"""
from playwright.sync_api import Page


class ProductPage:
    def __init__(self, page: Page):
        self.page = page
        # 可添加商品页面的定位器和方法
''',

    "pages/order_page.py": '''"""订单页面封装"""
from playwright.sync_api import Page


class OrderPage:
    def __init__(self, page: Page):
        self.page = page
        # 可添加订单页面的定位器和方法
''',

    "tests/test_login_smoke.py": '''"""登录冒烟测试"""
import pytest
from pages.login_page import LoginPage


def test_successful_login(page):
    """测试成功登录"""
    login_page = LoginPage(page)
    login_page.navigate()
    login_page.login("test_user", "test_pass")
    # 验证登录成功（根据实际业务调整）
    assert "dashboard" in page.url


def test_failed_login_with_wrong_password(page):
    """测试失败登录"""
    login_page = LoginPage(page)
    login_page.navigate()
    login_page.login("test_user", "wrong_pass")
    # 验证错误提示（根据实际业务调整）
    assert page.locator(".error-message").is_visible()
''',

    "tests/test_product_smoke.py": '''"""商品页面冒烟测试"""
from pages.product_page import ProductPage


def test_product_list_loading(page):
    """测试商品列表加载"""
    product_page = ProductPage(page)
    page.goto("/products")
    # 验证商品列表加载（根据实际业务调整）
    assert page.locator(".product-item").count() > 0
''',

    "tests/test_order_smoke.py": '''"""订单页面冒烟测试"""
from pages.order_page import OrderPage


def test_order_list_access(page):
    """测试订单列表访问"""
    order_page = OrderPage(page)
    page.goto("/orders")
    # 验证订单页面加载（根据实际业务调整）
    assert page.title() == "我的订单"
'''
}


def create_directory(path):
    """创建目录（递归创建，已存在则忽略）"""
    # 转换为绝对路径，便于查看
    abs_path = os.path.abspath(path)
    try:
        os.makedirs(abs_path, exist_ok=True)
        print(f"✅ 目录创建成功: {abs_path}")
    except Exception as e:
        print(f"❌ 目录创建失败: {abs_path}, 错误: {e}")


def create_file(file_path, content=""):
    """创建文件（已存在则跳过，避免覆盖）"""
    # 转换为绝对路径
    abs_file_path = os.path.abspath(file_path)
    file_path_obj = pathlib.Path(abs_file_path)

    if file_path_obj.exists():
        print(f"⚠️ 文件已存在，跳过创建: {abs_file_path}")
        return

    try:
        # 确保父目录存在
        file_path_obj.parent.mkdir(parents=True, exist_ok=True)
        # 写入文件内容
        with open(abs_file_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"✅ 文件创建成功: {abs_file_path}")
    except Exception as e:
        print(f"❌ 文件创建失败: {abs_file_path}, 错误: {e}")


def main():
    """主函数：在当前目录创建子目录和文件"""
    current_dir = os.path.abspath("..")
    print(f"开始在当前目录创建文件结构: {current_dir}\\n")

    # 第一步：创建所有目录
    for dir_path, config in PROJECT_STRUCTURE.items():
        create_directory(dir_path)
        # 创建子目录（当前目录的子目录已在 dirs 中定义，这里兜底）
        for sub_dir in config.get("dirs", []):
            full_sub_dir = os.path.join(dir_path, sub_dir)
            create_directory(full_sub_dir)

    # 第二步：创建所有文件
    for dir_path, config in PROJECT_STRUCTURE.items():
        for file_name in config.get("files", []):
            file_path = os.path.join(dir_path, file_name)
            # 提取相对路径作为模板key（如 pages/login_page.py）
            rel_path = os.path.normpath(file_path).lstrip("./")  # 去掉开头的 ./
            content = FILE_TEMPLATES.get(rel_path, "")
            create_file(file_path, content)

    print("\\n🎉 目录结构创建完成！")
    print("📌 后续操作：")
    print("   1. 安装依赖: pip install -r requirements.txt")
    print("   2. 安装 Playwright 浏览器: playwright install")
    print("   3. 运行测试: pytest")


if __name__ == "__main__":
    main()