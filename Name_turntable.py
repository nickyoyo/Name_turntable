import streamlit as st
import easyocr
import numpy as np
import cv2
from PIL import Image
import json
import base64
from io import BytesIO

# --- 1. 頁面設定 ---
st.set_page_config(page_title="專業 OCR 抽獎輪盤", layout="wide", page_icon="🎡")

# --- 2. OCR 邏輯與優化函式 ---
@st.cache_resource
def load_reader():
    # 載入英文與繁體中文模型
    return easyocr.Reader(['en', 'ch_tra'], gpu=False)

def advanced_name_fix(name):
    """針對特定辨識錯誤進行手動修正字典"""
    corrections = {
        "H[729": "JHE729",
        "J|[729": "JHE729",
        "J/729": "JHE729",
        "alan10002o1": "alan1000201",
        "laciiba1": "Tachiba7",
        "Iiiabc": "liiabc",
        "Ifal": "",  # 排除雜訊
    }
    # 先做精確匹配修正
    fixed_name = corrections.get(name, name)
    
    # 模糊邏輯：針對結尾有 729 且開頭辨識不全的情況
    if "729" in fixed_name and not fixed_name.startswith("JHE"):
        return "JHE729"
        
    return fixed_name

reader = load_reader()

def run_ocr(uploaded_files):
    """執行 OCR：包含圖像預處理與白名單過濾，並覆蓋舊名單"""
    if not uploaded_files:
        st.warning("請先選取圖片！")
        return
    
    all_new_names = []
    # 設定白名單：只允許英文、數字、底線與連字號，過濾掉 [ ] | 等符號
    allow_chars = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_-'
    
    with st.spinner("正在辨識圖片中 (包含二值化預處理)..."):
        for file in uploaded_files:
            img = Image.open(file)
            img_array = np.array(img)
            
            # --- 圖像預處理 (Pre-processing) ---
            # 1. 轉灰階
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            
            # 2. 二值化 (Otsu's Binarization)
            # 讓文字變純白、背景變純黑，消除血條背景顏色干擾
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # 辨識處理後的圖片
            results = reader.readtext(binary, allowlist=allow_chars)
            
            for (_, text, prob) in results:
                # 過濾太短的字串或信心值過低的結果
                if len(text) > 2 and prob > 0.15:
                    fixed = advanced_name_fix(text.strip())
                    if fixed: # 排除空字串
                        all_new_names.append(fixed)
    
    # 核心邏輯：先清空再新增 (透過 list(set()) 去重並排序)
    st.session_state.player_list = sorted(list(set(all_new_names)))
    st.success(f"辨識完成！目前名單共有 {len(st.session_state.player_list)} 人。")

# --- 3. 狀態初始化 ---
if 'player_list' not in st.session_state:
    st.session_state.player_list = []

# --- 4. 輪盤 HTML 生成函式 ---
def get_wheel_html(size_px="450"):
    display_list = st.session_state.player_list if st.session_state.player_list else ["請先掃描名單"]
    json_list = json.dumps(display_list)
    
    # 計算半徑與圓心
    r = int(int(size_px) / 2)
    
    return f"""
    <div style="display: flex; flex-direction: column; align-items: center; font-family: 'Microsoft JhengHei', sans-serif;">
        <div id="container" style="position: relative;">
            <canvas id="wheel" width="{size_px}" height="{size_px}" style="border: 5px solid #333; border-radius: 50%; box-shadow: 0 4px 15px rgba(0,0,0,0.2);"></canvas>
            <div id="pointer" style="position: absolute; top: -15px; left: 50%; transform: translateX(-50%); width: 0; height: 0; border-left: 18px solid transparent; border-right: 18px solid transparent; border-top: 35px solid #333; z-index: 10;"></div>
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
        if (segments.length <= 1 && segments[0] === "請先掃描名單") return;
        spinBtn.disabled = true;
        const display = window.parent.document.querySelector("#winner_box");
        if(display) display.style.display = "none";

        const startTime = Date.now(); 
        const duration = 5000; // 旋轉 5 秒
        const minRounds = 8;   // 旋轉 8 圈
        const totalRotation = (minRounds * 360) + Math.random() * 360; 
        const startAngle = currentAngle;

        function animate() {{
            const elapsed = Date.now() - startTime;
            const fraction = elapsed / duration;
            if (fraction < 1) {{
                const easeOut = 1 - Math.pow(1 - fraction, 4); // 減速曲線
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

# --- 5. 主介面渲染邏輯 ---
st.sidebar.title("⚙️ 系統設定")
view_mode = st.sidebar.radio("顯示模式", ["電腦網頁版", "手機行動版"])

if view_mode == "電腦網頁版":
    col_left, col_mid, col_right = st.columns([1.2, 2.5, 1.2])
    
    with col_left:
        st.subheader("📸 1. 上傳名單")
        files = st.file_uploader("選取圖片", accept_multiple_files=True, key="pc_up")
        if st.button("🔍 開始辨識 (清空並更新)", use_container_width=True, type="primary"):
            run_ocr(files)
            st.rerun()
            
    with col_mid:
        st.subheader("🎡 2. 抽獎轉盤")
        st.components.v1.html(get_wheel_html("450"), height=620)
        
    with col_right:
        st.subheader("📝 3. 名單管理")
        st.info(f"當前人數：{len(st.session_state.player_list)}")
        edited = st.text_area("辨識結果 (可手動修改)", value="\n".join(st.session_state.player_list), height=300)
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
    # 手機版轉盤稍小一點以利顯示
    st.components.v1.html(get_wheel_html("320"), height=480)
    st.markdown('<div id="winner_box" style="display:none; background:#ffff00; padding:15px; font-weight:bold; text-align:center; border:4px solid #ff4b4b; border-radius:10px; font-size:20px; margin: 10px 0;"></div>', unsafe_allow_html=True)

    with st.expander("📝 3. 名單管理"):
        st.write(f"當前人數：{len(st.session_state.player_list)}")
        edited = st.text_area("手動編輯名單", value="\n".join(st.session_state.player_list), height=250)
        if st.button("🔄 更新轉盤名單", use_container_width=True):
            st.session_state.player_list = sorted(list(set([n.strip() for n in edited.split("\n") if n.strip()])))
            st.rerun()