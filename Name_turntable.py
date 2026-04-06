import streamlit as st
import easyocr
import numpy as np
import cv2
from PIL import Image
import json
import base64
from io import BytesIO
import gc

# --- 1. 頁面設定 ---
st.set_page_config(page_title="全平台抽獎輪盤", layout="wide", page_icon="🎡")

# --- 2. OCR 邏輯 (支援中英、精簡名字) ---
@st.cache_resource
def load_reader():
    return easyocr.Reader(['en', 'ch_tra'], gpu=False)

def is_valid_name(text):
    # 增加過濾符號與雜訊，確保只留下名字
    text = text.strip()
    garbage_keywords = ['2026', 'AM', 'PM', 'Level', 'Server', '等級', '分', '秒', ':', '/', '\\', '.', '在線']
    if len(text) > 10 or len(text) < 2: return False
    if any(k in text for k in garbage_keywords): return False
    # 如果純數字也排除
    if text.isdigit(): return False
    return True

def advanced_name_fix(name):
    corrections = {"J|[729": "JHE729", "alan10002o1": "alan1000201"}
    return corrections.get(name, name)

# --- 3. 狀態初始化 ---
if 'player_list' not in st.session_state:
    st.session_state.player_list = []
if 'preview_idx' not in st.session_state:
    st.session_state.preview_idx = 0

# --- 4. 側邊欄控制 ---
with st.sidebar:
    st.title("⚙️ 設定")
    view_mode = st.radio("選擇顯示模式", ["電腦網頁版", "手機行動版"], index=0)
    st.divider()
    if st.button("🗑️ 清空目前名單", use_container_width=True):
        st.session_state.player_list = []
        st.rerun()

# --- 5. 邏輯函數：OCR 處理 (辨識即清空) ---
def run_ocr_fresh(files):
    if not files: return
    st.session_state.player_list = [] # 清空名單
    reader = load_reader()
    new_names = set() # 用 set 自動去重
    for file in files:
        img = Image.open(file)
        img.thumbnail((1000, 1000))
        results = reader.readtext(np.array(img))
        for (_, text, prob) in results:
            text = text.strip()
            if prob > 0.3 and is_valid_name(text): # 提高門檻減少雜訊
                new_names.add(advanced_name_fix(text))
    st.session_state.player_list = sorted(list(new_names))
    gc.collect()

# --- 6. 圖片預覽組件 ---
def image_preview_gallery(files):
    if not files:
        st.info("請上傳圖片以預覽")
        return
    
    num_files = len(files)
    # 確保索引不會溢出
    if st.session_state.preview_idx >= num_files:
        st.session_state.preview_idx = 0
        
    # 顯示目前是第幾張
    st.write(f"圖片預覽 ({st.session_state.preview_idx + 1} / {num_files})")
    
    # 預覽圖
    img = Image.open(files[st.session_state.preview_idx])
    st.image(img, use_container_width=True)
    
    # 切換按鈕
    col_prev, col_next = st.columns(2)
    with col_prev:
        if st.button("⬅️ 上一張", use_container_width=True) and st.session_state.preview_idx > 0:
            st.session_state.preview_idx -= 1
            st.rerun()
    with col_next:
        if st.button("下一張 ➡️", use_container_width=True) and st.session_state.preview_idx < num_files - 1:
            st.session_state.preview_idx += 1
            st.rerun()

