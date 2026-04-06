import streamlit as st
import easyocr
import numpy as np
import cv2
from PIL import Image
import json
import base64
from io import BytesIO

# --- 1. 頁面設定 ---
st.set_page_config(page_title="極速 OCR 抽獎輪盤", layout="wide", page_icon="🎡")

# --- 2. OCR 核心與優化邏輯 ---
@st.cache_resource
def load_reader():
    return easyocr.Reader(['en', 'ch_tra'], gpu=False)

def advanced_name_fix(name):
    """人工容錯字典：修正 OCR 易混淆的遊戲 ID"""
    corrections = {
        "H[729": "JHE729",
        "J|[729": "JHE729",
        "laciiba1": "Tachiba7",
        "alan10002o1": "alan1000201",
        "Ifal": "", 
    }
    fixed = corrections.get(name, name)
    if "729" in fixed and not fixed.startswith("JHE"):
        return "JHE729"
    return fixed

reader = load_reader()

def run_ocr(uploaded_file):
    """辨識單張圖片並覆蓋名單"""
    if not uploaded_file:
        st.warning("請先選取圖片！")
        return
    
    all_new_names = []
    allow_chars = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_-'
    
    with st.spinner("辨識中..."):
        img = Image.open(uploaded_file)
        # 縮圖加速
        max_width = 1000
        if img.width > max_width:
            w_percent = (max_width / float(img.width))
            h_size = int((float(img.height) * float(w_percent)))
            img = img.resize((max_width, h_size), Image.Resampling.LANCZOS)
        
        img_array = np.array(img)
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        results = reader.readtext(binary, allowlist=allow_chars, mag_ratio=1.0)
        
        for (_, text, prob) in results:
            if len(text) > 2 and prob > 0.15:
                fixed = advanced_name_fix(text.strip())
                if fixed:
                    all_new_names.append(fixed)
    
    st.session_state.player_list = sorted(list(set(all_new_names)))
    st.success(f"辨識完成！共 {len(st.session_state.player_list)} 人。")

# --- 3. 初始化 Session ---
if 'player_list' not in st.session_state:
    st.session_state.player_list = []

# --- 4. 輪盤 HTML ---
def get_wheel_html(size_px="450"):
    display_list = st.session_state.player_list if st.session_state.player_list else ["請先辨識名單"]
    json_list = json.dumps(display_list)
    r = int(int(size_px) / 2)
    return f"""
    <div style="display: flex; flex-direction: column; align-items: center; font-family: sans-serif;">
        <div id="container" style="position: relative;">
            <canvas id="wheel" width="{size_px}" height="{size_px}" style="border: 5px solid #333; border-radius: 50%;"></canvas>
            <div id="pointer" style="position: absolute; top: -15px; left: 50%; transform: translateX(-50%); width: 0; height: 0; border-left: 18px solid transparent; border-right: 18px solid transparent; border-top: 30px solid #333; z-index: 10;"></div>
        </div>
        <button id="spinBtn" style="margin-top: 20px; padding: 12px 60px; font-size: 22px; background: #ff4b4b; color: white; border: none; border-radius: 50px; cursor: pointer; font-weight: bold;">SPIN! 抽獎</button>
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
            ctx.strokeStyle = "white"; ctx.stroke();
            ctx.save(); ctx.fillStyle = "white"; ctx.translate(r, r); ctx.rotate(angle + arc / 2);
            ctx.textAlign = "right"; ctx.font = "bold 14px Arial"; ctx.fillText(text, r - 20, 7); ctx.restore();
        }});
    }}
    spinBtn.addEventListener('click', () => {{
        if (segments.length <= 1 && segments[0] === "請先辨識名單") return;
        spinBtn.disabled = true;
        const display = window.parent.document.querySelector("#winner_box");
        if(display) display.style.display = "none";
        const startTime = Date.now(); 
        const duration = 5000; 
        const minRounds = 8;   
        const totalRotation = (minRounds * 360) + Math.random() * 360; 
        const startAngle = currentAngle;
        function animate() {{
            const elapsed = Date.now() - startTime;
            const fraction = elapsed / duration;
            if (fraction < 1) {{
                const easeOut = 1 - Math.pow(1 - fraction, 3.5);
                currentAngle = startAngle + (easeOut * totalRotation * (Math.PI / 180));
                drawWheel();
                requestAnimationFrame(animate);
            }} else {{
                spinBtn.disabled = false;
                const degrees = (currentAngle * 180 / Math.PI) % 360;
                const sliceSize = 360 / segments.length;
                const index = Math.floor((360 - (degrees + 90) % 360) / sliceSize) % segments.length;
                const winner = segments[index >= 0 ? index : index + segments.length];
                if(display) {{
                    display.innerHTML = "<div style='font-size:16px; color:#666;'>WINNER</div><div style='color:#ff4b4b;'>🎊 " + winner + " 🎊</div>";
                    display.style.display = "block";
                }}
            }}
        }}
        requestAnimationFrame(animate);
    }});
    drawWheel();
    </script>
    """

