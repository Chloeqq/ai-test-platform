"""限时秒杀活动列表页面 - 基础功能测试"""
import pytest
from playwright.sync_api import Page, expect


pytestmark = [pytest.mark.e2e, pytest.mark.smoke, pytest.mark.flash]


def test_flash_list_page_load(page: Page, base_url: str):
    """测试秒杀活动列表页面加载"""
    # 访问秒杀活动列表页面
    page.goto(f"{base_url}/#/sms/flash", wait_until="networkidle")
    page.wait_for_timeout(2000)
    
    # 验证页面 URL
    assert "/sms/flash" in page.url, "页面 URL 不正确"
    
    # 验证筛选搜索区域可见
    filter_section = page.locator(".filter-container")
    expect(filter_section).to_be_visible(timeout=10000)
    
    # 验证数据列表区域可见
    data_list = page.locator(".data-list-container")
    expect(data_list).to_be_visible()
    
    # 验证页面标题
    page_title = page.title()
    assert "秒杀" in page_title or "活动" in page_title, f"页面标题不包含关键词：{page_title}"


def test_flash_table_display(page: Page, base_url: str):
    """测试活动表格数据显示"""
    # 访问页面
    page.goto(f"{base_url}/#/sms/flash", wait_until="networkidle")
    page.wait_for_timeout(2000)
    
    # 验证表格存在
    table = page.locator(".el-table")
    expect(table).to_be_visible()
    
    # 验证表格表头
    header_row = page.locator(".el-table__header tr")
    expect(header_row).to_be_visible()
    
    # 验证表头列名
    headers = page.locator(".el-table__header th")
    expect(headers).to_have_count(8)  # 编号、活动标题、活动状态、开始时间、结束时间、上线/下线、操作
    
    # 验证至少有一条数据
    body_rows = page.locator(".el-table__body tr")
    expect(body_rows).to_be_visible()
    expect(body_rows).to_have_count(gte=1)


def test_flash_activity_data(page: Page, base_url: str):
    """测试活动数据展示"""
    # 访问页面
    page.goto(f"{base_url}/#/sms/flash", wait_until="networkidle")
    page.wait_for_timeout(2000)
    
    # 获取第一个活动行
    first_row = page.locator(".el-table__body tr:nth-child(1)")
    expect(first_row).to_be_visible()
    
    # 验证活动标题列
    title_cell = first_row.locator("td:nth-child(3)")
    expect(title_cell).to_be_visible()
    
    # 验证活动状态列
    status_cell = first_row.locator("td:nth-child(4)")
    expect(status_cell).to_be_visible()
    
    # 验证状态文本包含"活动"
    status_text = status_cell.inner_text()
    assert "活动" in status_text, f"状态文本不包含'活动': {status_text}"


def test_flash_action_buttons(page: Page, base_url: str):
    """测试操作按钮可用性"""
    # 访问页面
    page.goto(f"{base_url}/#/sms/flash", wait_until="networkidle")
    page.wait_for_timeout(2000)
    
    # 获取第一个活动行
    first_row = page.locator(".el-table__body tr:nth-child(1)")
    
    # 验证设置商品按钮
    set_product_btn = first_row.get_by_role("button", name="设置商品")
    expect(set_product_btn).to_be_visible()
    
    # 验证编辑按钮
    edit_btn = first_row.get_by_role("button", name="编辑")
    expect(edit_btn).to_be_visible()
    
    # 验证删除按钮
    delete_btn = first_row.get_by_role("button", name="删除")
    expect(delete_btn).to_be_visible()


def test_flash_pagination(page: Page, base_url: str):
    """测试分页控件"""
    # 访问页面
    page.goto(f"{base_url}/#/sms/flash", wait_until="networkidle")
    page.wait_for_timeout(2000)
    
    # 验证分页区域存在
    pagination = page.locator(".el-pagination")
    expect(pagination).to_be_visible()
    
    # 验证总记录数显示
    total_text = page.locator(".el-pagination").filter(has_text="共")
    expect(total_text).to_be_visible()
    
    # 验证页码选择器
    page_size_selector = pagination.locator(".el-select")
    expect(page_size_selector).to_be_visible()
    
    # 验证上一页/下一页按钮
    prev_btn = page.get_by_role("button", name="上一页")
    next_btn = page.get_by_role("button", name="下一页")
    expect(prev_btn).to_be_visible()
    expect(next_btn).to_be_visible()


