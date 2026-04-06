import streamlit as st
import easyocr
import numpy as np
import cv2
from PIL import Image
import json
import base64
import difflib
from io import BytesIO

# --- 1. 頁面設定 ---
st.set_page_config(page_title="極速 OCR 抽獎輪盤 (精準校對版)", layout="wide", page_icon="🎡")

# --- 2. 核心邏輯：辨識與模糊校對 ---
@st.cache_resource
def load_reader():
    return easyocr.Reader(['en'], gpu=False)

def fuzzy_merge(name_list, threshold=0.75):
    """模糊合併：解決 alan1000201 與 alanl000201 這種微小辨識誤差"""
    if not name_list: return []
    unique_names = []
    # 由長到短排序，優先保留完整的名字
    for name in sorted(list(set(name_list)), key=len, reverse=True):
        is_duplicate = False
        for existing in unique_names:
            # 計算字串相似度
            similarity = difflib.SequenceMatcher(None, name, existing).ratio()
            if similarity >= threshold:
                is_duplicate = True
                break
        if not is_duplicate:
            unique_names.append(name)
    return sorted(unique_names)

def advanced_name_fix(name):
    """針對特定誤差的硬規則修正"""
    # 移除 ID 以外的雜字
    name = "".join([c for c in name if c.isalnum() or c in "_-"])
    
    # 常見字元錯誤替換 (I/l/1, o/0)
    # 這裡不強行替換，交給後面的模糊匹配處理更靈活
    
    corrections = {
        "arshedAtcz": "TarnishedArct",
        "lifabc": "liiabc",
        "Earydy": "Eazydy",
        "GaHid1": "",
        "T3b": ""
    }
    
    fixed = corrections.get(name, name)
    
    # 處理 JHE729 碎塊
    if "729" in fixed and not fixed.startswith("JHE") and len(fixed) < 10:
        return "JHE729"
    
    return fixed if len(fixed) >= 3 else ""

reader = load_reader()

def run_ocr(uploaded_file):
    if not uploaded_file: return
    
    raw_results = []
    allow_chars = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_-'
    
    with st.spinner("深度辨識與智慧校對中..."):
        img = Image.open(uploaded_file)
        # 優化辨識尺寸
        if img.width > 1100:
            img = img.resize((1100, int(img.height * (1100/img.width))), Image.Resampling.LANCZOS)
        
        img_array = np.array(img)
        h, w, _ = img_array.shape
        # 裁切左側 55% 避開右側 UI 雜訊
        roi = img_array[:, :int(w * 0.55)]
        
        # 預處理：強化對比
        gray = cv2.cvtColor(roi, cv2.COLOR_RGB2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        enhanced = clahe.apply(gray)
        
        # 雙重模式掃描
        for p_img in [enhanced, cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]]:
            results = reader.readtext(p_img, allowlist=allow_chars, mag_ratio=1.1)
            for (_, text, prob) in results:
                fixed = advanced_name_fix(text.strip())
                if fixed:
                    raw_results.append(fixed)
        
        # 執行模糊合併 (自動處理 alan1000201 / alanl000201 等)
        st.session_state.player_list = fuzzy_merge(raw_results)
    
    st.success(f"辨識完成！共 {len(st.session_state.player_list)} 位玩家。")

# --- 3. Session 狀態 ---
if 'player_list' not in st.session_state:
    st.session_state.player_list = []

