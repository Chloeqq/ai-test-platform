"""
Requirement Parser Agent runtime notes.

Current mode:
- Pure LLM only.
- Any parser failure must fail fast; no fallback/spec salvage is allowed.

Input contracts:
- requirement/user_story/prd_text/git_diff/defect_ticket/runtime_logs (text)
- prd_url/openapi_url (remote document URL, fetched with safety checks)
- git_diff_path (local file path, read under repository allowlist)

Output contract:
- RequirementSpecV1 JSON object only.
"""

INSTRUCTIONS_VERSION = "requirement-parser.instructions.v1.1.0"
