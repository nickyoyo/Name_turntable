import streamlit as st
import easyocr
import numpy as np
import cv2
from PIL import Image
import random
import time

# 頁面設定
st.set_page_config(page_title="遊戲抽獎轉盤 Pro", layout="wide", page_icon="🎡")

# --- 1. 定義修正邏輯 (手動校正表) ---
def advanced_name_fix(name):
    # 針對圖片中容易看錯的特定字串進行強制替換
    corrections = {
        "J|[729": "JHE729",
        "alan10002o1": "alan1000201",
        "BobCC": "Bobcc",
        "J/729": "JHE729",
        "Iiiabc": "liiabc"
    }
    return corrections.get(name, name)

# --- 2. 初始化 OCR ---
@st.cache_resource
def load_reader():
    # gpu=False 確保在 Streamlit Cloud 穩定執行
    return easyocr.Reader(['en', 'ch_tra'], gpu=False)

reader = load_reader()

st.title("🎡 玩家名單掃描 & 抽獎工具")
st.write("上傳截圖後，系統會自動修正已知錯誤並生成抽獎名單。")

# Session State 初始化
if 'player_list' not in st.session_state:
    st.session_state.player_list = []

# --- 3. 檔案上傳與辨識 ---
uploaded_file = st.file_uploader("步驟 1：上傳名單截圖", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:
    col1, col2 = st.columns([1, 1])
    img = Image.open(uploaded_file)
    
    with col1:
        st.image(img, caption="上傳的圖片", use_container_width=True)

    if st.button("🔍 開始掃描並修正名單"):
        with st.spinner("辨識中..."):
            img_array = np.array(img)
            # 轉灰階提升辨識度
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            # 限制字元集 (Allowlist) 可以有效減少雜訊字元出現
            results = reader.readtext(gray, allowlist='0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ-|[]/')
            
            scanned_names = []
            for (bbox, text, prob) in results:
                if len(text) > 1 and prob > 0.2:
                    # 執行手動校正表
                    fixed_name = advanced_name_fix(text)
                    scanned_names.append(fixed_name)
            
            st.session_state.player_list = sorted(list(set(scanned_names))) # 去重並排序

        if st.session_state.player_list:
            st.success(f"成功辨識！共計 {len(st.session_state.player_list)} 位玩家。")
        else:
            st.error("未能辨識到名字，請更換截圖或調整亮度。")

# --- 4. 抽獎功能區 ---
if st.session_state.player_list:
    st.divider()
    st.subheader("步驟 2：確認名單與抽獎")
    
    # 讓使用者可以做最後的手動微調
    edited_list_str = st.text_area("確認抽獎名單 (如有錯誤請在此手動修改)", 
                                   value="\n".join(st.session_state.player_list), 
                                   height=200)
    final_list = [n.strip() for n in edited_list_str.split("\n") if n.strip()]

    col_btn, col_result = st.columns([1, 2])
    
    with col_btn:
        draw_clicked = st.button("🎰 開始抽獎！", type="primary", use_container_width=True)

    if draw_clicked:
        if final_list:
            placeholder = st.empty()
            # 轉盤滾動特效
            for _ in range(20):
                temp = random.choice(final_list)
                placeholder.markdown(f"### 🎲 正在轉動... `{temp}`")
                time.sleep(0.08)
            
            winner = random.choice(final_list)
            placeholder.markdown(f"## 🎊 中獎者：**{winner}** 🎊")
            st.balloons()
        else:
            st.warning("請輸入至少一個名字。")

st.markdown("---")
st.caption("提示：若 OCR 持續辨識錯誤，可將該錯誤字串加入程式碼中的 `corrections` 字典中。")