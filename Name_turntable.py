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
st.set_page_config(page_title="全平台抽獎輪盤 (原始辨識版)", layout="wide", page_icon="🎡")

# --- 2. 核心 OCR 邏輯 (去除過濾器) ---
@st.cache_resource
def load_reader():
    return easyocr.Reader(['en', 'ch_tra'], gpu=False)

def advanced_name_fix(name):
    """僅針對已知錯誤進行修正，不進行過濾"""
    corrections = {
        ")HE729": "JHE729", 
        "(HE729": "JHE729", 
        "J/729": "JHE729",
        "alan10002o1": "alan1000201", 
        "Tacmiba1": "Tachiba7",
        "BobCC": "Bobcc", 
        "Iiiabc": "liiabc"
    }
    # 模糊匹配 alan10002 系列
    if "alan10002" in name: return "alan1000201"
    return corrections.get(name, name)

# --- 3. 狀態初始化 ---
if 'player_list' not in st.session_state:
    st.session_state.player_list = []

# --- 4. 側邊欄設定 ---
with st.sidebar:
    st.title("⚙️ 系統設定")
    view_mode = st.radio("顯示模式", ["電腦網頁版", "手機行動版"], index=0)
    st.divider()
    if st.button("🗑️ 清空目前名單", use_container_width=True):
        st.session_state.player_list = []
        st.rerun()

# --- 5. 轉盤 HTML 組件 ---
def get_wheel_html(width_val="450px"):
    display_list = st.session_state.player_list if st.session_state.player_list else ["尚未有名單"]
    json_list = json.dumps(display_list)
    return f"""
    <div style="display: flex; flex-direction: column; align-items: center; width: 100%;">
        <div id="container" style="position: relative; width: {width_val}; height: {width_val}; max-width: 90vw; max-height: 90vw;">
            <canvas id="wheel" width="450" height="450" style="width: 100%; height: 100%; border: 5px solid #333; border-radius: 50%;"></canvas>
            <div style="position: absolute; top: -15px; left: 50%; transform: translateX(-50%); width: 0; height: 0; border-left: 18px solid transparent; border-right: 18px solid transparent; border-top: 35px solid #333; z-index: 10;"></div>
        </div>
        <button id="spinBtn" style="margin-top: 20px; padding: 15px 60px; font-size: 22px; background: #ff4b4b; color: white; border: none; border-radius: 50px; cursor: pointer; font-weight: bold;">SPIN!</button>
    </div>
    <script>
    const segments = {json_list};
    const canvas = document.getElementById('wheel');
    const ctx = canvas.getContext('2d');
    let currentAngle = 0;
    const colors = segments.map((_, i) => `hsl(${{(i * 360 / segments.length)}}, 75%, 60%)`);

    function draw() {{
        const arc = 2 * Math.PI / segments.length;
        ctx.clearRect(0, 0, 450, 450);
        segments.forEach((text, i) => {{
            const angle = currentAngle + i * arc;
            ctx.fillStyle = colors[i]; ctx.beginPath(); ctx.moveTo(225, 225); ctx.arc(225, 225, 225, angle, angle + arc); ctx.fill();
            ctx.save(); ctx.fillStyle = "white"; ctx.translate(225, 225); ctx.rotate(angle + arc / 2);
            ctx.textAlign = "right"; ctx.font = "bold 14px Arial"; 
            ctx.fillText(text.length > 10 ? text.slice(0,9)+".." : text, 215, 5); ctx.restore();
        }});
    }}

    document.getElementById('spinBtn').onclick = () => {{
        if (segments[0] === "尚未有名單") return;
        const start = Date.now(); const duration = 5000;
        const totalRot = (10 * 360) + Math.random() * 360; const startA = currentAngle;
        function ani() {{
            const frac = (Date.now() - start) / duration;
            if (frac < 1) {{
                currentAngle = startA + (1 - Math.pow(1 - frac, 3.5)) * totalRot * (Math.PI / 180);
                draw(); requestAnimationFrame(ani);
            }} else {{
                const deg = (currentAngle * 180 / Math.PI) % 360;
                const idx = Math.floor((360 - (deg + 90) % 360) / (360 / segments.length)) % segments.length;
                const winner = segments[idx < 0 ? idx + segments.length : idx];
                const winBox = window.parent.document.getElementById("winner_box");
                winBox.innerHTML = "🎊 中獎者：" + winner + " 🎊"; winBox.style.display = "block";
            }}
        }}
        ani();
    }};
    draw();
    </script>
    """

# --- 6. OCR 執行函式 (全紀錄模式) ---
def run_ocr(files):
    reader = load_reader()
    st.session_state.player_list = [] # 每次辨識都清空，確保為當前圖片結果
    found_names = []
    
    for file in files:
        img = Image.open(file)
        img_array = np.array(img)
        # 僅做基本灰階處理提高對比
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        results = reader.readtext(gray)
        
        for (_, text, prob) in results:
            # 僅過濾掉長度小於 1 的極端狀況，其餘全部保留
            if len(text) > 0:
                fixed = advanced_name_fix(text)
                found_names.append(fixed)
                
    # 去除重複並排序
    st.session_state.player_list = sorted(list(set(found_names)))
    gc.collect()

# --- 7. 主介面渲染 ---

if view_mode == "電腦網頁版":
    col_l, col_m, col_r = st.columns([1.2, 2.5, 1.2])
    
    with col_l:
        st.subheader("📸 1. 上傳名單")
        files = st.file_uploader("選取圖片", accept_multiple_files=True)
        if st.button("🔍 開始辨識全部文字", use_container_width=True, type="primary"):
            run_ocr(files)
            st.rerun()
            
    with col_m:
        st.subheader("🎡 2. 抽獎轉盤")
        st.components.v1.html(get_wheel_html("450px"), height=650)
        
    with col_r:
        st.subheader("📝 3. 名單管理")
        edited = st.text_area("辨識結果 (可手動刪除雜訊)", value="\n".join(st.session_state.player_list), height=350)
        if st.button("🔄 同步至轉盤", use_container_width=True):
            st.session_state.player_list = sorted(list(set([n.strip() for n in edited.split("\n") if n.strip()])))
            st.rerun()
        st.markdown('<div id="winner_box" style="display:none; background:#ffff00; padding:20px; font-weight:bold; text-align:center; border:3px solid red; border-radius:10px; font-size:22px; margin-top:10px;"></div>', unsafe_allow_html=True)

else:
    # 手機行動版
    st.title("🎡 行動抽獎系統")
    
    with st.expander("📸 1. 上傳與辨識", expanded=len(st.session_state.player_list)==0):
        files = st.file_uploader("選取截圖", accept_multiple_files=True, key="mob_up")
        if st.button("🔍 辨識名單", use_container_width=True, type="primary"):
            run_ocr(files)
            st.rerun()

    st.subheader("🎯 2. 旋轉抽獎")
    st.components.v1.html(get_wheel_html("85vw"), height=550)
    st.markdown('<div id="winner_box" style="display:none; background:#ffff00; padding:15px; font-weight:bold; text-align:center; border:3px solid red; border-radius:10px; font-size:18px; margin: 10px 0;"></div>', unsafe_allow_html=True)

    with st.expander("📝 3. 結果管理"):
        edited = st.text_area("編輯名單", value="\n".join(st.session_state.player_list), height=250)
        if st.button("🔄 更新", use_container_width=True):
            st.session_state.player_list = sorted(list(set([n.strip() for n in edited.split("\n") if n.strip()])))
            st.rerun()