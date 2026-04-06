import streamlit as st
import easyocr
import numpy as np
import cv2
from PIL import Image
import json
import base64
from io import BytesIO

# --- 1. 頁面設定 ---
st.set_page_config(page_title="極速 OCR 抽獎輪盤 (穩定版)", layout="wide", page_icon="🎡")

# --- 2. OCR 核心與圖像穩定邏輯 ---
@st.cache_resource
def load_reader():
    return easyocr.Reader(['en'], gpu=False) # 僅載入英文，速度更快且針對 ID 更準

def advanced_name_fix(name):
    """人工容錯字典：修正常見混淆"""
    corrections = {
        "Iiiabc": "liiabc",
        "liabc": "liiabc",
        "alan10002o1": "alan1000201",
        "GaHid1": "", 
        "T3b": "",
    }
    # 移除 ID 中可能誤判的特殊符號
    name = "".join([c for c in name if c.isalnum() or c in "_-"])
    
    fixed = corrections.get(name, name)
    if "729" in fixed and not fixed.startswith("JHE"):
        return "JHE729"
    return fixed

reader = load_reader()

def robust_image_processing(img_array):
    """
    更穩定的預處理：
    1. 轉灰階
    2. 使用 CLAHE (有限對比自適應直方圖均衡化) 強化文字邊緣
    3. 自動二值化
    """
    # 轉灰階
    gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
    
    # 強化對比 (解決紅底白字對比不足的問題)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    enhanced = clahe.apply(gray)
    
    # 使用抗雜訊二值化
    _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    return binary

def run_ocr(uploaded_file):
    """辨識單張圖片：加入裁切邏輯避開右側雜訊"""
    if not uploaded_file:
        st.warning("請先選取圖片！")
        return
    
    all_new_names = []
    # 只允許英數，排除符號
    allow_chars = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_-'
    
    with st.spinner("深度辨識中..."):
        img = Image.open(uploaded_file)
        
        # 為了準確率，這次不縮太小，維持適中尺寸
        if img.width > 1200:
            w_percent = (1200 / float(img.width))
            h_size = int((float(img.height) * float(w_percent)))
            img = img.resize((1200, h_size), Image.Resampling.LANCZOS)
        
        img_array = np.array(img)
        
        # ---【新增：局部裁切】---
        # 遊戲名單通常在左側，我們只取左邊 50% 的區域，徹底避開右側 UI 雜訊
        h, w, _ = img_array.shape
        roi_img = img_array[:, :int(w * 0.5)]
        
        processed_img = robust_image_processing(roi_img)
        
        # 執行辨識
        results = reader.readtext(processed_img, allowlist=allow_chars)
        
        for (_, text, prob) in results:
            # 遊戲 ID 通常 > 3 字，過短的通常是 UI 碎片
            if len(text) >= 3 and prob > 0.2:
                fixed = advanced_name_fix(text.strip())
                if fixed:
                    all_new_names.append(fixed)
    
    st.session_state.player_list = sorted(list(set(all_new_names)))
    st.success(f"辨識完成！共抓取 {len(st.session_state.player_list)} 名玩家。")

# --- 3. 初始化 Session ---
if 'player_list' not in st.session_state:
    st.session_state.player_list = []

