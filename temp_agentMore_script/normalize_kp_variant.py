"""知识点变体统一：'递推' → '算法：递推'（一次性数据迁移脚本）

背景：库内两个变体并存——'算法：递推' 30 题（gesp-4 全系 + gesp-5 部分真题）
vs '递推' 4 题（gesp-5 202406/202409/202412/202503）。统一到主流 '算法：递推'
（与库内 '算法：排序概念和稳定性'、'算法：排序算法' 的官方大纲命名风格一致）。

用法：
  python scripts/normalize_kp_variant.py           # dry-run：只打印将要修改的内容
  python scripts/normalize_kp_variant.py --apply   # 实际写入

安全性：
- 文本级替换 "递推" → "算法：递推"（JSON 数组元素级精确匹配，不重序列化文件）
- 写入前后解析级校验：除 knowledge_points 外所有字段必须完全不变；
  替换后不得残留 '递推' 变体元素
"""
import json
import sys
from pathlib import Path

QB = Path(__file__).parent.parent / "question_bank"
OLD, NEW = "递推", "算法：递推"


def scan():
    """返回 {文件: [(题id, 旧kp列表), ...]}"""
    plan = {}
    for f in sorted(QB.glob("gesp-*.json")):
        try:
            questions = json.load(open(f, encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            print(f"!! {f.name} 无法解析，跳过: {e}")
            continue
        hits = [
            (q["id"], q["knowledge_points"])
            for q in questions
            if OLD in q.get("knowledge_points", [])
        ]
        if hits:
            plan[f] = hits
    return plan


def main():
    plan = scan()
    if not plan:
        print("没有需要统一的题目（'递推' 变体已清零）")
        return

    total = sum(len(h) for h in plan.values())
    for f, hits in plan.items():
        print(f"{f.name}:")
        for qid, kps in hits:
            print(f"  {qid}: {kps}")
    print(f"\n共 {total} 题待统一（涉及 {len(plan)} 个文件），方向: '{OLD}' → '{NEW}'")

    if "--apply" not in sys.argv:
        print("dry-run 模式，未写入。确认无误后执行: python scripts/normalize_kp_variant.py --apply")
        return

    for f, hits in plan.items():
        before = json.load(open(f, encoding="utf-8"))
        text = f.read_text(encoding="utf-8")
        new_text = text.replace(f'"{OLD}"', f'"{NEW}"')

        # 写前校验：解析级对比，除 kp 外所有字段不变
        after = json.loads(new_text)
        assert len(before) == len(after), f"{f.name}: 题数变化"
        for qb, qa in zip(before, after):
            for field in qb:
                if field == "knowledge_points":
                    continue
                assert qb[field] == qa[field], f"{f.name} {qb['id']}: 字段 {field} 被误改"
            expected = [NEW if k == OLD else k for k in qb["knowledge_points"]]
            assert qa["knowledge_points"] == expected, f"{f.name} {qb['id']}: kp 变化异常"
        # 无残留
        assert not any(OLD in q["knowledge_points"] for q in after), f"{f.name}: 仍有残留"

        f.write_text(new_text, encoding="utf-8")
        print(f"✓ {f.name}: {len(hits)} 题已统一")

    print("\n完成。请重建索引：python -c \"from app.core.question_loader import build_question_bank_index; build_question_bank_index()\"")


if __name__ == "__main__":
    main()
