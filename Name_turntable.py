import streamlit as st
import easyocr
import numpy as np
import cv2
from PIL import Image
import json
import base64
from io import BytesIO
import gc
import re

# --- 1. 頁面設定 ---
st.set_page_config(page_title="精準抽獎輪盤", layout="wide", page_icon="🎡")

# --- 2. 強化 OCR 修正與過濾 ---
@st.cache_resource
def load_reader():
    return easyocr.Reader(['en', 'ch_tra'], gpu=False)

def is_valid_name(text):
    text = text.strip()
    # 排除常見雜質：長度不符、包含標點、或是純雜亂英數
    if len(text) < 3 or len(text) > 15: return False
    if any(char in text for char in [')', '(', '|', '!', '?', ':', '/', '.', '\\', '+']): return False
    # 排除 OCR 誤認的常見短雜訊 (例如 Ifal, Tachi 等等非完整名稱)
    garbage = ['Ifal', 'Tachi', 'Tarnis', 'Senbe', 'Hacker'] 
    if text in garbage: return False
    return True

def advanced_name_fix(name):
    # 針對圖片中出現的錯誤進行強制修正
    corrections = {
        ")HE729": "JHE729",
        "J/729": "JHE729",
        "alan10002o1": "alan1000201",
        "Tacmiba1": "Tachiba7", # 修正 Tachiba7 的辨識錯誤
        "liiabc": "liiabc",    # 確保 l 與 i 的辨識正確
    }
    return corrections.get(name, name)

# --- 3. 狀態初始化 ---
if 'player_list' not in st.session_state:
    st.session_state.player_list = []
if 'preview_idx' not in st.session_state:
    st.session_state.preview_idx = 0

# --- 4. 側邊欄 ---
with st.sidebar:
    st.title("⚙️ 設定")
    view_mode = st.radio("顯示模式", ["電腦網頁版", "手機行動版"])
    st.divider()
    if st.button("🗑️ 完全清空名單", use_container_width=True):
        st.session_state.player_list = []
        st.rerun()

# --- 5. OCR 核心 (辨識即清空 + 精準去重) ---
def run_ocr_fresh(files):
    if not files: return
    st.session_state.player_list = [] # 點擊後先清空
    reader = load_reader()
    names_set = set()
    
    for file in files:
        img = Image.open(file)
        img.thumbnail((1200, 1200)) # 稍微提高解析度增加準確率
        results = reader.readtext(np.array(img))
        for (_, text, prob) in results:
            text = text.strip()
            # 提高信心門檻至 0.35
            if prob > 0.35 and is_valid_name(text):
                fixed = advanced_name_fix(text)
                names_set.add(fixed)
                
    st.session_state.player_list = sorted(list(names_set))
    gc.collect()

# --- 6. 圖片預覽畫廊 ---
def image_preview_gallery(files):
    num_files = len(files)
    st.session_state.preview_idx = min(st.session_state.preview_idx, num_files - 1)
    
    # 顯示預覽
    img = Image.open(files[st.session_state.preview_idx])
    st.image(img, caption=f"預覽中：第 {st.session_state.preview_idx + 1} 張 / 共 {num_files} 張", use_container_width=True)
    
    col_p, col_n = st.columns(2)
    with col_p:
        if st.button("⬅️ 上一張", use_container_width=True) and st.session_state.preview_idx > 0:
            st.session_state.preview_idx -= 1
            st.rerun()
    with col_n:
        if st.button("下一張 ➡️", use_container_width=True) and st.session_state.preview_idx < num_files - 1:
            st.session_state.preview_idx += 1
            st.rerun()

# --- 7. 轉盤與渲染邏輯 (與先前版本一致) ---
# [此處省略 render_wheel 函數代碼，請延用上一版]