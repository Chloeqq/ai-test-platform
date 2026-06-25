"""Quality Gate 规则自动发现。

导入所有规则模块，触发 @register_rule 装饰器执行。
"""

# 导入每条规则以触发注册
from . import rule_001_title_data_mismatch      # noqa: F401
from . import rule_002_missing_test_data        # noqa: F401
from . import rule_003_negative_weak_assertion  # noqa: F401
from . import rule_004_dependency_not_prepared  # noqa: F401
from . import rule_005_missing_precondition     # noqa: F401
from . import rule_006_unknown_element          # noqa: F401
from . import rule_007_unused_test_data         # noqa: F401
from . import rule_008_missing_assertion        # noqa: F401
from . import rule_009_assertion_target_invalid # noqa: F401
from . import rule_010_step_data_inconsistency  # noqa: F401
from . import rule_011_behavior_keyword_mismatch       # noqa: F401
from . import rule_012_title_step_mismatch      # noqa: F401
from . import rule_013_external_state_dependency # noqa: F401
from . import rule_014_page_object_mismatch     # noqa: F401
from . import rule_015_requirement_mismatch     # noqa: F401
from . import rule_016_ai_hallucination         # noqa: F401
from . import rule_017_case_incomplete          # noqa: F401
