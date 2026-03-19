from pathlib import Path

from src.agent import TestDesignAgent
from src.tools.yaml_writer import save_yaml


OUTPUT_DIR = Path(
    "../../assets/test-cases/ai-generated"
).resolve()


def main():

    requirement = """
    验证商品搜索功能：

    1 登录系统
    2 进入商品页面
    3 输入关键字搜索
    4 显示商品列表
    """

    agent = TestDesignAgent()

    case = agent.generate(requirement, page="product")

    file_name = f"{case['id']}.yaml"

    path = save_yaml(case, OUTPUT_DIR / file_name)

    print("YAML生成成功:")
    print(path)


if __name__ == "__main__":
    main()