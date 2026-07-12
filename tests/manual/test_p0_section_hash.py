"""P0-2 Section ID 稳定 hash 测试。"""
import os, sys, hashlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, "apps/web-ui-service")

from app.services.requirement_document_service import (
    _stable_section_id, _sections_from_headings, _sections_from_pdf,
)
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
print("\n=== P0-2 正常场景 ===")

id1 = _stable_section_id("登录模块", None)
t("stable_id generates sec- prefix", id1.startswith("sec-"), id1)
t("stable_id length = 12", len(id1) == 12, f"got {len(id1)}")

id2 = _stable_section_id("登录模块", None)
t("Same title+parent → same ID", id1 == id2, f"{id1} vs {id2}")

id3 = _stable_section_id("登录模块", "sec-abc")
t("Same title+different parent → different ID", id1 != id3, f"{id1} vs {id3}")

id4 = _stable_section_id("用户管理", None)
t("Different title → different ID", id1 != id4, f"{id1} vs {id4}")

# Full blocks_to_sections test
blocks = [
    {"type": "heading", "level": 2, "text": "登录模块"},
    {"type": "paragraph", "text": "用户输入账号密码"},
    {"type": "heading", "level": 3, "text": "账号密码登录"},
    {"type": "paragraph", "text": "输入账号和密码点击登录"},
    {"type": "heading", "level": 2, "text": "用户管理"},
    {"type": "paragraph", "text": "管理员查看用户列表"},
]
s1 = _sections_from_headings(blocks)
s2 = _sections_from_headings(blocks)
t("Re-parse returns same section count", len(s1) == len(s2), f"{len(s1)} vs {len(s2)}")
t("Re-parse returns same IDs", [s["id"] for s in s1] == [s["id"] for s in s2])
t("First section title preserved", s1[0]["title"] == "登录模块")
t("Second section title preserved", s1[1]["title"] == "用户管理")

# ========== 边界场景 ==========
print("\n=== P0-2 边界场景 ===")

# Empty
r = _sections_from_headings([])
t("Empty blocks → empty sections", r == [], str(r))

# No headings — fallback
blocks_no_h = [
    {"type": "paragraph", "text": "just text"},
    {"type": "paragraph", "text": "more text"},
]
r = _sections_from_headings(blocks_no_h)
t("No headings → 1 section 'sec-full'", len(r) == 1, str(r))
t("Fallback section has title '全文'", r[0]["title"] == "全文", r[0]["title"])
t("Fallback section includes all blocks", len(r[0]["block_ids"]) == 2, str(r[0]["block_ids"]))

# Single heading
blocks_single = [
    {"type": "heading", "level": 1, "text": "只有一章"},
    {"type": "paragraph", "text": "正文内容"},
]
r = _sections_from_headings(blocks_single)
t("Single heading → 1 section", len(r) == 1, str(r))

# All paragraphs only
r_para = _sections_from_headings([{"type": "paragraph", "text": "a"}, {"type": "paragraph", "text": "b"}])
t("All paragraphs → fallback single section", len(r_para) == 1)
t("Fallback has stable ID", r_para[0]["id"] == "sec-full")

# Long title
r = _stable_section_id("这是一个非常长的标题" * 10, None)
t("Very long title still produces valid ID", r.startswith("sec-") and len(r) == 12)

# Special chars in title
id_special = _stable_section_id("登录/注册 & 找回密码", None)
t("Special chars in title produce valid ID", id_special.startswith("sec-") and len(id_special) == 12)

# Emoji in title
id_emoji = _stable_section_id("支付💰流程", None)
t("Emoji in title produces valid ID", id_emoji.startswith("sec-") and len(id_emoji) == 12)

# Empty title (defensive)
id_empty = _stable_section_id("", None)
t("Empty title still produces valid ID", id_empty.startswith("sec-") and len(id_empty) == 12)

# PDF empty blocks
r_pdf_empty = _sections_from_pdf([])
t("PDF empty blocks → empty sections", r_pdf_empty == [], str(r_pdf_empty))

# ========== 一致性 ==========
print("\n=== P0-2 一致性 ===")

# 父子关系
blocks_tree = [
    {"type": "heading", "level": 2, "text": "父模块"},
    {"type": "heading", "level": 3, "text": "子模块1"},
    {"type": "paragraph", "text": "子1内容"},
    {"type": "heading", "level": 3, "text": "子模块2"},
    {"type": "paragraph", "text": "子2内容"},
]
r = _sections_from_headings(blocks_tree)
t("Parent has children", len(r) == 1 and len(r[0]["children"]) == 2, str(r[0]["id"]))
t("Children belong to parent", all(c["id"] for c in r[0]["children"]))
# Verify child IDs are stable — re-run produces same IDs
r2 = _sections_from_headings(blocks_tree)
t("Child ID stable across re-parse",
  r[0]["children"][0]["id"] == r2[0]["children"][0]["id"],
  f"{r[0]['children'][0]['id']} vs {r2[0]['children'][0]['id']}")

# PDF mode
pdf_blocks = [
    {"type": "paragraph", "text": "page1 content", "page": 1},
    {"type": "paragraph", "text": "page2 content", "page": 2},
]
r = _sections_from_pdf(pdf_blocks)
t("PDF: 2 pages → 2 sections", len(r) == 2)
t("PDF: page IDs start with 'page-'", all(s["id"].startswith("page-") for s in r))
t("PDF: page IDs are unique", len(set(s["id"] for s in r)) == 2)

# Same title + different parents → different IDs
id_a = _stable_section_id("子模块", "sec-aaa")
id_b = _stable_section_id("子模块", "sec-bbb")
t("Same title + different parents → different IDs", id_a != id_b, f"{id_a} vs {id_b}")

# ========== 硬编码检查 ==========
print("\n=== P0-2 硬编码检查 ===")
import pathlib, re
src = pathlib.Path(__file__).parent.parent.parent / "apps" / "web-ui-service" / "app" / "services" / "requirement_document_service.py"
content = src.read_text()
t("_stable_section_id function exists", "_stable_section_id" in content)
t("hashlib imported", "import hashlib" in content)
# Robust check: no sequential sec-{N} ID generation
# Match sec- followed by word chars; exclude sec-full and sec-{8 hex chars}
sec_patterns = re.findall(r'sec-[a-zA-Z0-9_]+', content)
illegal = [p for p in sec_patterns
           if not p.startswith("sec-full") and not re.match(r'sec-[a-f0-9]{8}$', p)]
t("No sequential sec-{N} ID generation", len(illegal) == 0,
  f"found: {illegal[:5]}" if illegal else "clean")

print(f"\n=== P0-2 RESULTS: {passed} passed, {failed} failed ===")
sys.exit(1 if failed else 0)