# --- 7. 轉盤組件 (略，同前版本) ---
def render_wheel(height=600, width_px="450px"):
    display_list = st.session_state.player_list if st.session_state.player_list else ["尚未有名單"]
    json_list = json.dumps(display_list)
    wheel_html = f"""
    <div style="display: flex; flex-direction: column; align-items: center; width: 100%;">
        <div id="container" style="position: relative; width: {width_px}; height: {width_px}; max-width: 90vw; max-height: 90vw;">
            <canvas id="wheel" width="450" height="450" style="width: 100%; height: 100%; border: 5px solid #333; border-radius: 50%;"></canvas>
            <div id="pointer" style="position: absolute; top: -10px; left: 50%; transform: translateX(-50%); width: 0; height: 0; border-left: 15px solid transparent; border-right: 15px solid transparent; border-top: 25px solid #333; z-index: 10;"></div>
        </div>
        <button id="spinBtn" style="margin-top: 20px; padding: 12px 60px; font-size: 22px; background: #ff4b4b; color: white; border: none; border-radius: 50px; cursor: pointer; font-weight: bold;">SPIN!</button>
    </div>
    <script>
    const segments = {json_list};
    const canvas = document.getElementById('wheel');
    const ctx = canvas.getContext('2d');
    const spinBtn = document.getElementById('spinBtn');
    let currentAngle = 0;
    const colors = segments.map((_, i) => `hsl(${{(i * 360 / segments.length)}}, 70%, 60%)`);
    function drawWheel() {{
        const radius = 225; const arc = 2 * Math.PI / segments.length;
        ctx.clearRect(0, 0, 450, 450);
        segments.forEach((text, i) => {{
            const angle = currentAngle + i * arc;
            ctx.fillStyle = colors[i]; ctx.beginPath(); ctx.moveTo(225, 225); ctx.arc(225, 225, radius, angle, angle + arc); ctx.fill();
            ctx.strokeStyle = "white"; ctx.stroke();
            ctx.save(); ctx.fillStyle = "white"; ctx.translate(225, 225); ctx.rotate(angle + arc / 2);
            ctx.textAlign = "right"; ctx.font = "bold 16px Arial";
            let txt = text.length > 8 ? text.substring(0,7)+".." : text;
            ctx.fillText(txt, 210, 6); ctx.restore();
        }});
    }}
    spinBtn.addEventListener('click', () => {{
        if (segments[0] === "尚未有名單") return;
        spinBtn.disabled = true;
        const display = window.parent.document.querySelector("#winner_box");
        if(display) display.style.display = "none";
        const startTime = Date.now(); const duration = 5000;
        const totalRotation = (10 * 360) + Math.random() * 360; const startAngle = currentAngle;
        function animate() {{
            const elapsed = Date.now() - startTime; const fraction = elapsed / duration;
            if (fraction < 1) {{
                currentAngle = startAngle + ((1 - Math.pow(1 - fraction, 3.5)) * totalRotation * (Math.PI / 180));
                drawWheel(); requestAnimationFrame(animate);
            }} else {{
                spinBtn.disabled = false;
                const degrees = (currentAngle * 180 / Math.PI) % 360;
                const index = Math.floor((360 - (degrees + 90) % 360) / (360 / segments.length)) % segments.length;
                const winner = segments[index >= 0 ? index : index + segments.length];
                if(display) {{
                    display.innerHTML = "<div style='font-size:14px;color:#666;'>WINNER</div><div style='color:#ff4b4b;'>🎊 " + winner + " 🎊</div>";
                    display.style.display = "block";
                }}
                if (window.navigator.vibrate) window.navigator.vibrate(200);
            }}
        }}
        requestAnimationFrame(animate);
    }});
    drawWheel();
    </script>
    """
    st.components.v1.html(wheel_html, height=height)

# --- 8. 畫面渲染 ---

if view_mode == "電腦網頁版":
    col_l, col_m, col_r = st.columns([1.2, 2.3, 1])
    with col_l:
        st.subheader("📸 掃描名單")
        files = st.file_uploader("上傳多張截圖", accept_multiple_files=True, key="web_up")
        if files:
            image_preview_gallery(files)
            if st.button("🔍 執行辨識 (清空舊名單)", key="web_btn", use_container_width=True, type="primary"):
                run_ocr_fresh(files)
                st.rerun()
    with col_m:
        st.subheader("🎡 抽獎轉盤")
        render_wheel(height=650, width_px="450px")
    with col_r:
        st.subheader("📝 名單管理")
        edited = st.text_area("編輯", value="\n".join(st.session_state.player_list), height=250, label_visibility="collapsed")
        if st.button("🔄 同步修改", key="web_sync", use_container_width=True):
            st.session_state.player_list = sorted(list(set([n.strip() for n in edited.split("\n") if n.strip()])))
            st.rerun()
        st.success(f"人數：{len(st.session_state.player_list)}")
        st.markdown('<div id="winner_box" style="font-size:24px; font-weight:bold; background:#ffff00; padding:15px; border-radius:12px; border:4px solid #ff4b4b; text-align:center; display:none;"></div>', unsafe_allow_html=True)

else:
    st.title("🎡 行動抽獎輪盤")
    with st.expander("📸 1. 上傳與預覽", expanded=len(st.session_state.player_list)==0):
        files = st.file_uploader("上傳截圖", accept_multiple_files=True, key="mob_up")
        if files:
            image_preview_gallery(files)
            if st.button("🔍 執行辨識", key="mob_btn", use_container_width=True, type="primary"):
                run_ocr_fresh(files)
                st.rerun()
    st.subheader("🎯 2. 抽獎旋轉")
    render_wheel(height=550, width_px="90vw")
    st.markdown('<div id="winner_box" style="font-size:24px; font-weight:bold; background:#ffff00; padding:15px; border-radius:12px; border:4px solid #ff4b4b; text-align:center; display:none; margin: 10px auto; width: 80%;"></div>', unsafe_allow_html=True)
    with st.expander("📝 3. 手動管理名單"):
        edited = st.text_area("編輯", value="\n".join(st.session_state.player_list), height=200)
        if st.button("🔄 同步修改", key="mob_sync", use_container_width=True):
            st.session_state.player_list = sorted(list(set([n.strip() for n in edited.split("\n") if n.strip()])))
            st.rerun()