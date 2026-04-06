import streamlit as st
import easyocr
import numpy as np
import cv2
from PIL import Image
import json
import base64
from io import BytesIO

# 頁面設定
st.set_page_config(page_title="遊戲抽獎輪盤 Pro", layout="wide", page_icon="🎡")

# --- 1. OCR 邏輯 ---
@st.cache_resource
def load_reader():
    return easyocr.Reader(['en'], gpu=False)

def advanced_name_fix(name):
    corrections = {
        "J|[729": "JHE729", "alan10002o1": "alan1000201", "BobCC": "Bobcc",
        "J/729": "JHE729", "Iiiabc": "liiabc"
    }
    return corrections.get(name, name)

reader = load_reader()

# --- 2. 介面佈局 ---
if 'player_list' not in st.session_state:
    st.session_state.player_list = ["玩家1", "玩家2", "玩家3", "玩家4", "玩家5", "玩家6"]

# 調整比例：讓中間轉盤更大，左右兩側極度縮減
col_left, col_mid, col_right = st.columns([0.8, 2.5, 0.8])

# --- 左欄：強制限制圖片高度 ---
with col_left:
    st.markdown("### 📸 1. 截圖")
    uploaded_file = st.file_uploader("上傳", type=["jpg", "png", "jpeg"], label_visibility="collapsed")
    
    if uploaded_file:
        img = Image.open(uploaded_file)
        
        # 將圖片轉為 base64 嵌入 HTML
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        
        # 關鍵修改：使用 HTML/CSS 強制限制顯示高度為 150px，超過會出現捲軸
        st.markdown(
            f'''
            <div style="height: 150px; overflow-y: auto; border: 1px solid #ddd; border-radius: 5px; margin-bottom: 10px;">
                <img src="data:image/png;base64,{img_str}" style="width: 100%;">
            </div>
            ''', 
            unsafe_allow_html=True
        )
        
        if st.button("🔍 辨識名單", use_container_width=True):
            with st.spinner("辨識中..."):
                img_array = np.array(img)
                gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
                results = reader.readtext(gray)
                names = [advanced_name_fix(text) for (_, text, prob) in results if len(text) > 1 and prob > 0.15]
                if names:
                    st.session_state.player_list = sorted(list(set(names)))
                    st.rerun()

# --- 中欄：轉盤 (稍微縮小畫布確保不遮擋) ---
with col_mid:
    st.markdown("<h3 style='text-align:center;'>🎡 2. 抽獎轉盤</h3>", unsafe_allow_html=True)
    json_list = json.dumps(st.session_state.player_list)
    wheel_html = f"""
    <div style="display: flex; flex-direction: column; align-items: center; justify-content: center;">
        <div id="container" style="position: relative;">
            <canvas id="wheel" width="400" height="400" style="border: 4px solid #333; border-radius: 50%;"></canvas>
            <div id="pointer" style="position: absolute; top: -10px; left: 50%; transform: translateX(-50%); width: 0; height: 0; border-left: 12px solid transparent; border-right: 12px solid transparent; border-top: 25px solid #333; z-index: 10;"></div>
        </div>
        <button id="spinBtn" style="margin-top: 15px; padding: 10px 50px; font-size: 20px; background: #ff4b4b; color: white; border: none; border-radius: 50px; cursor: pointer; font-weight: bold;">SPIN! 抽獎</button>
        <div id="resultModal" style="margin-top: 10px; text-align: center; display: none;">
            <div id="winnerName" style="font-size: 24px; font-weight: bold; background: #ffff00; padding: 5px 20px; border-radius: 8px; border: 2px solid #ff4b4b; display: inline-block;"></div>
        </div>
    </div>
    <script>
    const segments = {json_list};
    const canvas = document.getElementById('wheel');
    const ctx = canvas.getContext('2d');
    const spinBtn = document.getElementById('spinBtn');
    const resultModal = document.getElementById('resultModal');
    const winnerName = document.getElementById('winnerName');
    let currentAngle = 0;
    const colors = segments.map((_, i) => `hsl(${{(i * 360 / segments.length)}}, 75%, 60%)`);
    function drawWheel() {{
        const radius = 200; const arc = 2 * Math.PI / segments.length;
        ctx.clearRect(0, 0, 400, 400);
        segments.forEach((text, i) => {{
            const angle = currentAngle + i * arc;
            ctx.fillStyle = colors[i]; ctx.beginPath(); ctx.moveTo(200, 200); ctx.arc(200, 200, radius, angle, angle + arc); ctx.fill();
            ctx.strokeStyle = "white"; ctx.stroke();
            ctx.save(); ctx.fillStyle = "white"; ctx.translate(200, 200); ctx.rotate(angle + arc / 2);
            ctx.textAlign = "right"; ctx.font = "bold 14px Arial"; ctx.fillText(text, 190, 5); ctx.restore();
        }});
    }}
    spinBtn.addEventListener('click', () => {{
        spinBtn.disabled = true; resultModal.style.display = "none";
        const startTime = Date.now(); const duration = 5000; const minRounds = 8;
        const totalRotation = (minRounds * 360) + Math.random() * 360; const startAngle = currentAngle;
        function animate() {{
            const elapsed = Date.now() - startTime; const fraction = elapsed / duration;
            if (fraction < 1) {{
                currentAngle = startAngle + ((1 - Math.pow(1 - fraction, 3.5)) * totalRotation * (Math.PI / 180));
                drawWheel(); requestAnimationFrame(animate);
            }} else {{
                spinBtn.disabled = false;
                const index = Math.floor((360 - ((currentAngle * 180 / Math.PI) % 360)) / (360 / segments.length)) % segments.length;
                winnerName.innerText = "🎊 " + segments[index]; resultModal.style.display = "block";
            }}
        }}
        requestAnimationFrame(animate);
    }});
    drawWheel();
    </script>
    """
    import streamlit.components.v1 as components
    components.html(wheel_html, height=650)

# --- 右欄：極致精簡名單區 ---
with col_right:
    st.markdown("### 📝 3. 名單")
    edited_names = st.text_area("管理", value="\n".join(st.session_state.player_list), height=180, label_visibility="collapsed")
    current_list = [n.strip() for n in edited_names.split("\n") if n.strip()]
    if st.button("🔄 同步", use_container_width=True):
        st.session_state.player_list = current_list
        st.rerun()
    st.info(f"人數：{len(st.session_state.player_list)}")