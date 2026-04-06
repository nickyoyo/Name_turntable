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
st.set_page_config(page_title="全能抽獎輪盤系統", layout="wide", page_icon="🎡")

# --- 2. 核心 OCR 邏輯與精準過濾 ---
@st.cache_resource
def load_reader():
    # 載入英文與繁體中文模型
    return easyocr.Reader(['en', 'ch_tra'], gpu=False)

def is_valid_name(text):
    text = text.strip()
    # 1. 長度過濾：名字通常在 2~12 字之間
    if len(text) < 2 or len(text) > 12:
        return False
    # 2. 排除純數字 (通常是時間或等級)
    if text.isdigit():
        return False
    # 3. 排除包含非法符號的字串 (排除 OCR 誤認的括號、路徑符號)
    if any(char in text for char in [')', '(', '|', '!', '?', ':', '/', '.', '\\', '+', '=']):
        return False
    # 4. 黑名單：排除截圖中常見的系統文字
    garbage_keywords = [
        '2026', 'AM', 'PM', 'Level', 'Server', '等級', '分', '秒', 
        '在線', '頻道', '系統', '選單', '好友', '訊息', '確定', '取消'
    ]
    if any(k in text for k in garbage_keywords):
        return False
    return True

def advanced_name_fix(name):
    # 針對你提供的截圖辨識錯誤進行強制修正
    corrections = {
        ")HE729": "JHE729",
        "J/729": "JHE729",
        "alan10002o1": "alan1000201",
        "Tacmiba1": "Tachiba7",
        "liiabc": "liiabc",
        "Senbe": "Senbeimiguo" # 防止長名字被截斷辨識
    }
    return corrections.get(name, name)

# --- 3. 狀態初始化 ---
if 'player_list' not in st.session_state:
    st.session_state.player_list = []
if 'preview_idx' not in st.session_state:
    st.session_state.preview_idx = 0

# --- 4. 側邊欄控制 ---
with st.sidebar:
    st.title("⚙️ 系統設定")
    view_mode = st.radio("切換顯示模式", ["電腦網頁版", "手機行動版"], index=0)
    st.divider()
    if st.button("🗑️ 手動清空所有數據", use_container_width=True):
        st.session_state.player_list = []
        st.rerun()

# --- 5. 邏輯函數 ---

def run_ocr_process(files):
    """執行辨識：先清空，再辨識多圖並去重"""
    if not files:
        return
    st.session_state.player_list = [] # 關鍵：辨識前先清空
    reader = load_reader()
    found_names = set() # 使用 set 自動處理重複
    
    for file in files:
        img = Image.open(file)
        img.thumbnail((1200, 1200)) # 提高解析度上限以利辨識
        img_np = np.array(img)
        results = reader.readtext(img_np)
        
        for (_, text, prob) in results:
            text = text.strip()
            # 提高信心門檻至 0.3 減少雜質
            if prob > 0.3 and is_valid_name(text):
                fixed_name = advanced_name_fix(text)
                found_names.add(fixed_name)
    
    st.session_state.player_list = sorted(list(found_names))
    gc.collect()

def image_preview_gallery(files):
    """多圖分頁預覽組件"""
    num = len(files)
    if st.session_state.preview_idx >= num:
        st.session_state.preview_idx = 0
    
    st.write(f"📸 圖片預覽 ({st.session_state.preview_idx + 1} / {num})")
    st.image(files[st.session_state.preview_idx], use_container_width=True)
    
    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        if st.button("⬅️ 上一張", use_container_width=True) and st.session_state.preview_idx > 0:
            st.session_state.preview_idx -= 1
            st.rerun()
    with btn_col2:
        if st.button("下一張 ➡️", use_container_width=True) and st.session_state.preview_idx < num - 1:
            st.session_state.preview_idx += 1
            st.rerun()

