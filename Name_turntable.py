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
    # Streamlit Cloud 建議設為 gpu=False，若你有本地 GPU 環境再改回 True
    return easyocr.Reader(['en'], gpu=False)

def advanced_name_fix(name):
    corrections = {
        "J|[729": "JHE729", "alan10002o1": "alan1000201", "BobCC": "Bobcc",
        "J/729": "JHE729", "Iiiabc": "liiabc"
    }
    return corrections.get(name, name)

reader = load_reader()

# --- 2. 界面佈局 ---
if 'player_list' not in st.session_state:
    st.session_state.player_list = ["玩家1", "玩家2", "玩家3", "玩家4", "玩家5", "玩家6"]

col_left, col_mid, col_right = st.columns([1, 2.5, 1])

# --- 左欄：限制圖片預覽高度 ---
with col_left:
    st.subheader("📸 1. 上傳截圖")
    uploaded_file = st.file_uploader("選擇圖片", type=["jpg", "png", "jpeg"], label_visibility="collapsed")
    
    if uploaded_file:
        img = Image.open(uploaded_file)
        
        # 使用 Base64 嵌入並限制高度，防止按鈕被擠下去
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        st.markdown(
            f'''<div style="height: 400px; overflow-y: auto; border: 1px solid #ddd; border-radius: 5px; margin-bottom: 10px;">
                <img src="data:image/png;base64,{img_str}" style="width: 100%;">
            </div>''', unsafe_allow_html=True
        )
        
        if st.button("🔍 執行辨識", use_container_width=True):
            with st.spinner("辨識中..."):
                img_array = np.array(img)
                gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
                results = reader.readtext(gray)
                names = [advanced_name_fix(text) for (_, text, prob) in results if len(text) > 1 and prob > 0.15]
                if names:
                    st.session_state.player_list = sorted(list(set(names)))
                    st.rerun()

# --- 中欄：修正對位邏輯的轉盤 ---
with col_mid:
    st.subheader("🎡 2. 抽獎轉盤")
    json_list = json.dumps(st.session_state.player_list)
    wheel_html = f"""
    <div style="display: flex; flex-direction: column; align-items: center; font-family: sans-serif;">
        <div id="container" style="position: relative;">
            <canvas id="wheel" width="450" height="450" style="border: 5px solid #333; border-radius: 50%;"></canvas>
            <div id="pointer" style="position: absolute; top: -15px; left: 50%; transform: translateX(-50%); width: 0; height: 0; border-left: 18px solid transparent; border-right: 18px solid transparent; border-top: 35px solid #333; z-index: 10;"></div>
        </div>
        <button id="spinBtn" style="margin-top: 20px; padding: 12px 60px; font-size: 22px; background: #ff4b4b; color: white; border: none; border-radius: 50px; cursor: pointer; font-weight: bold;">SPIN! 抽獎</button>
        <div id="resultModal" style="margin-top: 15px; text-align: center; display: none;">
            <h2 style="color: #ff4b4b; margin: 0;">🎊 WINNER! 🎊</h2>
            <div id="winnerName" style="font-size: 28px; font-weight: bold; background: #ffff00; padding: 10px 30px; border-radius: 10px; border: 2px solid #ff4b4b; display: inline-block;"></div>
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
        const radius = 225;
        const arc = 2 * Math.PI / segments.length;
        ctx.clearRect(0, 0, 450, 450);
        segments.forEach((text, i) => {{
            const angle = currentAngle + i * arc;
            ctx.fillStyle = colors[i];
            ctx.beginPath(); ctx.moveTo(225, 225); ctx.arc(225, 225, radius, angle, angle + arc); ctx.fill();
            ctx.strokeStyle = "white"; ctx.stroke();
            ctx.save(); ctx.fillStyle = "white"; ctx.translate(225, 225); ctx.rotate(angle + arc / 2);
            ctx.textAlign = "right"; ctx.font = "bold 15px Arial"; ctx.fillText(text, 210, 8); ctx.restore();
        }});
    }}

    spinBtn.addEventListener('click', () => {{
        if (segments.length === 0) return;
        spinBtn.disabled = true; resultModal.style.display = "none";
        const startTime = Date.now(); 
        const duration = 5000; // 旋轉5秒
        const minRounds = 8;   // 至少轉8圈
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
                // --- 修正後的對位算法 ---
                // 1. 旋轉是順時針增加角度，文字也是順時針排列
                // 2. 畫布 0 度在 3 點鐘，指針在 12 點鐘 (-90度位置)
                // 3. 計算時需補償這 90 度的偏移
                const degrees = (currentAngle * 180 / Math.PI) % 360;
                const sliceSize = 360 / segments.length;
                // 算法：(360 - (度數 + 90) % 360) / 每片度數
                const index = Math.floor((360 - (degrees + 90) % 360) / sliceSize) % segments.length;
                
                winnerName.innerText = segments[index >= 0 ? index : index + segments.length]; 
                resultModal.style.display = "block";
            }}
        }}
        requestAnimationFrame(animate);
    }});
    drawWheel();
    </script>
    """
    import streamlit.components.v1 as components
    components.html(wheel_html, height=720)

# --- 右欄：名單管理 ---
with col_right:
    st.subheader("📝 3. 名單管理")
    edited_names = st.text_area("名單編輯", value="\n".join(st.session_state.player_list), height=250)
    current_list = [n.strip() for n in edited_names.split("\n") if n.strip()]
    
    if st.button("🔄 同步至轉盤", use_container_width=True):
        st.session_state.player_list = current_list
        st.rerun()
    st.success(f"當前人數：{len(st.session_state.player_list)} 人")