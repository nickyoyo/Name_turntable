import streamlit as st
import easyocr
import numpy as np
import cv2
from PIL import Image
import json
import base64
from io import BytesIO

# 頁面設定
st.set_page_config(page_title="OCR 抽獎輪盤", layout="wide", page_icon="🎡")

# --- 1. OCR 邏輯 ---
@st.cache_resource
def load_reader():
    # 載入英文與繁體中文模型
    return easyocr.Reader(['en', 'ch_tra'], gpu=False)

def advanced_name_fix(name):
    corrections = {
        "J|[729": "JHE729", "alan10002o1": "alan1000201", "BobCC": "Bobcc",
        "J/729": "JHE729", "Iiiabc": "liiabc"
    }
    return corrections.get(name, name)

reader = load_reader()

def run_ocr(uploaded_files):
    """執行 OCR 並覆蓋目前名單"""
    if not uploaded_files:
        st.warning("請先選取圖片！")
        return
    
    all_new_names = []
    with st.spinner("正在辨識圖片中..."):
        for file in uploaded_files:
            img = Image.open(file)
            img_array = np.array(img)
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            results = reader.readtext(gray)
            for (_, text, prob) in results:
                if len(text) > 1 and prob > 0.15:
                    all_new_names.append(advanced_name_fix(text))
    
    # 關鍵改動：直接覆蓋 session_state，不與舊名單合併
    st.session_state.player_list = sorted(list(set(all_new_names)))
    st.success(f"辨識完成！共匯入 {len(st.session_state.player_list)} 名玩家。")

# --- 2. 狀態初始化 ---
if 'player_list' not in st.session_state:
    st.session_state.player_list = []
    
# --- 3. 輪盤 HTML 生成 ---
def get_wheel_html(size_px="450"):
    display_list = st.session_state.player_list if st.session_state.player_list else ["請先掃描名單"]
    json_list = json.dumps(display_list)
    
    # 動態計算轉盤半徑
    radius = int(int(size_px.replace('px', '').replace('vw', '')) / 2)
    
    return f"""
    <div style="display: flex; flex-direction: column; align-items: center; font-family: sans-serif;">
        <div id="container" style="position: relative;">
            <canvas id="wheel" width="{size_px}" height="{size_px}" style="border: 5px solid #333; border-radius: 50%;"></canvas>
            <div id="pointer" style="position: absolute; top: -15px; left: 50%; transform: translateX(-50%); width: 0; height: 0; border-left: 18px solid transparent; border-right: 18px solid transparent; border-top: 35px solid #333; z-index: 10;"></div>
        </div>
        <button id="spinBtn" style="margin-top: 20px; padding: 12px 60px; font-size: 22px; background: #ff4b4b; color: white; border: none; border-radius: 50px; cursor: pointer; font-weight: bold;">SPIN! 抽獎</button>
    </div>
    <script>
    const segments = {json_list};
    const canvas = document.getElementById('wheel');
    const ctx = canvas.getContext('2d');
    const spinBtn = document.getElementById('spinBtn');
    let currentAngle = 0;
    const colors = segments.map((_, i) => `hsl(${{(i * 360 / segments.length)}}, 75%, 60%)`);

    function drawWheel() {{
        const r = {radius};
        const arc = 2 * Math.PI / segments.length;
        ctx.clearRect(0, 0, {size_px}, {size_px});
        segments.forEach((text, i) => {{
            const angle = currentAngle + i * arc;
            ctx.fillStyle = colors[i];
            ctx.beginPath(); ctx.moveTo(r, r); ctx.arc(r, r, r, angle, angle + arc); ctx.fill();
            ctx.strokeStyle = "white"; ctx.stroke();
            ctx.save(); ctx.fillStyle = "white"; ctx.translate(r, r); ctx.rotate(angle + arc / 2);
            ctx.textAlign = "right"; ctx.font = "bold 15px Arial"; ctx.fillText(text, r-15, 8); ctx.restore();
        }});
    }}

    spinBtn.addEventListener('click', () => {{
        if (segments.length <= 1 && segments[0] === "請先掃描名單") return;
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

# --- 4. 主介面渲染 ---
st.sidebar.title("⚙️ 系統設定")
view_mode = st.sidebar.radio("顯示模式", ["電腦網頁版", "手機行動版"])

if view_mode == "電腦網頁版":
    col_left, col_mid, col_right = st.columns([1.2, 2.5, 1.2])
    
    with col_left:
        st.subheader("📸 1. 上傳名單")
        files = st.file_uploader("選取圖片", accept_multiple_files=True, key="pc_up")
        if st.button("🔍 開始辨識並更新名單", use_container_width=True, type="primary"):
            run_ocr(files)
            st.rerun()
            
    with col_mid:
        st.subheader("🎡 2. 抽獎轉盤")
        st.components.v1.html(get_wheel_html("450"), height=600)
        
    with col_right:
        st.subheader("📝 3. 名單管理")
        st.info(f"當前人數：{len(st.session_state.player_list)}")
        edited = st.text_area("辨識結果 (可手動調整)", value="\n".join(st.session_state.player_list), height=300)
        if st.button("🔄 同步至轉盤", use_container_width=True):
            st.session_state.player_list = sorted(list(set([n.strip() for n in edited.split("\n") if n.strip()])))
            st.rerun()
        st.markdown('<div id="winner_box" style="display:none; background:#ffff00; padding:20px; font-weight:bold; text-align:center; border:3px solid red; border-radius:10px; font-size:22px; margin-top:10px;"></div>', unsafe_allow_html=True)

else:
    # 手機行動版
    st.title("🎡 行動抽獎系統")
    
    with st.expander("📸 1. 上傳與辨識", expanded=len(st.session_state.player_list)==0):
        files = st.file_uploader("選取截圖", accept_multiple_files=True, key="mob_up")
        if st.button("🔍 執行辨識 (覆蓋舊名單)", use_container_width=True, type="primary"):
            run_ocr(files)
            st.rerun()

    st.subheader("🎯 2. 旋轉抽獎")
    st.components.v1.html(get_wheel_html("320"), height=480)
    st.markdown('<div id="winner_box" style="display:none; background:#ffff00; padding:15px; font-weight:bold; text-align:center; border:3px solid red; border-radius:10px; font-size:18px; margin: 10px 0;"></div>', unsafe_allow_html=True)

    with st.expander("📝 3. 名單管理"):
        st.write(f"當前人數：{len(st.session_state.player_list)}")
        edited = st.text_area("編輯名單", value="\n".join(st.session_state.player_list), height=250)
        if st.button("🔄 更新轉盤", use_container_width=True):
            st.session_state.player_list = sorted(list(set([n.strip() for n in edited.split("\n") if n.strip()])))
            st.rerun()