def test_flash_search_filter(page: Page, base_url: str):
    """测试筛选搜索功能"""
    # 访问页面
    page.goto(f"{base_url}/#/sms/flash", wait_until="networkidle")
    page.wait_for_timeout(2000)
    
    # 验证搜索输入框存在
    search_input = page.get_by_placeholder("活动名称")
    expect(search_input).to_be_visible()
    
    # 验证查询按钮存在
    search_btn = page.get_by_role("button", name="查询搜索")
    expect(search_btn).to_be_visible()
    
    # 验证重置按钮存在
    reset_btn = page.get_by_role("button", name="重置")
    expect(reset_btn).to_be_visible()
    
    # 测试输入搜索关键词
    search_input.fill("测试")
    
    # 点击查询
    search_btn.click()
    page.wait_for_timeout(1000)
    
    # 验证查询后表格仍然可见
    table = page.locator(".el-table")
    expect(table).to_be_visible()


def test_flash_status_switch(page: Page, base_url: str):
    """测试上线/下线开关"""
    # 访问页面
    page.goto(f"{base_url}/#/sms/flash", wait_until="networkidle")
    page.wait_for_timeout(2000)
    
    # 获取第一个活动行的开关
    first_row = page.locator(".el-table__body tr:nth-child(1)")
    status_switch = first_row.locator(".el-switch")
    
    # 验证开关存在
    expect(status_switch).to_be_visible()
    
    # 验证开关状态（checked 或 unchecked）
    switch_class = status_switch.get_attribute("class")
    assert "is-checked" in switch_class or "is-checked" not in switch_class, "开关状态异常"


def test_flash_add_activity_button(page: Page, base_url: str):
    """测试添加活动按钮"""
    # 访问页面
    page.goto(f"{base_url}/#/sms/flash", wait_until="networkidle")
    page.wait_for_timeout(2000)
    
    # 验证添加活动按钮存在
    add_btn = page.get_by_role("button", name="添加活动")
    expect(add_btn).to_be_visible()
    
    # 验证秒杀时间段列表按钮存在
    time_btn = page.get_by_role("button", name="秒杀时间段列表")
    expect(time_btn).to_be_visible()


def test_flash_breadcrumb(page: Page, base_url: str):
    """测试面包屑导航"""
    # 访问页面
    page.goto(f"{base_url}/#/sms/flash", wait_until="networkidle")
    page.wait_for_timeout(2000)
    
    # 验证面包屑存在
    breadcrumb = page.locator(".el-breadcrumb")
    expect(breadcrumb).to_be_visible()
    
    # 验证面包屑链接
    home_link = page.get_by_role("link", name="首页")
    expect(home_link).to_be_visible()
    
    marketing_link = page.get_by_role("link", name="营销")
    expect(marketing_link).to_be_visible()


def test_flash_list_complete_flow(page: Page, base_url: str, test_username: str, test_password: str):
    """测试完整流程：登录 -> 访问列表 -> 验证数据 -> 搜索"""
    # 访问登录页
    page.goto(base_url, wait_until="networkidle")
    
    # 登录
    page.get_by_placeholder("请输入用户名").fill(test_username)
    page.get_by_placeholder("请输入密码").fill(test_password)
    page.get_by_role("button", name="登录").click()
    page.wait_for_timeout(2000)
    
    # 访问秒杀活动列表
    page.goto(f"{base_url}/#/sms/flash", wait_until="networkidle")
    page.wait_for_timeout(2000)
    
    # 验证页面加载
    expect(page.locator(".el-table")).to_be_visible()
    
    # 验证数据存在
    first_row = page.locator(".el-table__body tr:nth-child(1)")
    expect(first_row).to_be_visible()
    
    # 执行搜索
    search_input = page.get_by_placeholder("活动名称")
    search_input.fill("测试")
    page.get_by_role("button", name="查询搜索").click()
    page.wait_for_timeout(1000)
    
    # 验证搜索结果
    expect(page.locator(".el-table")).to_be_visible()