# --- 4. 輪盤 HTML ---
def get_wheel_html(size_px="450"):
    display_list = st.session_state.player_list if st.session_state.player_list else ["無名單"]
    json_list = json.dumps(display_list)
    return f"""
    <div style="display: flex; flex-direction: column; align-items: center; font-family: sans-serif;">
        <div style="position: relative; width: {size_px}px; height: {size_px}px;">
            <canvas id="wheel" width="{size_px}" height="{size_px}" style="border-radius: 50%; border: 5px solid #333;"></canvas>
            <div style="position: absolute; top: -10px; left: 50%; transform: translateX(-50%); width: 0; height: 0; border-left: 15px solid transparent; border-right: 15px solid transparent; border-top: 25px solid #333; z-index: 10;"></div>
        </div>
        <button id="spinBtn" style="margin-top: 25px; padding: 15px 70px; font-size: 24px; background: #ff4b4b; color: white; border: none; border-radius: 50px; cursor: pointer; font-weight: bold; box-shadow: 0 4px 10px rgba(0,0,0,0.2);">START SPIN</button>
    </div>
    <script>
    const names = {json_list};
    const canvas = document.getElementById('wheel');
    const ctx = canvas.getContext('2d');
    const spinBtn = document.getElementById('spinBtn');
    let angle = 0;
    const colors = names.map((_, i) => `hsl(${{i * 360 / names.length}}, 70%, 60%)`);

    function draw() {{
        const r = canvas.width / 2;
        const arc = 2 * Math.PI / names.length;
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        names.forEach((name, i) => {{
            ctx.fillStyle = colors[i];
            ctx.beginPath(); ctx.moveTo(r, r); ctx.arc(r, r, r, angle + i * arc, angle + (i+1) * arc); ctx.fill();
            ctx.save(); ctx.fillStyle = "white"; ctx.translate(r, r); ctx.rotate(angle + i * arc + arc/2);
            ctx.textAlign = "right"; ctx.font = "bold 14px Arial"; ctx.fillText(name, r - 20, 6); ctx.restore();
        }});
    }}

    spinBtn.onclick = () => {{
        if(names[0] === "無名單") return;
        spinBtn.disabled = true;
        const start = Date.now();
        const duration = 5000;
        const totalRot = (10 * 360) + Math.random() * 360;
        const initialAngle = angle;
        function frame() {{
            const now = Date.now() - start;
            const t = now / duration;
            if(t < 1) {{
                angle = initialAngle + (totalRot * (1 - Math.pow(1 - t, 4)) * Math.PI / 180);
                draw(); requestAnimationFrame(frame);
            }} else {{
                spinBtn.disabled = false;
                const finalDeg = (angle * 180 / Math.PI) % 360;
                const arcDeg = 360 / names.length;
                const idx = Math.floor((360 - (finalDeg + 90) % 360) / arcDeg) % names.length;
                const winner = names[idx >= 0 ? idx : idx + names.length];
                const res = window.parent.document.getElementById("winner_box");
                if(res) {{
                    res.innerHTML = "🏆 恭喜中獎： " + winner;
                    res.style.display = "block";
                }}
            }}
        }}
        frame();
    }};
    draw();
    </script>
    """

# --- 5. 介面佈局 ---
col1, col2, col3 = st.columns([1.3, 2, 1.2])

with col1:
    st.subheader("📸 1. 上傳截圖")
    file = st.file_uploader("請選取圖片", type=["png", "jpg", "jpeg"])
    
    if file:
        # --- 預覽圖縮小優化 ---
        img_preview = Image.open(file)
        buffered = BytesIO()
        img_preview.save(buffered, format="PNG")
        img_b64 = base64.b64encode(buffered.getvalue()).decode()
        
        # 使用 HTML 限制預覽圖高度為 200px，並加上捲軸
        st.markdown(
            f'''<div style="height: 200px; overflow: auto; border: 1px solid #ddd; border-radius: 8px; margin-bottom: 10px; background: #eee; text-align: center;">
                <img src="data:image/png;base64,{img_b64}" style="max-width: 100%;">
            </div>''', unsafe_allow_html=True
        )
        
        if st.button("🔍 辨識並更新", type="primary", use_container_width=True):
            run_ocr(file)
            st.rerun()

with col2:
    st.subheader("🎡 2. 抽獎輪盤")
    st.components.v1.html(get_wheel_html(420), height=580)
    st.markdown('<div id="winner_box" style="display:none; background:#fff3cd; padding:15px; border:2px solid #ffeeba; border-radius:10px; text-align:center; font-size:24px; font-weight:bold; color: #856404;"></div>', unsafe_allow_html=True)

with col3:
    st.subheader("📝 3. 名單管理")
    st.info(f"人數：{len(st.session_state.player_list)}")
    new_txt = st.text_area("編輯區 (可手動校正)", value="\n".join(st.session_state.player_list), height=400)
    if st.button("🔄 同步修改"):
        st.session_state.player_list = [n.strip() for n in new_txt.split("\n") if n.strip()]
        st.rerun()