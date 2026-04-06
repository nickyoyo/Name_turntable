import streamlit as st
import easyocr
import numpy as np
import cv2
from PIL import Image
import pandas as pd

# 頁面基本設定
st.set_page_config(page_title="玩家名單掃描器", layout="wide")

# 初始化 OCR 模型 (使用快取避免重複載入)
@st.cache_resource
def load_reader():
    # 支援英文與繁體中文，強制使用 CPU 模式 (gpu=False) 以適應雲端環境
    return easyocr.Reader(['en', 'ch_tra'], gpu=False)

try:
    reader = load_reader()
except Exception as e:
    st.error(f"OCR 模型初始化失敗: {e}")

st.title("🛡️ 遊戲玩家 ID 自動提取工具")
st.write("請上傳一張包含玩家名單的截圖，程式將自動分析文字。")

# 側邊欄設定
st.sidebar.header("辨識參數")
min_conf = st.sidebar.slider("信心值門檻", 0.1, 1.0, 0.3, help="數值越高越嚴格，可過濾雜訊。")

# 檔案上傳
uploaded_file = st.file_uploader("選擇圖片檔 (JPG/PNG)", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:
    # 轉換圖片格式
    image = Image.open(uploaded_file)
    img_array = np.array(image)

    col1, col2 = st.columns([1, 1])

    with col1:
        st.image(image, caption="原始截圖", use_container_width=True)

    with col2:
        st.subheader("📝 辨識清單")
        with st.spinner("正在辨識中，請稍候..."):
            try:
                # 影像預處理：轉灰階提高對比
                gray_img = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
                
                # 執行 OCR
                results = reader.readtext(gray_img)

                # 過濾並整理結果
                final_names = []
                for (bbox, text, prob) in results:
                    if prob >= min_conf and len(text) > 1:
                        final_names.append({"玩家名字": text, "信心值": f"{prob:.2%}"})

                if final_names:
                    df = pd.DataFrame(final_names)
                    st.dataframe(df, use_container_width=True)
                    
                    # CSV 下載功能
                    csv_data = df.to_csv(index=False).encode('utf-8-sig')
                    st.download_button(
                        label="📥 下載名單 (CSV)",
                        data=csv_data,
                        file_name="player_list.csv",
                        mime="text/csv"
                    )
                else:
                    st.warning("在此信心值下未偵測到任何文字，請嘗試調低左側門檻。")
            
            except Exception as e:
                st.error(f"辨識過程發生錯誤: {e}")

st.divider()
st.caption("v1.1 | Powered by EasyOCR & Streamlit")