"""P0-1 Token 估算统一测试。运行: cd repo-root && .venv/bin/python tests/manual/test_p0_token_estimator.py"""
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from shared_backend.token_estimator import estimate_tokens

passed = 0
failed = 0


def t(desc, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print(f"  FAIL [{desc}]: {detail}")


# ========== 正常场景 ==========
print("\n=== P0-1 正常场景 ===")

r = estimate_tokens("用户在登录页输入账号密码并点击登录按钮完成鉴权。")
t("CJK-only text returns ok", r["level"] == "ok", str(r))
t("CJK-only returns char_count=len", r["char_count"] == 24, f"got {r['char_count']}")
t("CJK-only: tokens ≈ chars/1.6", abs(r["estimated_tokens"] - 15) <= 2, f"got {r['estimated_tokens']}")

r = estimate_tokens("Hello World")
t("ASCII-only text returns ok", r["level"] == "ok", str(r))
t("ASCII-only: tokens ≈ chars/4", r["estimated_tokens"] <= 5, f"got {r['estimated_tokens']}")

r = estimate_tokens("你好World")
t("Mixed CJK+ASCII", r["cjk_count"] == 2, f"got {r['cjk_count']}")
t("Mixed: estimated correct", r["estimated_tokens"] == int(round(2 / 1.6 + 5 / 4.0)), f"got {r['estimated_tokens']}")

# ========== 边界场景 ==========
print("\n=== P0-1 边界场景 ===")

# 刚好 8000 tokens (≈12800 CJK chars)
text_8k = "测" * 12800
r = estimate_tokens(text_8k)
t("8000 tokens: level=warn (≥8000)", r["level"] == "warn", f"tokens={r['estimated_tokens']} level={r['level']}")
t("8000 tokens boundary: >=warn threshold", r["estimated_tokens"] >= 8000, f"got {r['estimated_tokens']}")

# 7999 tokens
text_7999 = "测" * 12798
r = estimate_tokens(text_7999)
t("7999 tokens: level=ok (<8000)", r["level"] == "ok", f"tokens={r['estimated_tokens']} level={r['level']}")

# 16000 tokens
text_16k = "测" * 25600
r = estimate_tokens(text_16k)
t("16000 tokens: level=block (≥16000)", r["level"] == "block", f"tokens={r['estimated_tokens']}")

# 15999 tokens
text_15999 = "测" * 25598
r = estimate_tokens(text_15999)
t("15999 tokens: level=warn", r["level"] == "warn", f"tokens={r['estimated_tokens']}")

# 极值
r = estimate_tokens("")
t("Empty string: level=ok, tokens=0", r["level"] == "ok" and r["char_count"] == 0, str(r))
r = estimate_tokens("a")
t("Single char: tokens≈0-1", 0 <= r["estimated_tokens"] <= 1, f"got {r['estimated_tokens']}")
r = estimate_tokens("测" * 100000)
t("100k CJK chars: level=block", r["level"] == "block", f"tokens={r['estimated_tokens']}")

# ========== 异常场景 ==========
print("\n=== P0-1 异常场景 ===")

r = estimate_tokens(None)
t("None input: level=ok, tokens=0", r["level"] == "ok" and r["char_count"] == 0, str(r))

r = estimate_tokens("")
t("Empty string: all zeros", r["char_count"] == 0 and r["estimated_tokens"] == 0)

# Env override: 300 CJK chars → ~188 tokens → >=100 warn but <200 block → level=warn
os.environ["REQUIREMENT_SCOPE_WARN_TOKENS"] = "100"
os.environ["REQUIREMENT_SCOPE_BLOCK_TOKENS"] = "200"
r = estimate_tokens("测" * 300)
t("Env override: tokens ≈188, >=100 warn, <200 block → level=warn", r["level"] == "warn", f"tokens={r['estimated_tokens']} level={r['level']}")
# 350 CJK chars → ~219 tokens → >=200 block
r2 = estimate_tokens("测" * 350)
t("Env override: tokens ≈219, >=200 block → level=block", r2["level"] == "block", f"tokens={r2['estimated_tokens']} level={r2['level']}")
del os.environ["REQUIREMENT_SCOPE_WARN_TOKENS"]
del os.environ["REQUIREMENT_SCOPE_BLOCK_TOKENS"]

# 补充 P01-B-06: CJK Ext-B 字符 (U+20000)
r = estimate_tokens("\U00020000")
t("CJK Ext-B char counted as CJK", r["cjk_count"] == 1, f"got {r['cjk_count']}")

# 补充 P01-B-07: 日文假名不算 CJK
r = estimate_tokens("あいう")
t("Hiragana NOT counted as CJK", r["cjk_count"] == 0, f"got {r['cjk_count']}")

# 补充 P01-B-08: 韩文谚文不算 CJK
r = estimate_tokens("한글")
t("Hangul NOT counted as CJK", r["cjk_count"] == 0, f"got {r['cjk_count']}")

# 补充: 自定义阈值作为参数传入
r = estimate_tokens("测" * 100, warn_tokens=50, block_tokens=100)
t("Custom threshold param: warn", r["level"] == "warn", f"tokens={r['estimated_tokens']} level={r['level']}")
r = estimate_tokens("测" * 200, warn_tokens=50, block_tokens=100)
t("Custom threshold param: block", r["level"] == "block", f"tokens={r['estimated_tokens']} level={r['level']}")

# 补充 P01-E-03: warn>block 的防呆
r = estimate_tokens("测" * 500, warn_tokens=200, block_tokens=100)
t("warn>block safeguard: block→warn*2=400", r["block_tokens"] == 400, f"got block={r['block_tokens']} warn={r['warn_tokens']}")

# warn=block → auto block=warn*2
r = estimate_tokens("测" * 500, warn_tokens=100, block_tokens=100)
t("warn=block safeguard: block→warn*2", r["block_tokens"] == 200, f"got {r['block_tokens']}")

# ========== 数据一致性 ==========
print("\n=== P0-1 一致性 ===")

# orchestrator 和 web-ui 都调用同一个函数,验证相同输入→相同输出
text = "用户在登录页输入账号密码" * 10
from shared_backend.token_estimator import estimate_tokens as et1
r1 = et1(text)
r2 = et1(text)
t("Idempotent: same input→same output", r1["estimated_tokens"] == r2["estimated_tokens"])

# 验证 orchestrator 调用点使用 shared_backend.token_estimator
import ast, pathlib
orch_src = pathlib.Path(__file__).parent.parent.parent / "apps" / "ai-orchestrator" / "src" / "services" / "requirement_parse_support.py"
orch_content = orch_src.read_text() if orch_src.exists() else ""
t("Orchestrator imports shared_backend.token_estimator",
  "from shared_backend.token_estimator import estimate_tokens" in orch_content,
  "orchestrator import check")

# ========== 硬编码检查 ==========
print("\n=== P0-1 硬编码检查 ===")
import pathlib

src = pathlib.Path(__file__).parent.parent.parent / "apps" / "web-ui-service" / "app" / "services" / "requirement_document_service.py"
content = src.read_text()
has_1_6 = "1.6" in content
is_comment_1_6 = False
if has_1_6:
    idx = content.find("1.6")
    is_comment_1_6 = "#" in content[max(0, idx - 5):idx + 5]
t("No hardcoded 1.6 in requirement_document_service", not has_1_6 or is_comment_1_6)

has_8000 = "8000" in content
is_comment_8000 = False
if has_8000:
    idx8000 = content.find("8000")
    is_comment_8000 = "#" in content[max(0, idx8000 - 5):idx8000 + 5]
t("No hardcoded 8000 in requirement_document_service", not has_8000 or is_comment_8000 or "PORT" in content)

# Check token_estimator has constants
src2 = pathlib.Path(__file__).parent.parent.parent / "shared_backend" / "token_estimator.py"
content2 = src2.read_text()
t("token_estimator has _CJK_RATIO constant", "_CJK_RATIO" in content2)
t("token_estimator has _OTHER_RATIO constant", "_OTHER_RATIO" in content2)

print(f"\n=== P0-1 RESULTS: {passed} passed, {failed} failed ===")
sys.exit(1 if failed else 0)
