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
st.set_page_config(page_title="終極 OCR 抽獎轉盤 (精準校正版)", layout="wide", page_icon="🎡")

# --- 2. 核心 OCR 與智慧過濾邏輯 ---
@st.cache_resource
def load_reader():
    # 強制只辨識英文與數字，降低混淆率
    return easyocr.Reader(['en'], gpu=False)

def advanced_fuzzy_merge(name_list, threshold=0.65):
    """
    智慧合併：解決 alan1000201 與 alanl0002Ol 這種微小辨識誤差。
    threshold 設為 0.65 代表相似度超過 65% 就判定為同一人。
    """
    if not name_list: return []
    
    # 第一步：物理校正 (針對你提到的誤差進行強力替換)
    cleaned = []
    for n in name_list:
        c = n.strip()
        # 處理數字 0 與字母 O/o 的混淆
        c = c.replace('l000', '1000').replace('0Ol', '001').replace('2Ol', '201')
        # 處理常見字首混淆
        if c.startswith('dlan'): c = 'alan' + c[4:]
        if c.startswith('nKal'): c = 'Ikal'
        # 處理已知 ID
        corrections = {
            "arshedAtcz": "TarnishedArct",
            "TartshedAttt": "TarnishedArct",
            "lifabc": "liiabc",
            "Iabc": "Iiiabc",
            "Nerveogu3": "Nerve0903",
            "Tachibat": "Tachiba7",
            "Senbeinlguc": "Senbeimiguc"
        }
        c = corrections.get(c, c)
        if len(c) >= 3: cleaned.append(c)
    
    # 第二步：模糊比對去重
    unique_names = []
    # 依長度排序，優先保留長度較完整的名字
    for name in sorted(list(set(cleaned)), key=len, reverse=True):
        is_duplicate = False
        for existing in unique_names:
            similarity = difflib.SequenceMatcher(None, name.lower(), existing.lower()).ratio()
            if similarity >= threshold:
                is_duplicate = True
                break
        if not is_duplicate:
            unique_names.append(name)
            
    return sorted(unique_names)

reader = load_reader()

