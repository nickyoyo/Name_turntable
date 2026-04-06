import streamlit as st
import easyocr
import numpy as np
import cv2
from PIL import Image
import json
import base64
from io import BytesIO

# --- 1. 頁面設定 ---
st.set_page_config(page_title="專業級 OCR 抽獎輪盤 (強化辨識)", layout="wide", page_icon="🎡")

# --- 2. OCR 核心與色彩過濾優化邏輯 ---
@st.cache_resource
def load_reader():
    # 載入模型 (GPU=False 為使用 CPU，若有 GPU 可設為 True)
    return easyocr.Reader(['en', 'ch_tra'], gpu=False)

def advanced_name_fix(name):
    """人工容錯字典：修正遊戲 ID 常見混淆字"""
    corrections = {
        # 通用混淆 (I/l, 0/o)
        "Iiiabc": "liiabc",
        "liabc": "liiabc", # 修正漏字
        "Iliiabc": "liiabc",
        "alan10002o1": "alan1000201",
        "alan1OOO2O1": "alan1000201", # 修正字母 O
        "BobCC": "Bobcc",
        
        # 圖片辨識到的特定雜訊
        "GaHid1": "", # 排除雜訊
        "T3b": "",   # 排除雜訊
        
        # 圖片中可能的嚴重混淆 (若經過優化後仍出錯可啟用)
        # "H[729": "JHE729",
        # "laciiba1": "Tachiba7",
    }
    
    # 模糊匹配邏輯 (結尾有 729 且開頭辨識不清的情況)
    if "729" in name and not name.startswith("JHE") and len(name) > 3:
        fixed = corrections.get(name, "JHE729")
    else:
        fixed = corrections.get(name, name)
        
    return fixed

reader = load_reader()

def optimize_image_for_white_text_on_red(img_array):
    """【核心優化】色彩過濾：將紅色血條背景變白，強化白字對比"""
    # 1. 轉換色彩空間 RGB -> HSV
    hsv = cv2.cvtColor(img_array, cv2.COLOR_RGB2HSV)

    # 2. 定義紅色的 HSV 範圍 (紅色在 HSV 中有兩個區域)
    # 區域 1: 接近 0 的紅色
    lower_red1 = np.array([0, 70, 50])
    upper_red1 = np.array([10, 255, 255])
    # 區域 2: 接近 180 的紅色
    lower_red2 = np.array([170, 70, 50])
    upper_red2 = np.array([180, 255, 255])

    # 3. 建立遮罩 (這會選取圖片中的所有紅色區域)
    mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
    mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
    red_mask = cv2.bitwise_or(mask1, mask2)

    # 4. 色彩過濾：將遮罩範圍內的紅色區域直接變為純白色
    # 這樣原本紅底白字的文字，背景變成了白色，字依然是白色（但 OCR 可辨識其邊緣）
    filtered_img = img_array.copy()
    filtered_img[red_mask > 0] = [255, 255, 255] # 將紅底設為白底

    # 5. 轉換處理後的圖片為灰階
    gray = cv2.cvtColor(filtered_img, cv2.COLOR_RGB2GRAY)

    # 6. 二值化：將圖片轉為黑白，極大化文字對比度
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # [可選 debug 功能] 若想看處理後的圖片，取消註釋下方一行 (只在本地測試有效)
    # cv2.imwrite('debug_processed.png', binary)
    
    return binary

def run_ocr(uploaded_files):
    """辨識圖片並覆蓋舊名單 (含色彩優化與速度優化)"""
    if not uploaded_files:
        st.warning("請先選取圖片！")
        return
    
    all_new_names = []
    # 白名單：排除 [ ] | / 等干擾符號
    allow_chars = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_-'
    
    # 顯示辨識進度框
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    with st.spinner("正在辨識中 (正在套用紅色色彩過濾以優化辨識)..."):
        for i, file in enumerate(uploaded_files):
            # 讀取圖片
            img = Image.open(file)
            
            # --- 速度優化：縮小圖片尺寸 ---
            # 遊戲 ID 不需要極高解析度，縮小寬度可大幅提升運算速度
            max_width = 1000
            if img.width > max_width:
                w_percent = (max_width / float(img.width))
                h_size = int((float(img.height) * float(w_percent)))
                img = img.resize((max_width, h_size), Image.Resampling.LANCZOS)
            
            img_array = np.array(img)
            
            # ---【核心核心核心】呼叫強化的圖像預處理函式 ---
            # 這個步驟會將原本的紅底白字處理成 OCR 極易辨識的黑底白字或黑白分明圖
            optimized_img = optimize_image_for_white_text_on_red(img_array)
            
            # 執行辨識 (優化參數：mag_ratio=1.0 省去額外放大的時間)
            results = reader.readtext(optimized_img, allowlist=allow_chars, mag_ratio=1.0)
            
            # 整理結果
            for (_, text, prob) in results:
                # 過濾信心值過低或過短的字串
                if len(text) > 3 and prob > 0.15:
                    fixed = advanced_name_fix(text.strip())
                    if fixed: # 排除空字串（如雜訊已被 corrections 設為空）
                        all_new_names.append(fixed)
            
            # 更新進度條
            progress_bar.progress((i + 1) / len(uploaded_files))
            status_text.text(f"已辨識完第 {i+1} 張圖片")
    
    # 清空進度提示
    progress_bar.empty()
    status_text.empty()
    
    # 核心邏輯：按下辨識即覆蓋舊名單 (去重並排序)
    st.session_state.player_list = sorted(list(set(all_new_names)))
    st.success(f"辨識完成！目前名單共有 {len(st.session_state.player_list)} 人。")

# --- 3. 狀態初始化 ---
if 'player_list' not in st.session_state:
    st.session_state.player_list = []

