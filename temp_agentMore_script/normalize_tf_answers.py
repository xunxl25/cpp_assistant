"""判断题 answer 历史格式统一：true/false → T/F

一次性数据迁移脚本（独立于代码 patch 运行）。
用法：
  python scripts/normalize_tf_answers.py           # dry-run：只打印将要修改的内容
  python scripts/normalize_tf_answers.py --apply   # 实际写入

安全性：
- 文本级精确替换（"answer": "true" → "answer": "T"），不做整文件重序列化，
  保证除目标行外文件内容零变化
- 替换次数必须与 json 解析统计的 true_false 题数完全一致，否则报错不写入
- 写入后自动复查：重新解析并统计，若仍有 true/false 残留则报错
"""
import json
import sys
from pathlib import Path

QB = Path(__file__).parent.parent / "question_bank"
MAPPING = {"true": "T", "false": "F"}


def scan():
    """返回 {文件: [(题id, 旧值, 新值), ...]}"""
    plan = {}
    for f in sorted(QB.glob("gesp-*.json")):
        try:
            questions = json.load(open(f, encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            print(f"!! {f.name} 无法解析，跳过: {e}")
            continue
        hits = [
            (q["id"], q["answer"], MAPPING[q["answer"]])
            for q in questions
            if q.get("type") == "true_false" and q.get("answer") in MAPPING
        ]
        if hits:
            plan[f] = hits
    return plan


def main():
    apply_mode = "--apply" in sys.argv
    plan = scan()

    if not plan:
        print("题库中所有判断题 answer 均为 T/F 格式，无需处理。")
        return

    total = 0
    for f, hits in plan.items():
        print(f"{f.name}:")
        for qid, old, new in hits:
            print(f"  {qid}: {old} → {new}")
        total += len(hits)
    print(f"\n共 {total} 题待统一（涉及 {len(plan)} 个文件）")

    if not apply_mode:
        print("dry-run 模式，未写入。确认无误后执行: python scripts/normalize_tf_answers.py --apply")
        return

    # --apply：文本级替换，次数强校验
    for f, hits in plan.items():
        text = f.read_text(encoding="utf-8")
        n_expect = len(hits)
        n_true = text.count('"answer": "true"')
        n_false = text.count('"answer": "false"')
        if n_true + n_false != n_expect:
            print(f"!! {f.name}: 文本替换计数不符（文本 {n_true}+{n_false} vs 解析 {n_expect}），跳过不写")
            continue
        text = text.replace('"answer": "true"', '"answer": "T"')
        text = text.replace('"answer": "false"', '"answer": "F"')
        f.write_text(text, encoding="utf-8")
        # 写后复查
        remain = [
            q["id"] for q in json.load(open(f, encoding="utf-8"))
            if q.get("type") == "true_false" and q.get("answer") in MAPPING
        ]
        if remain:
            print(f"!! {f.name} 写入后仍有残留: {remain}")
        else:
            print(f"✓ {f.name}: {n_expect} 题已统一为 T/F")

    print("\n完成。请重建索引：python -c \"from app.core.question_loader import build_question_bank_index; build_question_bank_index()\"")


if __name__ == "__main__":
    main()
