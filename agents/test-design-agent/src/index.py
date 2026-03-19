from .agent import TestDesignAgent


def main():
    requirement = """
    验证商品列表页面可以正常打开：
    1. 登录系统
    2. 点击商品菜单
    3. 页面显示商品列表
    """

    agent = TestDesignAgent()
    result = agent.generate(requirement, page="product")
    print(result)


if __name__ == "__main__":
    main()
