# mypy: ignore-errors

import time
from typing import List
import subprocess
from .base_executor import BaseTestExecutor, ExecutionConfig, ExecutionResult


class UiTestExecutor(BaseTestExecutor):
    """UI测试执行器"""
    
    def get_test_type(self) -> str:
        return "UI"
    
    def run(self, case_ids: List[str], config: ExecutionConfig) -> ExecutionResult:
        """
        执行UI测试用例（基于Playwright）
        """
        start_time = time.time()
        try:
            # 构建pytest命令来执行UI测试
            cmd = [
                "python", "-m", "pytest",
                "--tb=short",
                "--maxfail=1",
                f"--timeout={config.timeout//1000}"
            ]
            
            # 添加Playwright特定参数
            cmd.extend([
                f"--browser={config.browser}",
            ])
            
            if config.headless:
                cmd.append("--headless")
            
            # 如果有具体的用例ID，则只运行这些用例
            if case_ids:
                # 假设UI测试用例存储在特定目录下
                test_paths = []
                for case_id in case_ids:
                    # 将用例ID转换为对应的pytest路径
                    # 例如: TC_UI_001 -> tests/ui/test_tc_ui_001.py
                    test_path = f"tests/ui/test_{case_id.lower()}.py"
                    test_paths.append(test_path)
                
                cmd.extend(test_paths)
            else:
                # 运行所有UI测试
                cmd.append("tests/ui/")
            
            # 添加报告选项
            cmd.extend([
                "--html=reports/ui_test_report.html",
                "--self-contained-html",
                "-v"
            ])
            
            # 执行测试
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=config.timeout//1000 + 60  # 给UI测试更多时间
            )
            
            duration = time.time() - start_time
            
            if result.returncode == 0:
                return ExecutionResult(
                    success=True,
                    duration=duration,
                    output=result.stdout,
                    error=result.stderr if result.stderr else None,
                    report_url="reports/ui_test_report.html"
                )
            else:
                return ExecutionResult(
                    success=False,
                    duration=duration,
                    output=result.stdout,
                    error=result.stderr,
                    report_url="reports/ui_test_report.html"
                )
                
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            return ExecutionResult(
                success=False,
                duration=duration,
                output="",
                error="UI test execution timed out"
            )
        except Exception as e:
            duration = time.time() - start_time
            return ExecutionResult(
                success=False,
                duration=duration,
                output="",
                error=str(e)
            )