# --- 4. 輪盤 HTML (優化按鈕樣式) ---
def get_wheel_html(size_px="450"):
    display_list = st.session_state.player_list if st.session_state.player_list else ["無名單"]
    json_list = json.dumps(display_list)
    r = int(int(size_px) / 2)
    return f"""
    <div style="display: flex; flex-direction: column; align-items: center; font-family: sans-serif;">
        <div id="container" style="position: relative;">
            <canvas id="wheel" width="{size_px}" height="{size_px}" style="border: 5px solid #333; border-radius: 50%;"></canvas>
            <div style="position: absolute; top: -15px; left: 50%; transform: translateX(-50%); width: 0; height: 0; border-left: 15px solid transparent; border-right: 15px solid transparent; border-top: 25px solid #333; z-index: 10;"></div>
        </div>
        <button id="spinBtn" style="margin-top: 20px; padding: 15px 60px; font-size: 24px; background: #ff4b4b; color: white; border: none; border-radius: 50px; cursor: pointer; font-weight: bold; box-shadow: 0 4px 10px rgba(0,0,0,0.2);">START SPIN</button>
    </div>
    <script>
    const segments = {json_list};
    const canvas = document.getElementById('wheel');
    const ctx = canvas.getContext('2d');
    const spinBtn = document.getElementById('spinBtn');
    let currentAngle = 0;
    const colors = segments.map((_, i) => `hsl(${{(i * 360 / segments.length)}}, 70%, 60%)`);
    function drawWheel() {{
        const r = {r};
        const arc = 2 * Math.PI / segments.length;
        ctx.clearRect(0, 0, {size_px}, {size_px});
        segments.forEach((text, i) => {{
            const angle = currentAngle + i * arc;
            ctx.fillStyle = colors[i];
            ctx.beginPath(); ctx.moveTo(r, r); ctx.arc(r, r, r, angle, angle + arc); ctx.fill();
            ctx.save(); ctx.fillStyle = "white"; ctx.translate(r, r); ctx.rotate(angle + arc / 2);
            ctx.textAlign = "right"; ctx.font = "bold 14px Arial"; ctx.fillText(text, r - 20, 7); ctx.restore();
        }});
    }}
    spinBtn.addEventListener('click', () => {{
        if (segments[0] === "無名單") return;
        spinBtn.disabled = true;
        const display = window.parent.document.querySelector("#winner_box");
        if(display) display.style.display = "none";
        const duration = 5000;
        const startTime = Date.now();
        const totalRotation = (8 * 360) + Math.random() * 360;
        const startAngle = currentAngle;
        function animate() {{
            const elapsed = Date.now() - startTime;
            const progress = elapsed / duration;
            if (progress < 1) {{
                const easeOut = 1 - Math.pow(1 - progress, 3);
                currentAngle = startAngle + (easeOut * totalRotation * Math.PI / 180);
                drawWheel();
                requestAnimationFrame(animate);
            }} else {{
                spinBtn.disabled = false;
                const degrees = (currentAngle * 180 / Math.PI) % 360;
                const sliceSize = 360 / segments.length;
                const index = Math.floor((360 - (degrees + 90) % 360) / sliceSize) % segments.length;
                const winner = segments[index >= 0 ? index : index + segments.length];
                if(display) {{
                    display.innerHTML = "恭喜中獎：<span style='color:red;'>" + winner + "</span>";
                    display.style.display = "block";
                }}
            }}
        }}
        animate();
    }});
    drawWheel();
    </script>
    """

# --- 5. 介面佈局 ---
st.sidebar.title("抽獎系統設定")
mode = st.sidebar.radio("切換版面", ["電腦版", "手機版"])

if mode == "電腦版":
    c1, c2, c3 = st.columns([1.5, 2, 1.2])
    with c1:
        st.subheader("📸 上傳圖片")
        file = st.file_uploader("請上傳遊戲截圖", type=["png", "jpg", "jpeg"])
        if file:
            st.image(file, caption="預覽圖片", use_container_width=True)
            if st.button("🔍 辨識並更新名單", type="primary", use_container_width=True):
                run_ocr(file)
                st.rerun()
    with c2:
        st.subheader("🎡 幸運轉盤")
        st.components.v1.html(get_wheel_html("400"), height=550)
        st.markdown('<div id="winner_box" style="display:none; background:#fff3cd; padding:15px; border:2px solid #ffeeba; border-radius:10px; text-align:center; font-size:24px; font-weight:bold;"></div>', unsafe_allow_html=True)
    with c3:
        st.subheader("📝 名單")
        st.write(f"總計: {len(st.session_state.player_list)} 人")
        new_list = st.text_area("手動調整", value="\n".join(st.session_state.player_list), height=400)
        if st.button("🔄 同步修改"):
            st.session_state.player_list = [n.strip() for n in new_list.split("\n") if n.strip()]
            st.rerun()
else:
    # 手機版邏輯 (簡化)
    st.subheader("📸 上傳與辨識")
    file = st.file_uploader("選取圖片", type=["png", "jpg", "jpeg"], key="m_up")
    if file and st.button("🔍 開始辨識", type="primary"):
        run_ocr(file)
    st.components.v1.html(get_wheel_html("320"), height=450)
    st.markdown('<div id="winner_box" style="display:none; background:#fff3cd; padding:10px; border:2px solid #ffeeba; border-radius:10px; text-align:center; font-size:20px; font-weight:bold;"></div>', unsafe_allow_html=True)
    with st.expander("📝 編輯名單"):
        st.text_area("名單內容", value="\n".join(st.session_state.player_list), height=200)