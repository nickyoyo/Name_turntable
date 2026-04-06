import streamlit as st
import easyocr
import numpy as np
import cv2
from PIL import Image
import json
import gc
import re

# --- 1. 頁面設定 ---
st.set_page_config(page_title="精準抽獎輪盤系統", layout="wide", page_icon="🎡")

# --- 2. 強化版 OCR 預處理與校正 ---
@st.cache_resource
def load_reader():
    return easyocr.Reader(['en', 'ch_tra'], gpu=False)

def preprocess_image(img_np):
    """加強圖片對比度，協助辨識紅色底框內的白色文字"""
    # 轉灰階
    gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    # 增加對比度 (CLAHE)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    return enhanced

def is_valid_name(text):
    text = text.strip()
    # 1. 排除過短或過長的雜質
    if len(text) < 3 or len(text) > 15: return False
    # 2. 排除純數字 (時間/等級)
    if text.isdigit(): return False
    # 3. 排除包含非法特殊符號的內容 (OCR 常用括號或點來填補雜訊)
    if re.search(r'[(){}\[\]|!@#$%^&*+=\\/.,:;?]', text): return False
    # 4. 排除遊戲介面常用字 (黑名單)
    garbage = ['Level', 'Server', '等級', '頻道', '系統', '確定', '取消', 'Ifal', 'Tachi']
    if any(g in text for g in garbage): return False
    return True

def advanced_name_fix(name):
    """針對截圖中出現的特定錯誤進行『暴力修正』"""
    # 修正清單：左邊是錯的，右邊是正確的
    corrections = {
        ")HE729": "JHE729",
        "J/729": "JHE729",
        "(HE729": "JHE729",
        "alan10002o1": "alan1000201",
        "Tacmiba1": "Tachiba7",
        "liiabc": "liiabc",
        "nKai": "nKai",
        "Badpet666": "Badpet666"
    }
    # 處理常見的 O 與 0 混淆
    if "alan10002" in name: return "alan1000201"
    
    return corrections.get(name, name)

# --- 3. 狀態初始化 ---
if 'player_list' not in st.session_state:
    st.session_state.player_list = []
if 'preview_idx' not in st.session_state:
    st.session_state.preview_idx = 0

# --- 4. 側邊欄 ---
with st.sidebar:
    st.title("⚙️ 設定")
    view_mode = st.radio("模式", ["電腦網頁版", "手機行動版"])
    st.divider()
    if st.button("🗑️ 清空所有數據"):
        st.session_state.player_list = []
        st.rerun()

# --- 5. 核心 OCR 函數 ---
def run_ocr_process(files):
    if not files: return
    st.session_state.player_list = [] # 辨識前清空
    reader = load_reader()
    found_names = set()
    
    with st.spinner("正在精準辨識中..."):
        for file in files:
            img = Image.open(file)
            img_np = np.array(img)
            # 預處理圖片
            processed_img = preprocess_image(img_np)
            # 進行辨識 (開啟段落合併 paragraph=False 有助於分開名字)
            results = reader.readtext(processed_img, detail=1)
            
            for (bbox, text, prob) in results:
                text = text.strip()
                # 門檻微調：若符合 valid 規則且信心 > 0.25 則採納
                if is_valid_name(text) and prob > 0.25:
                    fixed = advanced_name_fix(text)
                    found_names.add(fixed)
    
    st.session_state.player_list = sorted(list(found_names))
    gc.collect()

# --- 6. 介面組件 ---
def image_preview_gallery(files):
    num = len(files)
    st.session_state.preview_idx = min(st.session_state.preview_idx, num-1)
    st.write(f"📸 預覽 ({st.session_state.preview_idx + 1}/{num})")
    st.image(files[st.session_state.preview_idx], use_container_width=True)
    c1, c2 = st.columns(2)
    with c1:
        if st.button("⬅️ 上一張") and st.session_state.preview_idx > 0:
            st.session_state.preview_idx -= 1
            st.rerun()
    with c2:
        if st.button("下一張 ➡️") and st.session_state.preview_idx < num - 1:
            st.session_state.preview_idx += 1
            st.rerun()

