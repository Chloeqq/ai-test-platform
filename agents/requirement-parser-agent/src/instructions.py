"""
Requirement Parser Agent runtime notes.

Current mode:
- Deterministic rule-based parser is the default execution path.
- Optional LLM path is reserved for future rollout and should preserve
  RequirementSpecV1 schema compatibility.

Input contracts:
- requirement/user_story/prd_text/git_diff/defect_ticket/runtime_logs (text)
- prd_url/openapi_url (remote document URL, fetched with safety checks)
- git_diff_path (local file path, read under repository allowlist)

Output contract:
- RequirementSpecV1 JSON object only.
"""

INSTRUCTIONS_VERSION = "requirement-parser.instructions.v1.1.0"
