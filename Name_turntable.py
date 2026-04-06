import streamlit as st
import easyocr
import numpy as np
import cv2
from PIL import Image

st.set_page_config(page_title="專業遊戲名單 OCR", layout="wide")

# 初始化 OCR
@st.cache_resource
def get_reader():
    return easyocr.Reader(['en', 'ch_tra'])

reader = get_reader()

st.title("🛡️ 遊戲玩家 ID 自動提取工具")
st.write("上傳圖片後，程式會自動強化對比並提取文字。")

col1, col2 = st.columns(2)

uploaded_file = st.file_uploader("上傳遊戲截圖", type=["png", "jpg", "jpeg"])

if uploaded_file:
    # 讀取圖片
    file_bytes = np.asarray(bytearray(uploaded_file.read()), dtype=np.uint8)
    img = cv2.imdecode(file_bytes, 1)
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    with col1:
        st.image(img_rgb, caption="原始圖片", use_container_width=True)

    with st.spinner("優化影像並辨識中..."):
        # --- 影像預處理 (提升辨識率的關鍵) ---
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) # 轉灰階
        # 增加對比度 (讓文字更白，背景更黑)
        alpha = 1.5 
        beta = 0    
        enhanced = cv2.convertScaleAbs(gray, alpha=alpha, beta=beta)
        
        # 執行辨識
        results = reader.readtext(enhanced)

    with col2:
        st.subheader("📝 辨識結果")
        player_list = []
        for (bbox, text, prob) in results:
            # 過濾掉太短或信心值過低的結果
            if len(text) > 2 and prob > 0.2:
                player_list.append(text)
                st.success(f"**{text}** (信心值: {prob:.2f})")
        
        if player_list:
            final_text = "\n".join(player_list)
            st.download_button("下載純文字名單", final_text, file_name="players.txt")
        else:
            st.error("找不到文字，請嘗試調整截圖亮度。")