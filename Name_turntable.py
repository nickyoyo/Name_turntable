import streamlit as st
import easyocr
import numpy as np
import cv2
from PIL import Image
import json
import base64
from io import BytesIO
import gc
import re # 導入正則表達式

# --- 1. 頁面設定 ---
st.set_page_config(page_title="精準辨識抽獎輪盤", layout="wide", page_icon="🎡")

# --- 2. 強化版 OCR 邏輯 ---
@st.cache_resource
def load_reader():
    # 支援英、繁中
    return easyocr.Reader(['en', 'ch_tra'], gpu=False)

def is_valid_name(text):
    text = text.strip()
    
    # 1. 基本長度過濾 (名字通常在 2~10 字之間)
    if len(text) < 2 or len(text) > 10:
        return False
    
    # 2. 排除純數字 (通常是時間、等級、金錢)
    if text.isdigit():
        return False
    
    # 3. 排除包含特殊符號的字串 (名字通常不會有這些)
    if any(char in text for char in [':', '/', '\\', '.', ',', '=', '+', '-', '*', '%', '(', ')']):
        return False
    
    # 4. 黑名單關鍵字 (根據你提供的截圖內容持續增加)
    garbage_keywords = [
        '2026', 'AM', 'PM', 'Level', 'Server', '等級', '分', '秒', '在線', 
        '頻道', '系統', '選單', '好友', '訊息', '確定', '取消', '關閉', '點擊'
    ]
    if any(k in text for k in garbage_keywords):
        return False
        
    # 5. 排除含有過多英數字混雜的內容 (可能是系統 ID 或亂碼)
    # 如果包含 3 個以上的數字，通常不是人名
    if len(re.findall(r'\d', text)) > 2:
        return False

    return True

def advanced_name_fix(name):
    # 手動修正表
    corrections = {"J|[729": "JHE729", "alan10002o1": "alan1000201"}
    return corrections.get(name, name)

# --- 3. 狀態初始化 ---
if 'player_list' not in st.session_state:
    st.session_state.player_list = []

# --- 4. 核心 OCR 處理 (自動去重 + 清空) ---
def run_ocr_fresh(files):
    if not files: return
    
    # 點擊辨識時清空舊名單
    st.session_state.player_list = []
    
    reader = load_reader()
    found_names = set() # 使用 set 確保在辨識階段就自動去重
    
    for file in files:
        img = Image.open(file)
        # 縮圖加速且省記憶體
        img.thumbnail((1000, 1000)) 
        results = reader.readtext(np.array(img))
        
        for (_, text, prob) in results:
            text = text.strip()
            # 門檻提高：置信度需 > 0.3 (減少雜訊)
            if prob > 0.3 and is_valid_name(text):
                fixed_name = advanced_name_fix(text)
                found_names.add(fixed_name) # set 會自動排除重複名字
    
    # 將去重後的結果轉回 list 並排序
    st.session_state.player_list = sorted(list(found_names))
    gc.collect()

# --- 5. 顯示模式切換與轉盤組件 (略，同前版本) ---
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

# --- 6. 畫面渲染 (關鍵修正：去重顯示) ---

# 側邊欄模式切換
with st.sidebar:
    st.title("⚙️ 設定")
    view_mode = st.radio("選擇模式", ["電腦版", "手機版"])
    if st.button("🗑️ 手動清空", use_container_width=True):
        st.session_state.player_list = []
        st.rerun()

# 主介面邏輯 (以電腦版為例展示關鍵區塊)
if view_mode == "電腦版":
    col_l, col_m, col_r = st.columns([1, 2.5, 1])
    with col_l:
        st.subheader("📸 掃描")
        files = st.file_uploader("上傳", accept_multiple_files=True, key="web_up")
        if st.button("🔍 執行辨識", use_container_width=True):
            run_ocr_fresh(files)
            st.rerun()
    
    with col_m:
        st.subheader("🎡 轉盤")
        # 這裡會呼叫之前的 render_wheel(height=650, width_px="450px")
        # 確保傳進去的是 st.session_state.player_list
        
    with col_r:
        st.subheader("📝 名單")
        # 這裡顯示的是已經去重並排序過的名單
        edited = st.text_area("管理", value="\n".join(st.session_state.player_list), height=250)
        if st.button("🔄 同步修改", use_container_width=True):
            # 萬一手動編輯有重複，存檔時再做一次去重
            new_list = [n.strip() for n in edited.split("\n") if n.strip()]
            st.session_state.player_list = sorted(list(set(new_list)))
            st.rerun()
        st.success(f"人數：{len(st.session_state.player_list)}")