import streamlit as st
import easyocr
import numpy as np
import cv2
from PIL import Image
import json
import base64
from io import BytesIO

# --- 1. 頁面設定 ---
st.set_page_config(page_title="極速 OCR 抽獎輪盤 (雙重掃描版)", layout="wide", page_icon="🎡")

# --- 2. OCR 核心與多重掃描邏輯 ---
@st.cache_resource
def load_reader():
    # 專門載入英文模型，減少辨識錯誤率
    return easyocr.Reader(['en'], gpu=False)

def advanced_name_fix(name):
    """人工容錯字典：修正 ID 與過濾雜訊"""
    # 移除 ID 以外的符號
    name = "".join([c for c in name if c.isalnum() or c in "_-"])
    
    corrections = {
        "Iiiabc": "liiabc",
        "liabc": "liiabc",
        "alan10002o1": "alan1000201",
        "GaHid1": "", 
        "T3b": "",
    }
    
    fixed = corrections.get(name, name)
    # 處理 JHE729 常見辨識碎塊
    if "729" in fixed and not fixed.startswith("JHE"):
        return "JHE729"
    return fixed

reader = load_reader()

def get_processed_images(img_array):
    """生成兩種不同強化程度的圖片，提高辨識成功率"""
    gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
    
    # 模式 A: 輕度強化 (適合原本就清晰的圖)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    enhanced = clahe.apply(gray)
    
    # 模式 B: 強力二值化 (適合紅底白字對比極差的圖)
    _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    return [enhanced, binary]

def run_ocr(uploaded_file):
    """雙重掃描辨識：確保兩張不同品質的圖都能成功"""
    if not uploaded_file:
        st.warning("請先選取圖片！")
        return
    
    all_raw_results = []
    allow_chars = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_-'
    
    with st.spinner("深度辨識中 (套用雙重掃描策略)..."):
        img = Image.open(uploaded_file)
        
        # 尺寸控制：1000px 是速度與準確的平衡點
        if img.width > 1000:
            w_percent = (1000 / float(img.width))
            h_size = int((float(img.height) * float(w_percent)))
            img = img.resize((1000, h_size), Image.Resampling.LANCZOS)
        
        img_array = np.array(img)
        
        # 裁切左側 55%：排除右側 UI 雜訊 (GaHid1 等)
        h, w, _ = img_array.shape
        roi_img = img_array[:, :int(w * 0.55)]
        
        # 獲取不同強化後的圖片列表
        processed_list = get_processed_images(roi_img)
        
        for p_img in processed_list:
            # 執行 OCR
            results = reader.readtext(p_img, allowlist=allow_chars, mag_ratio=1.0)
            for (_, text, prob) in results:
                if len(text) >= 3 and prob > 0.15:
                    fixed = advanced_name_fix(text.strip())
                    if fixed:
                        all_raw_results.append(fixed)
    
    # 整合兩次掃描結果並去重
    st.session_state.player_list = sorted(list(set(all_raw_results)))
    st.success(f"辨識完成！目前共 {len(st.session_state.player_list)} 人進入轉盤。")

# --- 3. 初始化 Session ---
if 'player_list' not in st.session_state:
    st.session_state.player_list = []

