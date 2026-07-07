"""Day 11: enumerate 与索引"""

# ============================================================
# 上午：写新函数 — 用 enumerate 替代 range(len(...))
# ============================================================

def traverse_with_index(items: list) -> list[tuple[int, object]]:
    """遍历列表时同时输出索引和元素。
    用 enumerate，不要用 range(len(...))。
    traverse_with_index(["a", "b", "c"]) → [(0, "a"), (1, "b"), (2, "c")]
    traverse_with_index([]) → []
    """
    result_list = []
    if not items:
        return []
    for index, item in enumerate(items):
        result_list.append((index, item))
    return result_list





def find_duplicate_indices(items: list) -> dict[object, list[int]]:
    """找出列表中重复元素的所有索引位置。
    只返回出现次数 > 1 的元素，值为该元素所有出现的索引列表。
    用 enumerate 遍历。
    find_duplicate_indices([1, 2, 1, 3, 2]) → {1: [0, 2], 2: [1, 4]}
    find_duplicate_indices(["a", "b", "c"]) → {}
    find_duplicate_indices([1, 1, 1]) → {1: [0, 1, 2]}
    """
    index_map = {}
    duplicate= {}
    for index, item in enumerate(items):
        if item not in index_map:
            index_map[item] = []
        index_map[item].append(index)

    for key, value in index_map.items():
        if len(value) > 1:
            duplicate[key] = value
    return duplicate










def merge_lists_by_index(nums: list, chars: list) -> list[dict]:
    """将两个列表按索引对应合并为字典列表。
    用 enumerate 获取索引。以较短列表的长度为准。
    merge_lists_by_index([1, 2], ["a", "b"]) →
        [{"index": 0, "num": 1, "char": "a"}, {"index": 1, "num": 2, "char": "b"}]
    merge_lists_by_index([1, 2, 3], ["a"]) → [{"index": 0, "num": 1, "char": "a"}]
    merge_lists_by_index([], ["a", "b"]) → []
    """
    result: list[dict] = []
    for i, num in enumerate(nums):
        if i >= len(chars):
            break
        result.append({"index": i, "num": num, "char": chars[i]})
    return result


