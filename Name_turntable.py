import streamlit as st
import easyocr
import numpy as np
import cv2
from PIL import Image
import json

# 頁面設定
st.set_page_config(page_title="遊戲抽獎輪盤", layout="wide", page_icon="🎡")

# --- 1. OCR 邏輯 ---
@st.cache_resource
def load_reader():
    return easyocr.Reader(['en', 'ch_tra'], gpu=False)

def advanced_name_fix(name):
    corrections = {
        "J|[729": "JHE729",
        "alan10002o1": "alan1000201",
        "BobCC": "Bobcc"
    }
    return corrections.get(name, name)

reader = load_reader()

# --- 2. 界面佈局 ---
st.title("🎡 實體旋轉抽獎輪盤")

if 'player_list' not in st.session_state:
    st.session_state.player_list = ["玩家1", "玩家2", "玩家3", "玩家4"]

col_file, col_wheel = st.columns([1, 2])

with col_file:
    st.subheader("第一步：掃描圖片")
    uploaded_file = st.file_uploader("上傳截圖", type=["jpg", "png", "jpeg"])
    
    if uploaded_file:
        img = Image.open(uploaded_file)
        st.image(img, use_container_width=True)
        if st.button("🔍 辨識並更新輪盤"):
            img_array = np.array(img)
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            results = reader.readtext(gray)
            names = [advanced_name_fix(text) for (bbox, text, prob) in results if len(text) > 1 and prob > 0.2]
            if names:
                st.session_state.player_list = list(set(names))
                st.success(f"已載入 {len(names)} 位玩家！")

    # 手動編輯區
    edited_names = st.text_area("編輯名單 (每行一個)", value="\n".join(st.session_state.player_list), height=200)
    current_list = [n.strip() for n in edited_names.split("\n") if n.strip()]
    if st.button("🎯 同步名單至轉盤"):
        st.session_state.player_list = current_list

# --- 3. JavaScript 轉盤組件 ---
with col_wheel:
    st.subheader("第二步：點擊輪盤旋轉")
    
    # 將 Python 列表轉換為 JavaScript 陣列
    json_list = json.dumps(st.session_state.player_list)

    # HTML/JS 轉盤代碼
    wheel_html = f"""
    <div style="display: flex; flex-direction: column; align-items: center;">
        <canvas id="wheel" width="500" height="500" style="border-radius: 50%; box-shadow: 0 0 20px rgba(0,0,0,0.2);"></canvas>
        <button id="spinBtn" style="margin-top: 20px; padding: 15px 40px; font-size: 20px; background-color: #ff4b4b; color: white; border: none; border-radius: 5px; cursor: pointer; font-weight: bold;">SPIN! 旋轉</button>
        <h2 id="winnerDisplay" style="margin-top: 20px; color: #ff4b4b; min-height: 40px;"></h2>
    </div>

    <script>
    const segments = {json_list};
    const canvas = document.getElementById('wheel');
    const ctx = canvas.getContext('2d');
    const spinBtn = document.getElementById('spinBtn');
    const winnerDisplay = document.getElementById('winnerDisplay');

    let startAngle = 0;
    const arc = Math.PI / (segments.length / 2);
    let spinTimeout = null;
    let spinAngleStart = 10;
    let spinTime = 0;
    let spinTimeTotal = 0;

    function drawWheel() {{
        ctx.clearRect(0, 0, 500, 500);
        const centerX = 250;
        const centerY = 250;
        const radius = 240;

        segments.forEach((text, i) => {{
            const angle = startAngle + i * arc;
            ctx.fillStyle = `hsl(${{(i * 360 / segments.length)}}, 70%, 60%)`;
            
            ctx.beginPath();
            ctx.moveTo(centerX, centerY);
            ctx.arc(centerX, centerY, radius, angle, angle + arc, false);
            ctx.lineTo(centerX, centerY);
            ctx.fill();
            ctx.stroke();

            ctx.save();
            ctx.fillStyle = "white";
            ctx.translate(centerX + Math.cos(angle + arc / 2) * radius * 0.7, 
                          centerY + Math.sin(angle + arc / 2) * radius * 0.7);
            ctx.rotate(angle + arc / 2 + Math.PI / 2);
            ctx.font = 'bold 16px Arial';
            ctx.fillText(text, -ctx.measureText(text).width / 2, 0);
            ctx.restore();
        }});

        // 繪製箭頭
        ctx.fillStyle = "black";
        ctx.beginPath();
        ctx.moveTo(centerX + 10, centerY - radius - 10);
        ctx.lineTo(centerX - 10, centerY - radius - 10);
        ctx.lineTo(centerX, centerY - radius + 20);
        ctx.fill();
    }}

    function rotateWheel() {{
        spinTime += 30;
        if (spinTime >= spinTimeTotal) {{
            stopRotateWheel();
            return;
        }}
        const spinAngle = spinAngleStart - easeOut(spinTime, 0, spinAngleStart, spinTimeTotal);
        startAngle += (spinAngle * Math.PI / 180);
        drawWheel();
        spinTimeout = setTimeout(rotateWheel, 30);
    }}

    function stopRotateWheel() {{
        clearTimeout(spinTimeout);
        const degrees = startAngle * 180 / Math.PI + 90;
        const arcd = arc * 180 / Math.PI;
        const index = Math.floor((360 - (degrees % 360)) / arcd);
        winnerDisplay.innerHTML = "🎊 中獎者: " + segments[index] + " 🎊";
    }}

    function easeOut(t, b, c, d) {{
        const ts = (t /= d) * t;
        const tc = ts * t;
        return b + c * (tc + -3 * ts + 3 * t);
    }}

    spinBtn.addEventListener('click', () => {{
        winnerDisplay.innerHTML = "🎲 旋轉中...";
        spinAngleStart = Math.random() * 10 + 10;
        spinTime = 0;
        spinTimeTotal = Math.random() * 3000 + 4000;
        rotateWheel();
    }});

    drawWheel();
    </script>
    """
    import streamlit.components.v1 as components
    components.html(wheel_html, height=700)