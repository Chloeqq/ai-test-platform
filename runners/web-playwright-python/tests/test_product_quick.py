"""快速测试商品列表页面"""
import pytest
from playwright.sync_api import Page


pytestmark = [pytest.mark.e2e, pytest.mark.smoke]


def test_product_list(page: Page, base_url: str, test_username: str, test_password: str):
    """测试商品列表页面加载"""
    # 访问登录页
    page.goto(base_url)
    
    # 登录
    page.fill('input[placeholder="请输入用户名"]', test_username)
    page.fill('input[placeholder="请输入密码"]', test_password)
    page.click('button:has-text("登录")')
    page.wait_for_timeout(2000)
    
    # 先点击"商品"父菜单展开子菜单 - 使用 text 定位器
    page.click('text=商品')
    page.wait_for_timeout(1000)
    
    # 再点击"商品列表"
    page.click('text=商品列表')
    page.wait_for_timeout(3000)
    
    # 验证 URL
    assert "/pms/product" in page.url
    
    # 验证表格存在
    table = page.query_selector('.el-table__body')
    assert table is not None, "商品表格未找到"
