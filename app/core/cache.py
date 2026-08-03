"""Streamlit 缓存数据加载层

核心模块 question_loader.py 不依赖 streamlit，
本模块在它之上套 @st.cache_data，供所有页面共用。

缓存失效策略：
- TTL 300 秒自动过期
- 题库变更（编辑/上传/刷新索引）后调用 st.cache_data.clear() 手动清除
- 练习记录变更（答题/移出错题本）后同样调 st.cache_data.clear()
"""
import streamlit as st
from app.core.question_loader import (
    load_questions_from_folder,
    get_all_exam_types,
    get_all_exam_levels,
    get_all_knowledge_points_with_frequency,
    get_exam_dates,
    get_kp_frequency_from_index,
    get_total_question_count,
    get_questions_by_ids,
)
from app.core.practice_tracker import (
    get_practice_log as _get_practice_log,
    get_mistake_questions as _get_mistake_questions,
    get_mistake_stats as _get_mistake_stats,
    get_answered_question_ids as _get_answered_question_ids,
)


@st.cache_data(ttl=300)
def get_all_questions(folder_path: str = "question_bank"):
    """缓存加载全部题目（5 分钟过期）"""
    return load_questions_from_folder(folder_path)


@st.cache_data(ttl=300)
def get_exam_types(question_bank_dir: str = "question_bank"):
    """缓存获取考试类型"""
    return get_all_exam_types(question_bank_dir)


@st.cache_data(ttl=300)
def get_exam_levels(question_bank_dir: str = "question_bank"):
    """缓存获取级别"""
    return get_all_exam_levels(question_bank_dir)


@st.cache_data(ttl=300)
def get_knowledge_points_with_frequency(question_bank_dir: str = "question_bank"):
    """缓存获取知识点（按频次分组）"""
    return get_all_knowledge_points_with_frequency(question_bank_dir)


@st.cache_data(ttl=300)
def get_exam_dates_cached(
    exam_types: tuple = None,
    exam_levels: tuple = None,
    question_bank_dir: str = "question_bank"
):
    """缓存获取考试日期（参数需为 tuple 以便 hash）"""
    et = list(exam_types) if exam_types else None
    el = list(exam_levels) if exam_levels else None
    return get_exam_dates(exam_types=et, exam_levels=el, question_bank_dir=question_bank_dir)


@st.cache_data(ttl=300)
def get_practice_log_cached(db_path: str = "data/practice_log.db"):
    """缓存加载全部练习记录（答题/移出错题本后自动清缓存）"""
    return _get_practice_log(db_path)


@st.cache_data(ttl=300)
def get_answered_question_ids_cached(db_path: str = "data/practice_log.db"):
    """缓存获取已答 question_id 集合（答题后自动清缓存）"""
    return _get_answered_question_ids(db_path)


@st.cache_data(ttl=300)
def get_mistake_questions_cached(db_path: str = "data/practice_log.db"):
    """缓存加载错题列表（答题/移出错题本后自动清缓存）"""
    return _get_mistake_questions(db_path)


@st.cache_data(ttl=300)
def get_mistake_stats_cached(db_path: str = "data/practice_log.db"):
    """缓存获取错题统计（答题/移出错题本后自动清缓存）"""
    return _get_mistake_stats(db_path)


@st.cache_data(ttl=300)
def get_kp_frequency_cached(question_bank_dir: str = "question_bank"):
    """缓存从索引 DB 获取知识点频次"""
    return get_kp_frequency_from_index(question_bank_dir)


@st.cache_data(ttl=300)
def get_total_question_count_cached(question_bank_dir: str = "question_bank"):
    """缓存从索引 DB 获取题目总数"""
    return get_total_question_count(question_bank_dir)


@st.cache_data(ttl=300)
def get_questions_by_ids_cached(
    question_ids: tuple,
    question_bank_dir: str = "question_bank"
):
    """缓存按 ID 列表批量加载题目（参数需为 tuple 以便 hash）"""
    return get_questions_by_ids(list(question_ids), question_bank_dir)
