"""一次性迁移：question_bank/ 下 4 位日期文件名统一为 6 位

背景：
    JSON 文件名早期手误用了 yymm（如 gesp-4-2306.json），
    标准应为 yyyymm（与题目 id / exam.date / past_exam PDF 命名一致，如 gesp-4-202306.json）。
    JSON 内容本身已是 6 位标准，仅文件名需修正。

脚本行为：
    1. 扫描 question_bank/*.json，匹配 {type}-{level}-{4位数字}.json
    2. 校验 JSON 内容（首题 exam.date）与扩展后的 6 位日期一致，不一致则跳过并警告（安全网）
    3. 目标文件已存在时跳过
    4. 重命名（git 工作区会自动识别为 rename）
    5. 重建题库索引 question_bank_index.db
    6. 幂等：已符合标准的文件不受影响，可重复执行

用法：
    python scripts/migrate_filenames_six_digit.py --dry-run   # 只打印计划，不执行
    python scripts/migrate_filenames_six_digit.py             # 执行迁移
"""
import json
import re
import sys
from pathlib import Path

# 保证从任意目录执行都能导入项目模块
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

QUESTION_BANK_DIR = Path("question_bank")
# 文件名中的 4 位纯数字日期段（sample 等非数字段自然不匹配）
NAME_PATTERN = re.compile(r"^(?P<stem>.+)-(?P<date>\d{4})\.json$")


def check_content_matches(json_path: Path, six_digit: str) -> bool:
    """校验 JSON 内容（首题 exam.date）与 6 位日期一致，作为重命名的安全网"""
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"  [警告] 读取 {json_path.name} 失败: {e}")
        return False

    if not data or not isinstance(data, list):
        print(f"  [警告] {json_path.name} 内容为空或非数组")
        return False

    inner_date = str(data[0].get("exam", {}).get("date", ""))
    if inner_date != six_digit:
        print(f"  [警告] {json_path.name} 内容日期为 {inner_date!r}，"
              f"与扩展后的 {six_digit!r} 不一致，需人工确认，跳过")
        return False
    return True


def main():
    dry_run = "--dry-run" in sys.argv

    if not QUESTION_BANK_DIR.is_dir():
        print(f"[错误] 找不到 {QUESTION_BANK_DIR}/，请在项目根目录执行")
        sys.exit(1)

    renamed, skipped = [], []
    for json_path in sorted(QUESTION_BANK_DIR.glob("*.json")):
        m = NAME_PATTERN.match(json_path.name)
        if not m:
            continue  # 已是 6 位 / sample / 其他格式，幂等跳过

        six_digit = f"20{m.group('date')}"  # GESP 起始于 2023 年，补 "20" 前缀安全
        target = json_path.with_name(f"{m.group('stem')}-{six_digit}.json")

        if target.exists():
            print(f"  [跳过] {json_path.name} -> {target.name}：目标已存在")
            skipped.append(json_path.name)
            continue
        if not check_content_matches(json_path, six_digit):
            skipped.append(json_path.name)
            continue

        print(f"  [重命名] {json_path.name} -> {target.name}")
        if not dry_run:
            json_path.rename(target)
        renamed.append(f"{json_path.name} -> {target.name}")

    # 重建索引（索引内 source_file 指向旧文件名，必须刷新）
    if renamed and not dry_run:
        from app.core.question_loader import build_question_bank_index
        build_question_bank_index()
        print("[索引] question_bank_index.db 已重建")

    mode = "（dry-run，未实际执行）" if dry_run else ""
    print(f"\n完成{mode}：重命名 {len(renamed)} 个，跳过 {len(skipped)} 个")
    if dry_run:
        print("确认无误后去掉 --dry-run 重新执行")
    elif renamed:
        print("请重启 Streamlit 应用使缓存生效，然后 git add -A 提交（git 会识别为 rename）")


if __name__ == "__main__":
    main()
