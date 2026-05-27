from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ExecutionConfig:
    """执行配置"""
    browser: str = "chromium"
    headless: bool = True
    timeout: int = 30000
    retries: int = 1
    parallel: bool = False


@dataclass
class ExecutionResult:
    """执行结果"""
    success: bool
    duration: float
    output: str
    error: Optional[str] = None
    report_url: Optional[str] = None


class BaseTestExecutor(ABC):
    """测试执行器基类"""
    
    @abstractmethod
    def get_test_type(self) -> str:
        """返回测试类型"""
        pass
    
    @abstractmethod
    def run(self, case_ids: List[str], config: ExecutionConfig) -> ExecutionResult:
        """执行测试用例"""
        pass
