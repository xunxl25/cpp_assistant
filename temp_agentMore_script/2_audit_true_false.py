"""诊断脚本：扫描 question_bank/ 中所有判断题的 answer 字段是否合法。

用法:
    cd D:\\Projects\\cpp_assistant
    python scripts/audit_true_false.py

输出:
    - 统计总数 / 合法数 / 异常数
    - 列出所有异常题目的文件、ID、当前 answer、题目前 40 字
"""
import json
import glob
import os
import sys

QUESTION_BANK_DIR = "question_bank"
VALID_ANSWERS = {"true", "false", "T", "F"}


def main():
    json_files = sorted(glob.glob(os.path.join(QUESTION_BANK_DIR, "*.json")))
    if not json_files:
        print(f"未找到 JSON 文件，请确认目录 {QUESTION_BANK_DIR} 存在")
        return

    total_tf = 0
    bad_count = 0
    bad_list = []

    for fpath in json_files:
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                questions = json.load(f)
        except Exception as e:
            print(f"⚠️ 无法读取 {fpath}: {e}")
            continue

        for q in questions:
            if not isinstance(q, dict):
                continue
            if q.get("type") != "true_false":
                continue

            total_tf += 1
            answer = q.get("answer", "")

            if answer not in VALID_ANSWERS:
                bad_count += 1
                qid = q.get("id", "(无ID)")
                qtext = str(q.get("question", ""))[:40]
                bad_list.append({
                    "file": os.path.basename(fpath),
                    "id": qid,
                    "answer": answer,
                    "question_preview": qtext,
                })

    print("=" * 60)
    print(f"判断题总数: {total_tf}")
    print(f"合法 (answer=true/false): {total_tf - bad_count}")
    print(f"异常: {bad_count}")
    print("=" * 60)

    if bad_list:
        print("\n异常题目列表:")
        print("-" * 60)
        for item in bad_list:
            print(f"  文件: {item['file']}")
            print(f"  ID:   {item['id']}")
            print(f"  answer: {item['answer']}")
            print(f"  题目: {item['question_preview']}...")
            print("-" * 60)
        print(f"\n共 {bad_count} 道异常，请手动修改对应 JSON 文件的 answer 字段")
        print('将 answer 改为 "true" 或 "false"')
    else:
        print("\n✅ 所有判断题数据正常")


if __name__ == "__main__":
    main()