# --- 4. 輪盤 HTML 元件 (維持不變) ---
def get_wheel_html(size_px="450"):
    display_list = st.session_state.player_list if st.session_state.player_list else ["請先辨識名單"]
    json_list = json.dumps(display_list)
    r = int(int(size_px) / 2)
    return f"""
    <div style="display: flex; flex-direction: column; align-items: center; font-family: sans-serif;">
        <div id="container" style="position: relative;">
            <canvas id="wheel" width="{size_px}" height="{size_px}" style="border: 5px solid #333; border-radius: 50%; box-shadow: 0 4px 15px rgba(0,0,0,0.2);"></canvas>
            <div id="pointer" style="position: absolute; top: -15px; left: 50%; transform: translateX(-50%); width: 0; height: 0; border-left: 18px solid transparent; border-right: 18px solid transparent; border-top: 30px solid #333; z-index: 10;"></div>
        </div>
        <button id="spinBtn" style="margin-top: 25px; padding: 15px 70px; font-size: 24px; background: linear-gradient(135deg, #ff4b4b, #ff7676); color: white; border: none; border-radius: 50px; cursor: pointer; font-weight: bold; box-shadow: 0 4px 10px rgba(255,75,75,0.3);">SPIN! 抽獎</button>
    </div>
    <script>
    const segments = {json_list};
    const canvas = document.getElementById('wheel');
    const ctx = canvas.getContext('2d');
    const spinBtn = document.getElementById('spinBtn');
    let currentAngle = 0;
    const colors = segments.map((_, i) => `hsl(${{(i * 360 / segments.length)}}, 70%, 60%)`);
    function drawWheel() {{
        const r = {r};
        const arc = 2 * Math.PI / segments.length;
        ctx.clearRect(0, 0, {size_px}, {size_px});
        segments.forEach((text, i) => {{
            const angle = currentAngle + i * arc;
            ctx.fillStyle = colors[i];
            ctx.beginPath(); ctx.moveTo(r, r); ctx.arc(r, r, r, angle, angle + arc); ctx.fill();
            ctx.strokeStyle = "rgba(255,255,255,0.5)"; ctx.lineWidth = 2; ctx.stroke();
            ctx.save(); ctx.fillStyle = "white"; ctx.translate(r, r); ctx.rotate(angle + arc / 2);
            ctx.textAlign = "right"; ctx.font = "bold 14px Arial"; ctx.fillText(text, r - 20, 7); ctx.restore();
        }});
    }}
    spinBtn.addEventListener('click', () => {{
        if (segments.length <= 1 && segments[0] === "請先辨識名單") return;
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
                const easeOut = 1 - Math.pow(1 - fraction, 4); 
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
                    display.innerHTML = "<div style='font-size:16px; color:#555;'>WINNER</div><div style='color:#ff4b4b;'>🎊 " + winner + " 🎊</div>";
                    display.style.display = "block";
                }}
            }}
        }}
        requestAnimationFrame(animate);
    }});
    drawWheel();
    </script>
    """

# --- 5. 介面佈局 (維持不變) ---
st.sidebar.title("⚙️ 系統設定")
view_mode = st.sidebar.radio("顯示模式", ["電腦網頁版", "手機行動版"])

if view_mode == "電腦網頁版":
    col_left, col_mid, col_right = st.columns([1.2, 2.5, 1.2])
    with col_left:
        st.subheader("📸 1. 上傳截圖")
        files = st.file_uploader("選取圖片", accept_multiple_files=True, key="pc_up")
        if st.button("🔍 開始辨識全部 (覆蓋舊名單)", use_container_width=True, type="primary"):
            run_ocr(files)
            st.rerun()
    with col_mid:
        st.subheader("🎡 2. 抽獎轉盤")
        st.components.v1.html(get_wheel_html("450"), height=620)
    with col_right:
        st.subheader("📝 3. 名單管理")
        st.info(f"當前人數：{len(st.session_state.player_list)}")
        edited = st.text_area("編輯區 (手動刪除雜訊)", value="\n".join(st.session_state.player_list), height=300)
        if st.button("🔄 同步至轉盤", use_container_width=True):
            st.session_state.player_list = sorted(list(set([n.strip() for n in edited.split("\n") if n.strip()])))
            st.rerun()
        st.markdown('<div id="winner_box" style="display:none; background:#ffff00; padding:20px; font-weight:bold; text-align:center; border:4px solid #ff4b4b; border-radius:12px; font-size:24px; margin-top:15px; box-shadow: 0 4px 10px rgba(0,0,0,0.1);"></div>', unsafe_allow_html=True)
else:
    # 手機行動版佈局
    st.title("🎡 行動抽獎系統")
    with st.expander("📸 1. 上傳與辨識", expanded=(len(st.session_state.player_list) == 0)):
        files = st.file_uploader("選取截圖", accept_multiple_files=True, key="mob_up")
        if st.button("🔍 執行辨識", use_container_width=True, type="primary"):
            run_ocr(files)
            st.rerun()
    st.subheader("🎯 2. 旋轉抽獎")
    st.components.v1.html(get_wheel_html("320"), height=480)
    st.markdown('<div id="winner_box" style="display:none; background:#ffff00; padding:15px; font-weight:bold; text-align:center; border:4px solid #ff4b4b; border-radius:10px; font-size:20px; margin: 10px 0;"></div>', unsafe_allow_html=True)
    with st.expander("📝 3. 名單管理"):
        st.write(f"當前人數：{len(st.session_state.player_list)}")
        edited = st.text_area("手動編輯名單", value="\n".join(st.session_state.player_list), height=250)
        if st.button("🔄 更新轉盤名單", use_container_width=True):
            st.session_state.player_list = sorted(list(set([n.strip() for n in edited.split("\n") if n.strip()])))
            st.rerun()