"""Streamlit 缓存数据加载层

核心模块 question_loader.py 不依赖 streamlit，
本模块在它之上套 @st.cache_data，供所有页面共用。

缓存失效策略：
- TTL 300 秒自动过期
- 题库变更（编辑/上传/刷新索引）后调用 st.cache_data.clear() 手动清除
"""
import streamlit as st
from app.core.question_loader import (
    load_questions_from_folder,
    get_all_exam_types,
    get_all_exam_levels,
    get_all_knowledge_points_with_frequency,
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
