# mypy: ignore-errors

import time
from typing import List
import subprocess
from .base_executor import BaseTestExecutor, ExecutionConfig, ExecutionResult


class ApiTestExecutor(BaseTestExecutor):
    """API测试执行器"""
    
    def get_test_type(self) -> str:
        return "API"
    
    def run(self, case_ids: List[str], config: ExecutionConfig) -> ExecutionResult:
        """
        执行API测试用例
        """
        start_time = time.time()
        try:
            # 构建pytest命令来执行API测试
            cmd = [
                "python", "-m", "pytest", 
                "--tb=short", 
                "--maxfail=1",
                f"--timeout={config.timeout//1000}"
            ]
            
            # 如果有具体的用例ID，则只运行这些用例
            if case_ids:
                # 假设API测试用例存储在特定目录下
                test_paths = []
                for case_id in case_ids:
                    # 将用例ID转换为对应的pytest路径
                    # 例如: TC_API_001 -> tests/api/test_tc_api_001.py
                    test_path = f"tests/api/test_{case_id.lower()}.py"
                    test_paths.append(test_path)
                
                cmd.extend(test_paths)
            else:
                # 运行所有API测试
                cmd.append("tests/api/")
            
            if config.headless:
                cmd.extend(["-v"])  # 显示详细信息而不是使用GUI
            
            # 执行测试
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=config.timeout//1000 + 30  # 给一些额外时间
            )
            
            duration = time.time() - start_time
            
            if result.returncode == 0:
                return ExecutionResult(
                    success=True,
                    duration=duration,
                    output=result.stdout,
                    error=result.stderr if result.stderr else None
                )
            else:
                return ExecutionResult(
                    success=False,
                    duration=duration,
                    output=result.stdout,
                    error=result.stderr
                )
                
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            return ExecutionResult(
                success=False,
                duration=duration,
                output="",
                error="Test execution timed out"
            )
        except Exception as e:
            duration = time.time() - start_time
            return ExecutionResult(
                success=False,
                duration=duration,
                output="",
                error=str(e)
            )


# 辅助函数：用于创建API测试用例
def create_api_test_case(test_name: str, method: str, url: str, headers: dict = None, 
                        params: dict = None, data: dict = None) -> str:
    """
    创建API测试用例模板
    """
    template = f'''import pytest
import requests

def test_{test_name.replace(" ", "_").lower()}():
    """API测试: {test_name}"""
    url = "{url}"
    method = "{method.upper()}"
    headers = {headers or {}}
    params = {params or {}}
    data = {data or {}}
    
    response = requests.request(method, url, headers=headers, params=params, json=data)
    
    # 基础断言
    assert response.status_code in [200, 201], f"Expected status 200/201, got {{response.status_code}}"
    '''
    return template
