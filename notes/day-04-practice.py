"""
第 3 天上午练习 — set 集合与条件判断

规则：
1. 关掉所有 AI 工具和参考文件
2. 在下面 5 个函数的 TODO 处手写实现
3. 写完运行: python notes/day-03-practice.py
4. 全部通过 → 打 ✓
"""
from typing import Any


# ============================================================
# 练习 1: 交集、并集、差集
# 需求：给定两个列表，返回它们的交集、并集、差集（a有b没有）
# 示例：list1=[1,2,3,4], list2=[3,4,5,6]
#       交集 [3,4]  并集 [1,2,3,4,5,6]  差集 [1,2]
# ============================================================
def set_operations(list1: list, list2: list) -> dict[str, list]:
    """返回 {"intersection": ..., "union": ..., "difference": ...}"""
    lst_a = list(set(list2) & set(list1))
    lst_b = list(set(list1) | set(list2))
    lst_c = list(set(list1) - set(list2))
    return {"intersection": lst_a, "union": lst_b, "difference": lst_c}

# ============================================================
# 练习 2: 判断列表是否有重复元素
# 需求：有重复返回 True，全部唯一返回 False
# 示例：[1,2,2,3] → True  [1,2,3] → False
# ============================================================
def has_duplicates(items: list) -> bool:
    """判断列表是否有重复元素。"""
    return len(set(items)) != len(items)


# ============================================================
# 练习 3: 删除所有元音字母
# 需求：删除字符串中所有 a e i o u（大小写都算）
# 示例："Hello World" → "Hll Wrld"
# ============================================================
import re
def remove_vowels(text: str) -> str:
    """删除所有元音字母 (a, e, i, o, u)，大小写均删除。"""
    return re.sub(r'[aeiouAEIOU]', '', text)



# ============================================================
# 练习 4: 判断字符串是否只包含字母和数字
# 需求：只含字母和数字 → True，有其他字符 → False
# 示例："Hello123" → True  "Hello 123" → False  "你好" → False
# ============================================================
def is_alphanumeric(text: str) -> bool:
    """判断字符串是否只包含字母和数字（不含空格、符号、中文等）。"""
    for ch in text:
        if not (ch.isascii() and ch.isalnum()):
            return False
    return True


# ============================================================
# 练习 5: 找出闰年
# 需求：闰年规则 — 能被4整除但不能被100整除，或能被400整除
# 示例：[2000, 1900, 2024, 2023] → [2000, 2024]
# ============================================================
def find_leap_years(years: list[int]) -> list[int]:
    """返回所有闰年。"""
    lst = []
    for year in years:

        if year % 400 == 0 or (year % 4 == 0 and year % 100 != 0):
            lst.append(year)
    return lst


# ============================================================
# 自测
# ============================================================
if __name__ == "__main__":
    # --- 交集并集差集 ---
    result = set_operations([1, 2, 3, 4], [3, 4, 5, 6])
    assert sorted(result["intersection"]) == [3, 4], "set_ops-1: 交集"
    assert sorted(result["union"]) == [1, 2, 3, 4, 5, 6], "set_ops-2: 并集"
    assert sorted(result["difference"]) == [1, 2], "set_ops-3: 差集"
    # 边界：空列表
    result2 = set_operations([], [1, 2])
    assert result2["intersection"] == [], "set_ops-4: 空列表交集"
    assert sorted(result2["union"]) == [1, 2], "set_ops-5: 空列表并集"
    assert result2["difference"] == [], "set_ops-6: 空列表差集"
    print("✅ set_operations 通过")

    # --- 重复元素 ---
    assert has_duplicates([1, 2, 2, 3]) == True, "dup-1: 有重复"
    assert has_duplicates([1, 2, 3]) == False, "dup-2: 无重复"
    assert has_duplicates([]) == False, "dup-3: 空列表"
    assert has_duplicates(["a", "b", "a"]) == True, "dup-4: 字符串重复"
    print("✅ has_duplicates 通过")

    # --- 删除元音 ---
    assert remove_vowels("Hello World") == "Hll Wrld", "vowel-1"
    assert remove_vowels("AEIOUaeiou") == "", "vowel-2: 全元音"
    assert remove_vowels("BCDFG") == "BCDFG", "vowel-3: 无元音"
    assert remove_vowels("") == "", "vowel-4: 空字符串"
    print("✅ remove_vowels 通过")

    # --- 字母数字判断 ---
    assert is_alphanumeric("Hello123") == True, "alnum-1"
    assert is_alphanumeric("Hello 123") == False, "alnum-2: 有空格"
    assert is_alphanumeric("你好") == False, "alnum-3: 中文"
    assert is_alphanumeric("") == True, "alnum-4: 空字符串（vacuously true）"
    assert is_alphanumeric("abc_def") == False, "alnum-5: 有下划线"
    print("✅ is_alphanumeric 通过")

    # --- 闰年 ---
    assert find_leap_years([2000, 1900, 2024, 2023]) == [2000, 2024], "leap-1"
    assert find_leap_years([1600, 1700, 1800, 1900]) == [1600], "leap-2: 世纪年"
    assert find_leap_years([]) == [], "leap-3: 空列表"
    assert find_leap_years([2023, 2025, 2026]) == [], "leap-4: 无闰年"
    print("✅ find_leap_years 通过")

    print("\n🎉 全部 5 道题通过！")