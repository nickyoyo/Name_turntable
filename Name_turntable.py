import streamlit as st
import easyocr
import numpy as np
import cv2
from PIL import Image
import json

# 頁面設定：強制使用寬螢幕模式以容納三欄
st.set_page_config(page_title="遊戲抽獎輪盤 Pro", layout="wide", page_icon="🎡")

# --- 1. OCR 邏輯 ---
@st.cache_resource
def load_reader():
    return easyocr.Reader(['en'], gpu=False) # 遊戲名字多為英文，僅載入英文可加速

def advanced_name_fix(name):
    corrections = {
        "J|[729": "JHE729",
        "alan10002o1": "alan1000201",
        "BobCC": "Bobcc",
        "J/729": "JHE729",
        "Iiiabc": "liiabc"
    }
    return corrections.get(name, name)

reader = load_reader()

# --- 2. 界面佈局 (分為三欄) ---
if 'player_list' not in st.session_state:
    st.session_state.player_list = ["玩家1", "玩家2", "玩家3", "玩家4", "玩家5", "玩家6"]

# 設定欄位比例：左(1) : 中(2.5) : 右(1)
col_left, col_mid, col_right = st.columns([1, 2.5, 1])

# --- 左欄：圖片上傳與預覽 ---
with col_left:
    st.subheader("📸 1. 上傳截圖")
    uploaded_file = st.file_uploader("選擇圖片", type=["jpg", "png", "jpeg"])
    
    if uploaded_file:
        img = Image.open(uploaded_file)
        # 限制顯示寬度，避免圖片過大
        st.image(img, caption="原始截圖", use_container_width=True) 
        
        if st.button("🔍 辨識名單", use_container_width=True):
            with st.spinner("辨識中..."):
                img_array = np.array(img)
                gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
                results = reader.readtext(gray)
                
                names = []
                for (bbox, text, prob) in results:
                    if len(text) > 1 and prob > 0.15:
                        names.append(advanced_name_fix(text))
                
                if names:
                    st.session_state.player_list = sorted(list(set(names)))
                    st.rerun()

# --- 中欄：核心轉盤功能 (5秒 8圈) ---
with col_mid:
    st.subheader("🎡 2. 抽獎轉盤")
    json_list = json.dumps(st.session_state.player_list)

    wheel_html = f"""
    <div style="display: flex; flex-direction: column; align-items: center; font-family: sans-serif;">
        <div id="container" style="position: relative;">
            <canvas id="wheel" width="500" height="500" style="border: 5px solid #333; border-radius: 50%; box-shadow: 0 10px 30px rgba(0,0,0,0.2);"></canvas>
            <div id="pointer" style="position: absolute; top: -15px; left: 50%; transform: translateX(-50%); width: 0; height: 0; border-left: 18px solid transparent; border-right: 18px solid transparent; border-top: 35px solid #333; z-index: 10;"></div>
        </div>
        <button id="spinBtn" style="margin-top: 30px; padding: 15px 80px; font-size: 26px; background: #ff4b4b; color: white; border: none; border-radius: 50px; cursor: pointer; font-weight: bold; box-shadow: 0 4px 15px rgba(0,0,0,0.3);">SPIN! 抽獎</button>
        
        <div id="resultModal" style="margin-top: 25px; text-align: center; display: none;">
            <h1 style="color: #ff4b4b; font-size: 45px; margin-bottom: 5px; text-shadow: 2px 2px 4px rgba(0,0,0,0.1);">🎊 WINNER! 🎊</h1>
            <div id="winnerName" style="font-size: 36px; font-weight: bold; background: #ffff00; padding: 15px 40px; border-radius: 15px; border: 3px solid #ff4b4b; display: inline-block;"></div>
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
        const radius = 250;
        const arc = 2 * Math.PI / segments.length;
        ctx.clearRect(0, 0, 500, 500);

        segments.forEach((text, i) => {{
            const angle = currentAngle + i * arc;
            ctx.fillStyle = colors[i];
            ctx.beginPath(); ctx.moveTo(250, 250); ctx.arc(250, 250, radius, angle, angle + arc); ctx.fill();
            ctx.strokeStyle = "white"; ctx.lineWidth = 2; ctx.stroke();

            ctx.save();
            ctx.fillStyle = "white"; ctx.translate(250, 250); ctx.rotate(angle + arc / 2);
            ctx.textAlign = "right"; ctx.font = "bold 18px Arial";
            ctx.fillText(text, 235, 10);
            ctx.restore();
        }});
    }}

    function spin() {{
        if (segments.length === 0) return;
        spinBtn.disabled = true;
        resultModal.style.display = "none";
        
        const startTime = Date.now();
        const duration = 5000; // 5秒
        const minRounds = 8;   // 8圈
        const totalRotation = (minRounds * 360) + Math.random() * 360; 
        const startAngle = currentAngle;

        function animate() {{
            const now = Date.now();
            const elapsed = now - startTime;
            const fraction = elapsed / duration;

            if (fraction < 1) {{
                const easeOut = 1 - Math.pow(1 - fraction, 3.5); // 稍微加強減速感
                currentAngle = startAngle + (easeOut * totalRotation * (Math.PI / 180));
                drawWheel();
                requestAnimationFrame(animate);
            }} else {{
                spinBtn.disabled = false;
                const index = Math.floor((360 - ((currentAngle * 180 / Math.PI) % 360)) / (360 / segments.length)) % segments.length;
                winnerName.innerText = segments[index];
                resultModal.style.display = "block";
            }}
        }}
        requestAnimationFrame(animate);
    }}

    spinBtn.addEventListener('click', spin);
    drawWheel();
    </script>
    """
    import streamlit.components.v1 as components
    components.html(wheel_html, height=850)

# --- 右欄：名單編輯與管理 ---
with col_right:
    st.subheader("📝 3. 名單管理")
    st.write("掃描後的名單會顯示在此，你也可以手動修改：")
    
    edited_names = st.text_area(
        "名單編輯 (每行一位玩家)", 
        value="\n".join(st.session_state.player_list), 
        height=400,
        help="修改後請點擊下方同步按鈕"
    )
    
    current_list = [n.strip() for n in edited_names.split("\n") if n.strip()]
    
    if st.button("🔄 同步修改至轉盤", use_container_width=True):
        st.session_state.player_list = current_list
        st.success("名單已更新！")
        st.rerun()

    st.divider()
    st.info(f"當前人數：{len(st.session_state.player_list)} 人")