def render_wheel_html(height=600, width_style="450px"):
    """抽獎轉盤核心 HTML/JS"""
    display_names = st.session_state.player_list if st.session_state.player_list else ["尚未有名單"]
    json_list = json.dumps(display_names)
    
    return f"""
    <div style="display: flex; flex-direction: column; align-items: center; width: 100%;">
        <div id="container" style="position: relative; width: {width_style}; height: {width_style}; max-width: 90vw; max-height: 90vw;">
            <canvas id="wheel" width="450" height="450" style="width: 100%; height: 100%; border: 6px solid #333; border-radius: 50%; box-shadow: 0 10px 30px rgba(0,0,0,0.2);"></canvas>
            <div id="pointer" style="position: absolute; top: -15px; left: 50%; transform: translateX(-50%); width: 0; height: 0; border-left: 20px solid transparent; border-right: 20px solid transparent; border-top: 35px solid #333; z-index: 10;"></div>
        </div>
        <button id="spinBtn" style="margin-top: 25px; padding: 15px 70px; font-size: 24px; background: linear-gradient(135deg, #ff4b4b, #ff7676); color: white; border: none; border-radius: 50px; cursor: pointer; font-weight: bold; box-shadow: 0 4px 15px rgba(255,75,75,0.4);">SPIN! 旋轉抽獎</button>
    </div>
    <script>
    const segments = {json_list};
    const canvas = document.getElementById('wheel');
    const ctx = canvas.getContext('2d');
    const spinBtn = document.getElementById('spinBtn');
    let currentAngle = 0;
    const colors = segments.map((_, i) => `hsl(${{(i * 360 / segments.length)}}, 75%, 60%)`);

    function drawWheel() {{
        const radius = 225; const arc = 2 * Math.PI / segments.length;
        ctx.clearRect(0, 0, 450, 450);
        segments.forEach((text, i) => {{
            const angle = currentAngle + i * arc;
            ctx.fillStyle = colors[i]; ctx.beginPath(); ctx.moveTo(225, 225); ctx.arc(225, 225, radius, angle, angle + arc); ctx.fill();
            ctx.strokeStyle = "rgba(255,255,255,0.5)"; ctx.lineWidth = 2; ctx.stroke();
            ctx.save(); ctx.fillStyle = "white"; ctx.translate(225, 225); ctx.rotate(angle + arc / 2);
            ctx.textAlign = "right"; ctx.font = "bold 16px Arial";
            let displayTxt = text.length > 8 ? text.substring(0,7)+".." : text;
            ctx.fillText(displayTxt, 210, 6); ctx.restore();
        }});
    }}

    spinBtn.addEventListener('click', () => {{
        if (segments[0] === "尚未有名單") return;
        spinBtn.disabled = true;
        const display = window.parent.document.querySelector("#winner_box");
        if(display) display.style.display = "none";

        const startTime = Date.now(); const duration = 5000;
        const totalRotation = (12 * 360) + Math.random() * 360; 
        const startAngle = currentAngle;

        function animate() {{
            const elapsed = Date.now() - startTime; const fraction = elapsed / duration;
            if (fraction < 1) {{
                const easeOut = 1 - Math.pow(1 - fraction, 4);
                currentAngle = startAngle + (easeOut * totalRotation * (Math.PI / 180));
                drawWheel(); requestAnimationFrame(animate);
            }} else {{
                spinBtn.disabled = false;
                const degrees = (currentAngle * 180 / Math.PI) % 360;
                const index = Math.floor((360 - (degrees + 90) % 360) / (360 / segments.length)) % segments.length;
                const winner = segments[index >= 0 ? index : index + segments.length];
                if(display) {{
                    display.innerHTML = "<div style='font-size:16px;color:#666;'>恭喜中獎</div><div style='color:#ff4b4b; font-size:28px;'>🎊 " + winner + " 🎊</div>";
                    display.style.display = "block";
                }}
                if (window.navigator.vibrate) window.navigator.vibrate([100, 50, 100]);
            }}
        }}
        requestAnimationFrame(animate);
    }});
    drawWheel();
    </script>
    """

# --- 6. 畫面渲染 ---

if view_mode == "電腦網頁版":
    col_l, col_m, col_r = st.columns([1.3, 2.4, 1.3])
    
    with col_l:
        st.subheader("📸 1. 掃描截圖")
        uploaded_files = st.file_uploader("可選取多張圖片", type=["jpg", "png", "jpeg"], accept_multiple_files=True, key="web_up")
        if uploaded_files:
            image_preview_gallery(uploaded_files)
            if st.button("🔍 開始辨識 (覆蓋舊名單)", use_container_width=True, type="primary"):
                run_ocr_process(uploaded_files)
                st.rerun()

    with col_m:
        st.subheader("🎡 2. 抽獎輪盤")
        st.components.v1.html(render_wheel_html(height=650, width_style="450px"), height=650)
        
    with col_r:
        st.subheader("📝 3. 名單管理")
        edited = st.text_area("手動調整名單", value="\n".join(st.session_state.player_list), height=300, help="每行一個名字")
        if st.button("🔄 同步至轉盤", use_container_width=True):
            st.session_state.player_list = sorted(list(set([n.strip() for n in edited.split("\n") if n.strip()])))
            st.rerun()
        
        st.info(f"當前人數：{len(st.session_state.player_list)} 人")
        st.markdown('<div id="winner_box" style="margin-top:20px; font-weight:bold; background:#fff7e6; padding:20px; border-radius:15px; border:3px dashed #ff4b4b; text-align:center; display:none; box-shadow: 0 4px 10px rgba(0,0,0,0.1);"></div>', unsafe_allow_html=True)

else:
    # 手機行動版：垂直佈局
    st.title("🎡 行動抽獎系統")
    
    with st.expander("📸 第一步：上傳與預覽", expanded=len(st.session_state.player_list) == 0):
        uploaded_files = st.file_uploader("選取圖片", type=["jpg", "png", "jpeg"], accept_multiple_files=True, key="mob_up")
        if uploaded_files:
            image_preview_gallery(uploaded_files)
            if st.button("🔍 辨識名單", use_container_width=True, type="primary"):
                run_ocr_process(uploaded_files)
                st.rerun()

    st.subheader("🎯 第二步：旋轉抽獎")
    st.components.v1.html(render_wheel_html(height=550, width_style="85vw"), height=550)
    st.markdown('<div id="winner_box" style="margin: 10px auto; width: 90%; font-weight:bold; background:#fff7e6; padding:20px; border-radius:15px; border:3px dashed #ff4b4b; text-align:center; display:none;"></div>', unsafe_allow_html=True)

    with st.expander("📝 第三步：名單管理"):
        edited = st.text_area("編輯名單", value="\n".join(st.session_state.player_list), height=200)
        if st.button("🔄 更新轉盤", use_container_width=True):
            st.session_state.player_list = sorted(list(set([n.strip() for n in edited.split("\n") if n.strip()])))
            st.rerun()
        st.write(f"目前人數：{len(st.session_state.player_list)}")