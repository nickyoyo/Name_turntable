import streamlit as st
import easyocr
import numpy as np
import cv2
from PIL import Image
import random
import time

# 頁面設定
st.set_page_config(page_title="遊戲抽獎轉盤", layout="wide", page_icon="🎡")

# --- CSS 美化輪盤效果 ---
st.markdown("""
    <style>
    .winner-box {
        padding: 20px;
        border-radius: 10px;
        background-color: #f0f2f6;
        border: 2px solid #ff4b4b;
        text-align: center;
        font-size: 30px;
        font-weight: bold;
        color: #ff4b4b;
    }
    </style>
    """, unsafe_allow_html=True)

# 1. 初始化 OCR (強制 CPU 模式)
@st.cache_resource
def load_reader():
    return easyocr.Reader(['en', 'ch_tra'], gpu=False)

reader = load_reader()

st.title("🎡 玩家名單掃描 & 幸運抽獎機")
st.write("上傳截圖自動抓取玩家，並直接進行隨機抽獎！")

# 2. 檔案上傳
uploaded_file = st.file_uploader("步驟 1：上傳名單截圖", type=["jpg", "jpeg", "png"])

# 初始化 Session State 用來儲存名單，避免網頁刷新就消失
if 'player_list' not in st.session_state:
    st.session_state.player_list = []

if uploaded_file is not None:
    col1, col2 = st.columns([1, 1])
    
    img = Image.open(uploaded_file)
    with col1:
        st.image(img, caption="上傳的圖片", use_container_width=True)

    # 辨識邏輯
    if st.button("🔍 開始掃描名單"):
        with st.spinner("正在辨識中..."):
            img_array = np.array(img)
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            results = reader.readtext(gray)
            
            # 過濾名字
            names = [text for (bbox, text, prob) in results if len(text) > 1 and prob > 0.3]
            st.session_state.player_list = list(set(names)) # 去重
            
        if st.session_state.player_list:
            st.success(f"成功掃描到 {len(st.session_state.player_list)} 位玩家！")
        else:
            st.error("掃描不到名字，請確認圖片是否清晰。")

# 3. 抽獎/轉盤功能區
if st.session_state.player_list:
    st.divider()
    st.subheader("步驟 2：開始抽獎")
    
    # 顯示目前名單（可以手動編輯）
    edited_list = st.text_area("目前的抽獎名單 (每行一個名字)", value="\n".join(st.session_state.player_list), height=150)
    final_list = [n.strip() for n in edited_list.split("\n") if n.strip()]

    if st.button("🎰 點我抽獎！", type="primary"):
        if len(final_list) > 0:
            # 模擬轉盤動畫
            placeholder = st.empty()
            for i in range(15): # 模擬滾動 15 次
                temp_winner = random.choice(final_list)
                placeholder.markdown(f"<div class='winner-box'>🎲 轉動中... {temp_winner}</div>", unsafe_allow_html=True)
                time.sleep(0.1)
            
            # 最終中獎者
            winner = random.choice(final_list)
            placeholder.markdown(f"<div class='winner-box'>🎊 恭喜得獎者：{winner} 🎊</div>", unsafe_allow_html=True)
            st.balloons() # 噴彩帶特效
        else:
            st.warning("名單是空的！")

# 底部說明
st.info("💡 提示：你可以手動修改上面的文字區域，增減參與抽獎的人員。")