#!/bin/bash
# P0 Smoke Test — run from repo root
set -e
cd "$(dirname "$0")/../.."

echo "=== P0 Smoke Test ==="

echo -n "P0-1 token estimator: "
.venv/bin/python -c "
from shared_backend.token_estimator import estimate_tokens
r = estimate_tokens('你好World')
assert r['level'] == 'ok', f'FAIL: {r}'
print('OK')
"
echo -n "P0-2 section hash: "
PYTHONPATH=apps/web-ui-service .venv/bin/python -c "
from app.services.requirement_document_service import _stable_section_id
id1 = _stable_section_id('登录模块', None)
id2 = _stable_section_id('登录模块', None)
assert id1 == id2, f'FAIL: {id1} != {id2}'
print('OK')
"
echo -n "P0-3 prompt chain: "
.venv/bin/python -c "
import os
agent_path = 'agents/requirement-parser-agent/src/agent.py'
assert os.path.exists(agent_path), 'agent.py not found'
content = open(agent_path).read()
assert 'prompt_system or SYSTEM_PROMPT' in content, 'fallback pattern missing'
orchestrator_path = 'apps/web-ui-service/app/services/workbench_generation_api/orchestrator_client_factory.py'
assert os.path.exists(orchestrator_path), 'orchestrator client not found'
print('OK (static checks passed, integration requires running service)')
"
echo -n "Service health: "
curl -sf -o /dev/null -w "%{http_code}" http://localhost:8013/health 2>/dev/null && echo " (UP)" || echo " (DOWN — skip integration test)"

echo "=== Smoke Done ==="