# --- 5. 介面佈局 ---
st.sidebar.title("⚙️ 系統設定")
view_mode = st.sidebar.radio("顯示模式", ["電腦網頁版", "手機行動版"])

if view_mode == "電腦網頁版":
    col_l, col_m, col_r = st.columns([1.2, 2.5, 1.2])
    
    with col_l:
        st.subheader("📸 1. 上傳名單")
        file = st.file_uploader("選取單張截圖", type=["png", "jpg", "jpeg"], key="pc_up")
        
        if file:
            # 顯示圖片預覽 (限制高度以免撐開頁面)
            img_preview = Image.open(file)
            buffered = BytesIO()
            img_preview.save(buffered, format="PNG")
            img_base64 = base64.b64encode(buffered.getvalue()).decode()
            st.markdown(
                f'''<div style="height: 250px; overflow-y: auto; border: 1px solid #ddd; border-radius: 8px; margin-bottom: 15px; background: #f9f9f9; text-align: center;">
                    <img src="data:image/png;base64,{img_base64}" style="width: 100%;">
                </div>''', unsafe_allow_html=True
            )
            
            if st.button("🔍 開始辨識", use_container_width=True, type="primary"):
                run_ocr(file)
                st.rerun()
            
    with col_m:
        st.subheader("🎡 2. 抽獎轉盤")
        st.components.v1.html(get_wheel_html("450"), height=620)
        
    with col_r:
        st.subheader("📝 3. 名單管理")
        st.info(f"當前人數：{len(st.session_state.player_list)}")
        edited = st.text_area("編輯區", value="\n".join(st.session_state.player_list), height=300)
        if st.button("🔄 同步至轉盤", use_container_width=True):
            st.session_state.player_list = sorted(list(set([n.strip() for n in edited.split("\n") if n.strip()])))
            st.rerun()
        st.markdown('<div id="winner_box" style="display:none; background:#ffff00; padding:20px; font-weight:bold; text-align:center; border:4px solid red; border-radius:10px; font-size:22px; margin-top:15px;"></div>', unsafe_allow_html=True)

else:
    # 手機行動版
    st.title("🎡 行動抽獎系統")
    file = st.file_uploader("選取截圖", type=["png", "jpg", "jpeg"], key="mob_up")
    if file:
        st.image(file, use_container_width=True)
        if st.button("🔍 執行辨識", use_container_width=True, type="primary"):
            run_ocr(file)
            st.rerun()

    st.subheader("🎯 2. 旋轉抽獎")
    st.components.v1.html(get_wheel_html("320"), height=480)
    st.markdown('<div id="winner_box" style="display:none; background:#ffff00; padding:15px; font-weight:bold; text-align:center; border:4px solid red; border-radius:10px; font-size:18px; margin: 10px 0;"></div>', unsafe_allow_html=True)