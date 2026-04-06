import streamlit as st
import easyocr
import numpy as np
import cv2
from PIL import Image
import json
import base64
from io import BytesIO

# 頁面設定
st.set_page_config(page_title="多圖累加抽獎輪盤", layout="wide", page_icon="🎡")

# --- 1. OCR 邏輯 (支援中英) ---
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

# --- 2. 狀態初始化 ---
if 'player_list' not in st.session_state:
    st.session_state.player_list = [] # 預設空名單，等待掃描

# --- 3. 界面佈局 ---
col_left, col_mid, col_right = st.columns([1, 2.5, 1])

# --- 左欄：多圖上傳與累加 ---
with col_left:
    st.subheader("📸 1. 掃描截圖")
    # 設為 True 即可一次選取多張圖片，或分次上傳
    uploaded_files = st.file_uploader("上傳一張或多張截圖", type=["jpg", "png", "jpeg"], accept_multiple_files=True, label_visibility="collapsed")
    
    if uploaded_files:
        # 顯示最近一張上傳的圖片預覽
        last_img = Image.open(uploaded_files[-1])
        buffered = BytesIO()
        last_img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        st.markdown(
            f'''<div style="height: 0px; overflow-y: auto; border: 1px solid #ddd; border-radius: 5px; margin-bottom: 10px;">
                <img src="data:image/png;base64,{img_str}" style="width: 100%;">
            </div>''', unsafe_allow_html=True
        )
        
        if st.button("🔍 辨識並「累加」至名單", use_container_width=True):
            with st.spinner("正在辨識所有圖片..."):
                all_new_names = []
                for file in uploaded_files:
                    img = Image.open(file)
                    img_array = np.array(img)
                    gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
                    results = reader.readtext(gray)
                    for (_, text, prob) in results:
                        if len(text) > 1 and prob > 0.15:
                            all_new_names.append(advanced_name_fix(text))
                
                # 取得舊名單並合併新名單，透過 set 去除重複
                combined_list = list(set(st.session_state.player_list + all_new_names))
                st.session_state.player_list = sorted(combined_list)
                st.success(f"已從 {len(uploaded_files)} 張圖中加入名單！")
                st.rerun()

    if st.button("🗑️ 清空所有名單", use_container_width=True, type="secondary"):
        st.session_state.player_list = []
        st.rerun()

# --- 中欄：轉盤功能 ---
with col_mid:
    st.subheader("🎡 2. 抽獎轉盤")
    # 如果名單為空，給予預設提示
    display_list = st.session_state.player_list if st.session_state.player_list else ["請先掃描名單"]
    json_list = json.dumps(display_list)
    
    wheel_html = f"""
    <div style="display: flex; flex-direction: column; align-items: center; font-family: sans-serif;">
        <div id="container" style="position: relative;">
            <canvas id="wheel" width="450" height="450" style="border: 5px solid #333; border-radius: 50%;"></canvas>
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
    import streamlit.components.v1 as components
    components.html(wheel_html, height=600)

# --- 右欄：名單管理與隱藏結果 ---
with col_right:
    st.subheader("📝 3. 名單管理")
    edited_names = st.text_area("管理", value="\n".join(st.session_state.player_list), height=250, label_visibility="collapsed")
    
    if st.button("🔄 同步修改", use_container_width=True):
        st.session_state.player_list = [n.strip() for n in edited_names.split("\n") if n.strip()]
        st.rerun()
    
    st.success(f"人數：{len(st.session_state.player_list)}")
    
    st.markdown("<br>", unsafe_allow_html=True)
    # 中獎顯示區
    st.markdown(
        '''<div id="winner_box" style="font-size: 24px; font-weight: bold; background: #ffff00; 
        padding: 15px; border-radius: 12px; border: 4px solid #ff4b4b; text-align: center; 
        display: none; box-shadow: 0 4px 10px rgba(0,0,0,0.1); animation: fadeIn 0.5s;">
        </div>
        <style>@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }</style>
        ''', unsafe_allow_html=True
    )