def run_ocr(uploaded_file):
    if not uploaded_file: return
    
    raw_results = []
    allow_chars = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_-'
    
    with st.spinner("深度辨識中..."):
        img = Image.open(uploaded_file)
        # 固定寬度以維持辨識品質
        if img.width > 1100:
            img = img.resize((1100, int(img.height * (1100/img.width))), Image.Resampling.LANCZOS)
        
        img_array = np.array(img)
        h, w, _ = img_array.shape
        # 裁切左側 55% 區塊
        roi = img_array[:, :int(w * 0.55)]
        
        # 預處理：強化對比
        gray = cv2.cvtColor(roi, cv2.COLOR_RGB2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        enhanced = clahe.apply(gray)
        
        # 進行辨識
        results = reader.readtext(enhanced, allowlist=allow_chars, mag_ratio=1.2)
        for (_, text, prob) in results:
            if len(text) >= 3:
                raw_results.append(text.strip())
        
        # 執行智慧校正與合併
        st.session_state.player_list = advanced_fuzzy_merge(raw_results)
    
    st.success(f"辨識完成！已自動合併相似項，共 {len(st.session_state.player_list)} 人。")

# --- 3. 初始化 ---
if 'player_list' not in st.session_state:
    st.session_state.player_list = []

# --- 4. 輪盤 HTML (動畫優化) ---
def get_wheel_html(size_px="450"):
    display_list = st.session_state.player_list if st.session_state.player_list else ["無名單"]
    json_list = json.dumps(display_list)
    return f"""
    <div style="display: flex; flex-direction: column; align-items: center; font-family: sans-serif;">
        <div style="position: relative; width: {size_px}px; height: {size_px}px;">
            <canvas id="wheel" width="{size_px}" height="{size_px}" style="border-radius: 50%; border: 6px solid #333;"></canvas>
            <div style="position: absolute; top: -12px; left: 50%; transform: translateX(-50%); width: 0; height: 0; border-left: 18px solid transparent; border-right: 18px solid transparent; border-top: 28px solid #333; z-index: 10;"></div>
        </div>
        <button id="spinBtn" style="margin-top: 25px; padding: 15px 80px; font-size: 26px; background: #E63946; color: white; border: none; border-radius: 50px; cursor: pointer; font-weight: bold; box-shadow: 0 5px 15px rgba(0,0,0,0.2);">SPIN!</button>
    </div>
    <script>
    const names = {json_list};
    const canvas = document.getElementById('wheel');
    const ctx = canvas.getContext('2d');
    const spinBtn = document.getElementById('spinBtn');
    let angle = 0;
    const colors = names.map((_, i) => `hsl(${{i * 360 / names.length}}, 75%, 55%)`);

    function draw() {{
        const r = canvas.width / 2;
        const arc = 2 * Math.PI / names.length;
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        names.forEach((name, i) => {{
            ctx.fillStyle = colors[i];
            ctx.beginPath(); ctx.moveTo(r, r); ctx.arc(r, r, r, angle + i * arc, angle + (i+1) * arc); ctx.fill();
            ctx.strokeStyle = "rgba(255,255,255,0.3)"; ctx.stroke();
            ctx.save(); ctx.fillStyle = "white"; ctx.translate(r, r); ctx.rotate(angle + i * arc + arc/2);
            ctx.textAlign = "right"; ctx.font = "bold 13px Arial"; ctx.fillText(name, r - 15, 5); ctx.restore();
        }});
    }}

    spinBtn.onclick = () => {{
        if(names[0] === "無名單") return;
        spinBtn.disabled = true;
        const duration = 5000;
        const start = Date.now();
        const totalRot = (12 * 360) + Math.random() * 360; // 旋轉 12 圈以上
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
                const res = window.parent.document.getElementById("res_win");
                if(res) {{
                    res.innerHTML = "🎊 恭喜中獎： " + winner + " 🎊";
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
c1, c2, c3 = st.columns([1.2, 2, 1.2])

with c1:
    st.subheader("📸 1. 上傳截圖")
    file = st.file_uploader("請拖入遊戲圖片", type=["png", "jpg", "jpeg"])
    
    if file:
        # 縮小預覽圖顯示
        img_preview = Image.open(file)
        buffered = BytesIO()
        img_preview.save(buffered, format="PNG")
        img_b64 = base64.b64encode(buffered.getvalue()).decode()
        
        st.markdown(
            f'''<div style="height: 180px; overflow: auto; border: 2px solid #ddd; border-radius: 10px; margin-bottom: 10px; background: #f0f0f0; text-align: center;">
                <img src="data:image/png;base64,{img_b64}" style="max-width: 100%;">
            </div>''', unsafe_allow_html=True
        )
        
        if st.button("🔍 辨識名單", type="primary", use_container_width=True):
            run_ocr(file)
            st.rerun()

with c2:
    st.subheader("🎡 2. 幸運大轉盤")
    st.components.v1.html(get_wheel_html(420), height=580)
    st.markdown('<div id="res_win" style="display:none; background:#ffffcc; padding:20px; border:4px solid #ffcc00; border-radius:15px; text-align:center; font-size:28px; font-weight:bold; color: #d63031; margin-top:-20px;"></div>', unsafe_allow_html=True)

with c3:
    st.subheader("📝 3. 名單與手動修正")
    st.write(f"當前人數：**{len(st.session_state.player_list)}**")
    new_txt = st.text_area("編輯區 (每一行一個名字)", value="\n".join(st.session_state.player_list), height=400)
    if st.button("🔄 更新轉盤", use_container_width=True):
        st.session_state.player_list = [n.strip() for n in new_txt.split("\n") if n.strip()]
        st.rerun()