def paginate(items: list, page: int, page_size: int) -> dict:
    """实现一个简单的分页器：给定列表和页码(1-indexed)，返回对应页的数据。
    返回 dict 包含 items、page、total_pages、has_next、has_prev。
    用 enumerate 定位当前页的起止索引。
    页码超出范围时返回空 items。

    result = paginate([1,2,3,4,5,6,7], page=2, page_size=3)
    → {"items": [4,5,6], "page": 2, "total_pages": 3, "has_next": True, "has_prev": True}

    paginate([1,2,3], page=5, page_size=2)
    → {"items": [], "page": 5, "total_pages": 2, "has_next": False, "has_prev": True}
    """
    total_pages = max(1, (len(items) + page_size - 1) // page_size) if items else 1
    start = (page - 1) * page_size
    end = start + page_size

    # 用 enumerate 切片
    page_items: list = []
    for i, item in enumerate(items):
        if i >= start and i < end:
            page_items.append(item)
        if i >= end:
            break

    return {
        "items": page_items,
        "page": page,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1,
    }


def fizzbuzz_with_enumerate(n: int) -> list[str]:
    """用 enumerate 重写 FizzBuzz。
    用 enumerate 的索引作为数字（而不是单独维护计数器 i）。
    FizzBuzz 规则：3的倍数→"Fizz"，5的倍数→"Buzz"，15的倍数→"FizzBuzz"，否则→数字字符串。
    fizzbuzz_with_enumerate(5) → ["1", "2", "Fizz", "4", "Buzz"]
    fizzbuzz_with_enumerate(15)[-1] → "FizzBuzz"
    """
    result: list[str] = []
    for num, _ in enumerate(range(n), start=1):
        if num % 15 == 0:
            result.append("FizzBuzz")
        elif num % 3 == 0:
            result.append("Fizz")
        elif num % 5 == 0:
            result.append("Buzz")
        else:
            result.append(str(num))
    return result


# ============================================================
# 下午：逆向项目代码 — 还原 execution_compiler.py 中的 enumerate 逻辑
# ============================================================

def extract_steps(point: dict) -> list[dict]:
    """逆向重写 execution_compiler.py 中 _extract_steps 的逻辑（第129-147行）。
    从 point 中提取 steps，统一返回 list[dict] 格式。
    - steps 是 list[dict] → 直接返回
    - steps 是 list[str] → 每个字符串包成 {"raw_text": str}
    - steps 是 dict → 包成单元素列表 [dict]
    - steps 是其他非 None 值 → 转字符串后包成 {"raw_text": str}
    - steps 是 None/不存在 → 返回 []
    提示：用 isinstance 检查类型，str(value or "") 处理 None。

    extract_steps({"steps": [{"action": "click"}, {"action": "type"}]}) → [{"action": "click"}, {"action": "type"}]
    extract_steps({"steps": ["click button", "type text"]}) → [{"raw_text": "click button"}, {"raw_text": "type text"}]
    extract_steps({"steps": {"action": "click"}}) → [{"action": "click"}]
    extract_steps({"steps": None}) → []
    extract_steps({}) → []
    """
    raw_steps = point.get("steps")
    result: list[dict] = []

    if isinstance(raw_steps, list):
        for step in raw_steps:
            if isinstance(step, dict):
                result.append(step)
            else:
                text = str(step or "").strip()
                if text:
                    result.append({"raw_text": text})
    elif isinstance(raw_steps, dict):
        result.append(raw_steps)
    elif raw_steps is not None:
        text = str(raw_steps).strip()
        if text:
            result.append({"raw_text": text})

    return result


def normalize_test_points(points: list[dict]) -> list[dict]:
    """逆向重写 execution_compiler.py 中 normalize_test_points 的逻辑（第150-199行）。
    校验并规范化 test_points：
    1. points 必须是 list，否则抛 ValueError
    2. points 不能为空，否则抛 ValueError
    3. 每个 point 必须是 dict，否则抛 ValueError（带 index 信息）
    4. 每个 point 必须有 intent_id，否则抛 ValueError（带 index 信息）
    5. 每个 point 提取 steps 后不能为空，否则抛 ValueError（带 index 信息）
    6. 返回规范化后的列表，每项含 intent_id、point_index、steps
    关键模式：for point_index, raw_point in enumerate(points)

    points = [{"intent_id": "login", "steps": [{"action": "click"}]}]
    normalize_test_points(points) → [{"intent_id": "login", "point_index": 0, "steps": [{"action": "click"}]}]
    """
    if not isinstance(points, list):
        raise ValueError("points must be a list")
    if not points:
        raise ValueError("points must not be empty")

    normalized: list[dict] = []
    for point_index, raw_point in enumerate(points):
        if not isinstance(raw_point, dict):
            raise ValueError(f"point at index {point_index} must be a dict")

        intent_id = str(raw_point.get("intent_id") or "").strip()
        if not intent_id:
            raise ValueError(f"point at index {point_index} missing intent_id")

        steps = extract_steps(raw_point)
        if not steps:
            raise ValueError(f"point at index {point_index} has no executable steps")

        normalized.append({
            "intent_id": intent_id,
            "point_index": point_index,
            "steps": steps,
        })

    return normalized


# ============================================================
# 测试
# ============================================================

if __name__ == "__main__":
    # 上午
    assert traverse_with_index(["a", "b", "c"]) == [(0, "a"), (1, "b"), (2, "c")]
    assert traverse_with_index([]) == []
    print("✓ traverse_with_index")

    assert find_duplicate_indices([1, 2, 1, 3, 2]) == {1: [0, 2], 2: [1, 4]}
    assert find_duplicate_indices(["a", "b", "c"]) == {}
    assert find_duplicate_indices([1, 1, 1]) == {1: [0, 1, 2]}
    assert find_duplicate_indices([]) == {}
    print("✓ find_duplicate_indices")

    assert merge_lists_by_index([1, 2], ["a", "b"]) == [
        {"index": 0, "num": 1, "char": "a"},
        {"index": 1, "num": 2, "char": "b"},
    ]
    assert merge_lists_by_index([1, 2, 3], ["a"]) == [{"index": 0, "num": 1, "char": "a"}]
    assert merge_lists_by_index([], ["a", "b"]) == []
    print("✓ merge_lists_by_index")

    r = paginate([1, 2, 3, 4, 5, 6, 7], page=2, page_size=3)
    assert r["items"] == [4, 5, 6]
    assert r["page"] == 2
    assert r["total_pages"] == 3
    assert r["has_next"] is True
    assert r["has_prev"] is True

    r2 = paginate([1, 2, 3], page=5, page_size=2)
    assert r2["items"] == []
    assert r2["has_next"] is False
    assert r2["has_prev"] is True

    r3 = paginate([1, 2, 3, 4], page=1, page_size=2)
    assert r3["items"] == [1, 2]
    assert r3["has_prev"] is False
    assert r3["has_next"] is True

    r4 = paginate([], page=1, page_size=10)
    assert r4["items"] == []
    assert r4["total_pages"] == 1
    print("✓ paginate")

    assert fizzbuzz_with_enumerate(5) == ["1", "2", "Fizz", "4", "Buzz"]
    assert fizzbuzz_with_enumerate(15)[-1] == "FizzBuzz"
    assert fizzbuzz_with_enumerate(15)[2] == "Fizz"       # i=3
    assert fizzbuzz_with_enumerate(15)[4] == "Buzz"       # i=5
    assert fizzbuzz_with_enumerate(15)[14] == "FizzBuzz"  # i=15
    assert len(fizzbuzz_with_enumerate(30)) == 30
    print("✓ fizzbuzz_with_enumerate")

    # 下午
    assert extract_steps({"steps": [{"action": "click"}, {"action": "type"}]}) == [
        {"action": "click"}, {"action": "type"}
    ]
    assert extract_steps({"steps": ["click button", "type text"]}) == [
        {"raw_text": "click button"}, {"raw_text": "type text"}
    ]
    assert extract_steps({"steps": {"action": "click"}}) == [{"action": "click"}]
    assert extract_steps({"steps": None}) == []
    assert extract_steps({}) == []
    assert extract_steps({"steps": "single string"}) == [{"raw_text": "single string"}]
    print("✓ extract_steps")

    points = [{"intent_id": "login", "steps": [{"action": "click"}]}]
    result = normalize_test_points(points)
    assert len(result) == 1
    assert result[0]["intent_id"] == "login"
    assert result[0]["point_index"] == 0
    assert result[0]["steps"] == [{"action": "click"}]

    # 多 points
    points2 = [
        {"intent_id": "login", "steps": [{"action": "click"}]},
        {"intent_id": "search", "steps": [{"action": "type"}, {"action": "press_enter"}]},
    ]
    result2 = normalize_test_points(points2)
    assert len(result2) == 2
    assert result2[0]["point_index"] == 0
    assert result2[1]["point_index"] == 1
    assert result2[1]["intent_id"] == "search"

    # 错误情况
    try:
        normalize_test_points("not a list")
        assert False, "应该抛 ValueError"
    except ValueError:
        pass

    try:
        normalize_test_points([])
        assert False, "应该抛 ValueError"
    except ValueError:
        pass

    try:
        normalize_test_points([{"intent_id": "x"}])  # 无 steps
        assert False, "应该抛 ValueError"
    except ValueError:
        pass

    try:
        normalize_test_points([{"steps": [{"a": 1}]}])  # 无 intent_id
        assert False, "应该抛 ValueError"
    except ValueError:
        pass

    print("✓ normalize_test_points")

    print("\n🎉 全部通过！")