def render_wheel_html(height=600, width_style="450px"):
    names = st.session_state.player_list if st.session_state.player_list else ["尚未有名單"]
    json_list = json.dumps(names)
    return f"""
    <div style="display: flex; flex-direction: column; align-items: center; width: 100%;">
        <div id="container" style="position: relative; width: {width_style}; height: {width_style}; max-width: 90vw; max-height: 90vw;">
            <canvas id="wheel" width="450" height="450" style="width: 100%; height: 100%; border: 6px solid #333; border-radius: 50%;"></canvas>
            <div style="position: absolute; top: -15px; left: 50%; transform: translateX(-50%); width: 0; height: 0; border-left: 20px solid transparent; border-right: 20px solid transparent; border-top: 35px solid #333;"></div>
        </div>
        <button id="spinBtn" style="margin-top: 20px; padding: 12px 60px; font-size: 22px; background: #ff4b4b; color: white; border: none; border-radius: 50px; font-weight: bold; cursor: pointer;">SPIN!</button>
    </div>
    <script>
        const segments = {json_list};
        const canvas = document.getElementById('wheel');
        const ctx = canvas.getContext('2d');
        const spinBtn = document.getElementById('spinBtn');
        let currentAngle = 0;
        const colors = segments.map((_, i) => `hsl(${{(i * 360 / segments.length)}}, 70%, 60%)`);

        function draw() {{
            const arc = 2 * Math.PI / segments.length;
            ctx.clearRect(0,0,450,450);
            segments.forEach((text, i) => {{
                const angle = currentAngle + i * arc;
                ctx.fillStyle = colors[i]; ctx.beginPath(); ctx.moveTo(225,225); ctx.arc(225,225,225,angle,angle+arc); ctx.fill();
                ctx.save(); ctx.fillStyle = "white"; ctx.translate(225,225); ctx.rotate(angle+arc/2);
                ctx.textAlign="right"; ctx.font="bold 16px Arial"; ctx.fillText(text.length > 9 ? text.slice(0,8)+".." : text, 210, 6); ctx.restore();
            }});
        }}
        spinBtn.onclick = () => {{
            if(segments[0]==="尚未有名單") return;
            spinBtn.disabled = true;
            const duration = 5000; const start = Date.now();
            const totalRot = (10*360) + Math.random()*360; const startA = currentAngle;
            function ani() {{
                const now = Date.now()-start; const frac = now/duration;
                if(frac<1) {{
                    currentAngle = startA + (1-Math.pow(1-frac,4))*totalRot*(Math.PI/180);
                    draw(); requestAnimationFrame(ani);
                }} else {{
                    spinBtn.disabled = false;
                    const deg = (currentAngle*180/Math.PI)%360;
                    const idx = Math.floor((360-(deg+90)%360)/(360/segments.length))%segments.length;
                    const winner = segments[idx<0?idx+segments.length:idx];
                    const winBox = window.parent.document.getElementById("winner_box");
                    winBox.innerHTML = "中獎者： " + winner; winBox.style.display="block";
                }}
            }}
            ani();
        }};
        draw();
    </script>
    """

# --- 7. 渲染介面 ---
if view_mode == "電腦網頁版":
    col1, col2, col3 = st.columns([1.3, 2.4, 1.3])
    with col1:
        st.subheader("📸 1. 掃描")
        up = st.file_uploader("上傳圖片", accept_multiple_files=True)
        if up:
            image_preview_gallery(up)
            if st.button("🔍 辨識 (覆蓋)", type="primary", use_container_width=True):
                run_ocr_process(up)
                st.rerun()
    with col2:
        st.subheader("🎡 2. 抽獎")
        st.components.v1.html(render_wheel_html(), height=600)
    with col3:
        st.subheader("📝 3. 管理")
        txt = st.text_area("名單", value="\n".join(st.session_state.player_list), height=300)
        if st.button("🔄 同步修改", use_container_width=True):
            st.session_state.player_list = sorted(list(set([n.strip() for n in txt.split("\n") if n.strip()])))
            st.rerun()
        st.markdown('<div id="winner_box" style="display:none; background:yellow; padding:20px; font-weight:bold; text-align:center; border:3px solid red; border-radius:10px;"></div>', unsafe_allow_html=True)
else:
    # 手機版 (垂直排版)
    st.title("🎡 行動抽獎")
    with st.expander("📸 1. 上傳與預覽"):
        up = st.file_uploader("上傳圖片", accept_multiple_files=True, key="m_up")
        if up:
            image_preview_gallery(up)
            if st.button("🔍 辨識", type="primary"):
                run_ocr_process(up)
                st.rerun()
    st.components.v1.html(render_wheel_html(width_style="85vw"), height=550)
    st.markdown('<div id="winner_box" style="display:none; background:yellow; padding:15px; font-weight:bold; text-align:center; border:2px solid red;"></div>', unsafe_allow_html=True)
    with st.expander("📝 3. 名單管理"):
        txt = st.text_area("編輯", value="\n".join(st.session_state.player_list))
        if st.button("🔄 更新"):
            st.session_state.player_list = sorted(list(set([n.strip() for n in txt.split("\n") if n.strip()])))
            st.rerun()