# --- 4. 輪盤 HTML ---
def get_wheel_html(size_px="450"):
    display_list = st.session_state.player_list if st.session_state.player_list else ["無名單"]
    json_list = json.dumps(display_list)
    r = int(int(size_px) / 2)
    return f"""
    <div style="display: flex; flex-direction: column; align-items: center; font-family: sans-serif;">
        <div id="container" style="position: relative;">
            <canvas id="wheel" width="{size_px}" height="{size_px}" style="border: 5px solid #333; border-radius: 50%; box-shadow: 0 4px 10px rgba(0,0,0,0.2);"></canvas>
            <div style="position: absolute; top: -15px; left: 50%; transform: translateX(-50%); width: 0; height: 0; border-left: 15px solid transparent; border-right: 15px solid transparent; border-top: 25px solid #333; z-index: 10;"></div>
        </div>
        <button id="spinBtn" style="margin-top: 20px; padding: 12px 50px; font-size: 22px; background: #ff4b4b; color: white; border: none; border-radius: 50px; cursor: pointer; font-weight: bold;">SPIN 抽獎</button>
    </div>
    <script>
    const segments = {json_list};
    const canvas = document.getElementById('wheel');
    const ctx = canvas.getContext('2d');
    const spinBtn = document.getElementById('spinBtn');
    let currentAngle = 0;
    const colors = segments.map((_, i) => `hsl(${{(i * 360 / segments.length)}}, 75%, 60%)`);
    function drawWheel() {{
        const r = {r};
        const arc = 2 * Math.PI / segments.length;
        ctx.clearRect(0, 0, {size_px}, {size_px});
        segments.forEach((text, i) => {{
            const angle = currentAngle + i * arc;
            ctx.fillStyle = colors[i];
            ctx.beginPath(); ctx.moveTo(r, r); ctx.arc(r, r, r, angle, angle + arc); ctx.fill();
            ctx.strokeStyle = "white"; ctx.lineWidth = 1; ctx.stroke();
            ctx.save(); ctx.fillStyle = "white"; ctx.translate(r, r); ctx.rotate(angle + arc / 2);
            ctx.textAlign = "right"; ctx.font = "bold 13px Arial"; ctx.fillText(text, r - 15, 6); ctx.restore();
        }});
    }}
    spinBtn.addEventListener('click', () => {{
        if (segments[0] === "無名單") return;
        spinBtn.disabled = true;
        const display = window.parent.document.querySelector("#winner_box");
        if(display) display.style.display = "none";
        const duration = 5000;
        const startTime = Date.now();
        const totalRotation = (10 * 360) + Math.random() * 360;
        const startAngle = currentAngle;
        function animate() {{
            const elapsed = Date.now() - startTime;
            const progress = elapsed / duration;
            if (progress < 1) {{
                const easeOut = 1 - Math.pow(1 - progress, 4);
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
                    display.innerHTML = "🎉 恭喜中獎：<span style='color:red;'>" + winner + "</span> 🎉";
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
st.sidebar.title("抽獎設定")
mode = st.sidebar.radio("版面顯示", ["電腦網頁版", "手機行動版"])

if mode == "電腦網頁版":
    c1, c2, c3 = st.columns([1.5, 2, 1.2])
    with c1:
        st.subheader("📸 1. 上傳截圖")
        file = st.file_uploader("請拖放截圖至此", type=["png", "jpg", "jpeg"])
        if file:
            st.image(file, caption="預覽圖片", use_container_width=True)
            if st.button("🔍 開始辨識名單", type="primary", use_container_width=True):
                run_ocr(file)
                st.rerun()
    with c2:
        st.subheader("🎡 2. 抽獎輪盤")
        st.components.v1.html(get_wheel_html("420"), height=580)
        st.markdown('<div id="winner_box" style="display:none; background:#ffffcc; padding:15px; border:3px solid #ffcc00; border-radius:12px; text-align:center; font-size:26px; font-weight:bold;"></div>', unsafe_allow_html=True)
    with c3:
        st.subheader("📝 3. 目前名單")
        st.info(f"總計人數: {len(st.session_state.player_list)}")
        new_list = st.text_area("編輯區", value="\n".join(st.session_state.player_list), height=400)
        if st.button("🔄 同步手動更新"):
            st.session_state.player_list = sorted(list(set([n.strip() for n in new_list.split("\n") if n.strip()])))
            st.rerun()
else:
    # 手機版佈局
    st.title("🎡 行動抽獎轉盤")
    file = st.file_uploader("上傳截圖", type=["png", "jpg", "jpeg"], key="mob_up")
    if file and st.button("🔍 執行辨識", type="primary", use_container_width=True):
        run_ocr(file)
    st.components.v1.html(get_wheel_html("320"), height=450)
    st.markdown('<div id="winner_box" style="display:none; background:#ffffcc; padding:10px; border:2px solid #ffcc00; border-radius:10px; text-align:center; font-size:20px; font-weight:bold;"></div>', unsafe_allow_html=True)
    with st.expander("📝 編輯名單"):
        st.text_area("名單", value="\n".join(st.session_state.player_list), height=250)