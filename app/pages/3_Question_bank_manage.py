"""题库管理页面"""
import sys
import sqlite3
import json
import logging
from contextlib import closing
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import streamlit as st

logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="题库管理 - C++ 做题助手",
    page_icon="📚",
    layout="wide"
)

from app.core.question_loader import (
    load_questions,
    get_knowledge_point_frequency,
    build_question_bank_index,
    QUESTION_BANK_INDEX_PATH,
    search_questions,
    update_question_in_file,
    get_question_by_id_from_all,
)
from app.core.cache import get_all_questions
from app.core.pdf_parser import (
    pdf_to_markdown,
    parse_pdf_metadata,
    validate_metadata,
    check_duplicate,
    generate_filename,
    parse_pdf_questions,
    validate_question,
)

# 题库路径
QUESTION_BANK_DIR = "question_bank"
PAST_EXAM_DIR = "past_exam"
TEMP_DIR = "temp"


def main():
    """题库管理页面"""
    st.title("📚 题库管理")

    # ---------- 1. 题库概览 ----------
    st.header("题库概览")

    col_refresh, col1, col2 = st.columns([1, 1, 1])
    with col_refresh:
        if st.button("刷新题库索引"):
            with st.spinner("正在构建索引..."):
                build_question_bank_index()
                st.cache_data.clear()
            st.success("索引已刷新")
            st.rerun()

    all_questions = get_all_questions(QUESTION_BANK_DIR)

    # 统计知识点（兼容新旧格式）
    all_kps = set()
    for q in all_questions:
        kps = q.get("knowledge_points", [])
        all_kps.update(kps)
    col1.metric("总题目数", len(all_questions))
    col2.metric("知识点数量", len(all_kps))

    # 展示索引表概览
    try:
        if Path(QUESTION_BANK_INDEX_PATH).exists():
            with closing(sqlite3.connect(QUESTION_BANK_INDEX_PATH)) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT DISTINCT exam_type, exam_level, exam_date, source_file
                    FROM question_index
                """)
                rows = cursor.fetchall()

            index_data = [
                {"考试类型": r[0], "级别": r[1], "日期": r[2], "源文件": r[3]}
                for r in rows
            ]
            if index_data:
                st.dataframe(index_data, width='stretch', hide_index=True)
            else:
                st.info("索引为空，请点击刷新按钮构建索引。")
        else:
            st.warning("索引文件不存在，请点击刷新按钮构建索引。")
    except Exception as e:
        st.error(f"读取索引失败: {e}")

    # ---------- 2. 题目列表 ----------
    st.header("题目列表")
    df_data = []
    for q in all_questions:
        kps = q.get("knowledge_points", [])
        knowledge_point_display = ", ".join(kps) if kps else "未分类"
        question_text = q.get("question", "")
        display_question = question_text[:50] + "..." if len(question_text) > 50 else question_text
        df_data.append({
            "ID": q.get("id", ""),
            "知识点": knowledge_point_display,
            "类型": "选择题" if q.get("type") == "single_choice" else "判断题",
            "题目": display_question
        })
    if df_data:
        st.dataframe(df_data, width='stretch', hide_index=True)
    else:
        st.warning("题库为空")

    # ---------- 3. 单题编辑 ----------
    st.divider()
    st.header("🔍 单题编辑")
    st.caption("替代原有全量 JSON 编辑：搜索或输入 ID，只编辑选中题目，保存时仅更新该题。")

    # 初始化 session state
    if "edit_results" not in st.session_state:
        st.session_state.edit_results = []
        st.session_state.edit_sel_idx = 0
        st.session_state.edit_source_files = []

    # 方式1：关键字搜索
    sc1, sc2 = st.columns([4, 1])
    with sc1:
        search_kw = st.text_input("搜索（ID 或题目内容关键字）", key="edit_search_kw")
    with sc2:
        st.write("")  # 占位对齐
        st.write("")
        if st.button("🔍 搜索", width='stretch'):
            if search_kw.strip():
                results = search_questions(all_questions, search_kw.strip())
                st.session_state.edit_results = results
                st.session_state.edit_sel_idx = 0
                st.session_state.edit_source_files = []  # 搜索路径无 source_file
                if not results:
                    st.warning("未找到匹配的题目，请尝试其他关键字")
            else:
                st.session_state.edit_results = []
            st.rerun()

    # 方式2：直接输入 ID
    ic1, ic2 = st.columns([4, 1])
    with ic1:
        load_id = st.text_input("或直接输入题目 ID 加载", key="edit_load_id")
    with ic2:
        st.write("")
        st.write("")
        if st.button("📂 加载", width='stretch'):
            q, path = get_question_by_id_from_all(load_id.strip())
            if q:
                st.session_state.edit_results = [q]
                st.session_state.edit_sel_idx = 0
                st.session_state.edit_source_files = [path]
            else:
                st.warning(f"未找到 ID 为 {load_id.strip()} 的题目")
            st.rerun()

    results = st.session_state.edit_results
    if results:
        st.write(f"当前结果：{len(results)} 道题")

        # 上一题 / 下一题
        nav1, nav2, nav3 = st.columns([1, 1, 4])
        with nav1:
            if st.button("◀ 上一题") and st.session_state.edit_sel_idx > 0:
                st.session_state.edit_sel_idx -= 1
                st.rerun()
        with nav2:
            if st.button("下一题 ▶") and st.session_state.edit_sel_idx < len(results) - 1:
                st.session_state.edit_sel_idx += 1
                st.rerun()
        with nav3:
            st.caption(f"第 {st.session_state.edit_sel_idx + 1} / {len(results)} 题")

        sel_idx = st.session_state.edit_sel_idx
        current_q = results[sel_idx]

        # 选择框
        sel = st.selectbox(
            "选择题目",
            range(len(results)),
            index=sel_idx,
            format_func=lambda i: f"{results[i].get('id', '')}: {results[i].get('question', '')[:40]}",
            key="edit_select"
        )
        if sel != sel_idx:
            st.session_state.edit_sel_idx = sel
            st.rerun()
            current_q = results[sel]

        # JSON 编辑区（key 绑定 id，切换题目时重置）
        edit_key = f"edit_json_{current_q.get('id', 'new')}"
        default_json = json.dumps(current_q, ensure_ascii=False, indent=2)
        edited = st.text_area(
            "题目 JSON（可编辑）",
            value=default_json,
            height=400,
            key=edit_key,
            help="修改后点击保存，仅更新此题"
        )

        bc1, bc2 = st.columns(2)
        with bc1:
            if st.button("💾 保存修改", type="primary"):
                # 解析编辑后的 JSON
                try:
                    updated_q = json.loads(edited)
                except json.JSONDecodeError as e:
                    st.error(f"❌ JSON 格式错误: {e}")
                else:
                    # 优先用加载时缓存的源文件路径，避免重复查索引
                    source_files = st.session_state.get("edit_source_files", [])
                    sel_idx = st.session_state.edit_sel_idx
                    file_path = source_files[sel_idx] if sel_idx < len(source_files) else None

                    # ID 被修改或搜索路径加载时，fallback 查索引
                    if not file_path or updated_q.get("id") != current_q.get("id"):
                        _q, file_path = get_question_by_id_from_all(updated_q.get("id", ""))

                    if not file_path:
                        st.error("无法定位题目所在文件（可能 ID 已被修改且原 ID 不存在）")
                    else:
                        ok, err = update_question_in_file(file_path, updated_q)
                        if ok:
                            st.cache_data.clear()
                            st.success(f"✅ 已保存到 {file_path}，索引已刷新")
                            # 刷新结果列表中的对应题
                            st.session_state.edit_results[st.session_state.edit_sel_idx] = updated_q
                        else:
                            st.error(f"❌ {err}")
        with bc2:
            if st.button("🔄 重新加载"):
                st.rerun()
    else:
        st.info("请在上方搜索关键字或输入 ID 加载题目")

    # ---------- 4. 批量 PDF 上传 ----------
    st.divider()
    st.header("📤 批量 PDF 上传")
    st.caption("上传考试 PDF，自动解析元数据与题目，生成 JSON 入库。最多建议 20 个文件。")

    if "upload_meta" not in st.session_state:
        st.session_state.upload_meta = []  # list[dict]: orig, type, level, date, status, stem, markdown, temp_path
        st.session_state.upload_results = {}  # stem -> list[dict] 解析后的题目
        st.session_state.upload_report = None

    uploaded = st.file_uploader(
        "选择 PDF 文件（可多选）",
        accept_multiple_files=True,
        type=["pdf"],
        key="upload_uploader"
    )

    uc1, uc2 = st.columns(2)
    with uc1:
        if st.button("🔍 解析元数据", type="primary"):
            if not uploaded:
                st.warning("请先选择 PDF 文件")
            else:
                logger.info("开始解析元数据...")

                Path(TEMP_DIR).mkdir(exist_ok=True)
                meta_list = []

                for f in uploaded:
                    logger.info("正在处理文件: %s", f.name)

                    # 保存到 temp
                    temp_path = Path(TEMP_DIR) / f.name
                    with open(temp_path, "wb") as out:
                        out.write(f.getbuffer() if hasattr(f, "getbuffer") else f.read())

                    try:
                        md = pdf_to_markdown(temp_path)
                        logger.debug("PDF 转 Markdown 成功，前 100 字符: %s", md[:100])
                    except Exception as e:
                        logger.warning("PDF 转 Markdown 失败: %s", e)
                        meta_list.append({
                            "orig": f.name, "type": "", "level": "", "date": "",
                            "status": "❌ 解析失败", "stem": "", "markdown": "", "temp_path": str(temp_path)
                        })
                        continue

                    try:
                        md_meta = parse_pdf_metadata(md)
                        logger.debug("parse_pdf_metadata 返回: %s", md_meta)
                    except Exception as e:
                        logger.warning("parse_pdf_metadata 抛出异常: %s", e)
                        md_meta = {}

                    t, l, d = md_meta.get("type", ""), md_meta.get("level", ""), md_meta.get("date", "")
                    ok, err = validate_metadata(t, l, d)
                    stem = generate_filename(t, l, d) if ok else ""
                    
                    if not ok:
                        status = f"❌ {err}"
                    elif check_duplicate(t, l, d):
                        status = "⚠️ 已存在"
                    else:
                        status = "✅ 新题"
                        
                    meta_list.append({
                        "orig": f.name, "type": t, "level": l, "date": d,
                        "status": status, "stem": stem, "markdown": md, "temp_path": str(temp_path)
                    })

                st.session_state.upload_meta = meta_list
                st.session_state.upload_results = {}
                st.session_state.upload_report = None
                st.rerun()
    with uc2:
        if st.button("🗑️ 清空", key="clear_pdf_upload"):
            st.session_state.upload_meta = []
            st.session_state.upload_results = {}
            st.session_state.upload_report = None
            st.rerun()

    meta = st.session_state.upload_meta
    # 显示调试信息
    if "debug_meta" in st.session_state:
        st.warning(st.session_state["debug_meta"])
    if meta:
        st.subheader("元数据解析结果（可编辑）")
        # 表头
        hc = st.columns([3, 1.5, 1, 1.5, 2])
        for col, label in zip(hc, ["原文件名", "Type", "Level", "Date", "状态"]):
            col.write(f"**{label}**")
        # 可编辑行
        for i, m in enumerate(meta):
            rc = st.columns([3, 1.5, 1, 1.5, 2])
            rc[0].write(m["orig"])
            m["type"] = rc[1].text_input("type", m["type"], key=f"um_t_{i}", label_visibility="collapsed")
            m["level"] = rc[2].text_input("level", m["level"], key=f"um_l_{i}", label_visibility="collapsed")
            m["date"] = rc[3].text_input("date", m["date"], key=f"um_d_{i}", label_visibility="collapsed")
            # 实时重算状态
            ok, err = validate_metadata(m["type"], m["level"], m["date"])
            if ok:
                m["stem"] = generate_filename(m["type"], m["level"], m["date"])
                m["status"] = "⚠️ 已存在" if check_duplicate(m["type"], m["level"], m["date"]) else "✅ 新题"
            else:
                m["stem"] = ""
                m["status"] = f"❌ {err}"
            rc[4].write(m["status"])

    # ========== 解析题目 ==========
    if st.button("✅ 确认无误，开始解析题目", type="primary"):
        results = {}
        new_files = [m for m in meta if m["status"] == "✅ 新题"]
        progress = st.progress(0.0)
        
        logger.info("开始解析题目，待解析文件数: %d", len(new_files))

        for i, m in enumerate(new_files):
            progress.progress((i) / max(len(new_files), 1), text=f"正在解析 {i+1}/{len(new_files)}：{m['orig']}")
            logger.info("[%d] 正在处理: %s", i + 1, m["orig"])

            try:
                qs = parse_pdf_questions(m["markdown"], {
                    "type": m["type"],
                    "level": m["level"],
                    "date": m["date"]
                })

                if qs:
                    logger.info("[%d] 解析成功，题目数: %d", i + 1, len(qs))
                    results[m["stem"]] = qs
                    m["status"] = "✅ 已解析"
                else:
                    logger.warning("[%d] 解析失败：返回为空", i + 1)
                    m["status"] = "❌ 解析失败"

            except Exception as e:
                logger.warning("[%d] 解析异常: %s", i + 1, e)
                m["status"] = f"❌ 异常"

        logger.info("解析流程结束")
        
        progress.progress(1.0, text="解析完成")
        st.session_state.upload_results = results
        st.rerun()

    # ========== JSON 预览 + 保存 ==========
    if st.session_state.upload_results:
        st.subheader("JSON 预览（新题）")
        preview = []
        for stem, qs in st.session_state.upload_results.items():
            preview.extend(qs)
        st.text_area(
            "预览",
            value=json.dumps(preview, ensure_ascii=False, indent=2),
            height=300,
            key="upload_preview"
        )

        if st.button("💾 保存所有新题", type="primary"):
            Path(PAST_EXAM_DIR).mkdir(exist_ok=True)
            Path(QUESTION_BANK_DIR).mkdir(exist_ok=True)
            saved, skipped, failed = 0, 0, 0
            for m in meta:
                if m["status"] != "✅ 已解析":
                    if m["status"] == "⚠️ 已存在":
                        skipped += 1
                    else:
                        failed += 1
                    continue
                stem = m["stem"]
                qs = st.session_state.upload_results.get(stem, [])
                try:
                    with open(Path(QUESTION_BANK_DIR) / f"{stem}.json", "w", encoding="utf-8") as f:
                        json.dump(qs, f, ensure_ascii=False, indent=2)
                    src = Path(m["temp_path"])
                    dst = Path(PAST_EXAM_DIR) / f"{stem}.pdf"
                    src.replace(dst)
                    saved += 1
                except Exception as e:
                    st.error(f"保存 {m['orig']} 失败: {e}")
                    failed += 1
            try:
                build_question_bank_index()
                st.cache_data.clear()
            except Exception as e:
                st.warning(f"索引刷新失败，请手动点击刷新: {e}")
            st.session_state.upload_report = {
                "saved": saved, "skipped": skipped, "failed": failed
            }
            st.session_state.upload_results = {}
            st.rerun()

    # ========== 处理报告 ==========
    if st.session_state.upload_report:
        r = st.session_state.upload_report
        st.info(f"处理报告：✅ 成功 {r['saved']} 个，⚠️ 跳过 {r['skipped']} 个，❌ 失败 {r['failed']} 个")

    # ---------- 5. 直接上传 JSON ----------
    st.divider()
    st.header("📥 直接上传 JSON")
    st.caption("绕过 PDF/LLM，直接上传已编辑好的题目 JSON 文件入库。文件名建议 {type}-{level}-{date}.json。")

    if "json_upload" not in st.session_state:
        st.session_state.json_upload = {}  # stem -> {"valid": [...], "invalid": int, "errors": [...]}

    json_files = st.file_uploader(
        "选择 JSON 文件（可多选）",
        accept_multiple_files=True,
        type=["json"],
        key="json_uploader"
    )

    jc1, jc2 = st.columns(2)
    with jc1:
        if st.button("🔍 校验并预览", type="primary"):
            if not json_files:
                st.warning("请先选择 JSON 文件")
            else:
                parsed = {}
                for f in json_files:
                    stem = Path(f.name).stem
                    try:
                        data = json.loads(f.getvalue().decode("utf-8"))
                    except Exception as e:
                        parsed[stem] = {"valid": [], "invalid": 0, "errors": [f"读取/JSON 错误: {e}"]}
                        continue
                    if not isinstance(data, list):
                        parsed[stem] = {"valid": [], "invalid": 0, "errors": ["顶层必须是数组"]}
                        continue
                    valid, errors = [], []
                    for i, q in enumerate(data):
                        if not isinstance(q, dict):
                            errors.append(f"第 {i+1} 题: 不是对象")
                            continue
                        ok, err = validate_question(q)
                        if ok:
                            valid.append(q)
                        else:
                            errors.append(f"第 {i+1} 题 ({q.get('id','?')}): {err}")
                    parsed[stem] = {"valid": valid, "invalid": len(errors), "errors": errors}
                st.session_state.json_upload = parsed
                st.rerun()
    with jc2:
        if st.button("🗑️ 清空", key="clear_json_upload"):
            st.session_state.json_upload = {}
            st.rerun()

    if st.session_state.json_upload:
        st.subheader("校验结果")
        rows = []
        for stem, info in st.session_state.json_upload.items():
            rows.append({
                "文件": f"{stem}.json",
                "有效题数": len(info["valid"]),
                "无效题数": info["invalid"],
                "状态": "✅ 可入库" if info["valid"] and not info["invalid"] else (
                    "⚠️ 部分无效" if info["valid"] else "❌ 全部无效"
                )
            })
        st.dataframe(rows, width='stretch', hide_index=True)

        # 错误详情
        all_errors = []
        for stem, info in st.session_state.json_upload.items():
            for e in info["errors"]:
                all_errors.append(f"{stem}: {e}")
        if all_errors:
            with st.expander(f"错误详情（{len(all_errors)}）"):
                for e in all_errors:
                    st.write(e)

        # 预览有效题
        valid_preview = []
        for info in st.session_state.json_upload.values():
            valid_preview.extend(info["valid"])
        if valid_preview:
            with st.expander(f"有效题预览（{len(valid_preview)}）"):
                st.json(valid_preview[:5])

            if st.button("💾 保存入库", type="primary"):
                Path(QUESTION_BANK_DIR).mkdir(exist_ok=True)
                saved, failed = 0, 0
                for stem, info in st.session_state.json_upload.items():
                    if not info["valid"]:
                        continue
                    try:
                        with open(Path(QUESTION_BANK_DIR) / f"{stem}.json", "w", encoding="utf-8") as out:
                            json.dump(info["valid"], out, ensure_ascii=False, indent=2)
                        saved += 1
                    except Exception as e:
                        st.error(f"保存 {stem}.json 失败: {e}")
                        failed += 1
                try:
                    build_question_bank_index()
                    st.cache_data.clear()
                except Exception as e:
                    st.warning(f"索引刷新失败，请手动刷新: {e}")
                st.success(f"✅ 入库 {saved} 个文件，失败 {failed} 个，索引已刷新")
                st.session_state.json_upload = {}
                st.rerun()


if __name__ == "__main__":
    main()
