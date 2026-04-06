import streamlit as st
import easyocr
import numpy as np
import cv2
from PIL import Image
import json

# 頁面設定
st.set_page_config(page_title="遊戲抽獎輪盤 Pro", layout="wide", page_icon="🎡")

# --- 1. OCR 邏輯 ---
@st.cache_resource
def load_reader():
    return easyocr.Reader(['en', 'ch_tra'], gpu=False)

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

# --- 2. 界面佈局 ---
st.title("🎡 實體旋轉抽獎輪盤 (5秒/8圈)")

if 'player_list' not in st.session_state:
    st.session_state.player_list = ["玩家1", "玩家2", "玩家3", "玩家4", "玩家5", "玩家6"]

# 再次調整比例，左邊縮小到 0.7，右邊放大到 2.3
col_file, col_wheel = st.columns([0.7, 2.3])

with col_file:
    st.subheader("📝 步驟一：圖片辨識")
    uploaded_file = st.file_uploader("上傳截圖", type=["jpg", "png", "jpeg"], help="上傳包含玩家名單的遊戲截圖")
    
    if uploaded_file:
        img = Image.open(uploaded_file)
        
        # 關鍵修改 1：再次縮小預覽圖寬度至 200，並加入邊框與圓角美化
        st.markdown(
            f'<div style="text-align: left; margin: 10px 0;">'
            f'<img src="data:image/png;base64,{st.session_state.get("prev_img_base64") if "prev_img_base64" in st.session_state else ""}"'
            f'style="width: 200px; max-width: 200px; border: 2px solid #e6e6e6; border-radius: 8px; box-shadow: 2px 2px 8px rgba(0,0,0,0.1);">'
            f'</div>',
            unsafe_allow_html=True
        )
        # 用於 Streamlit 的一般預覽
        st.image(img, caption="截圖縮圖", width=200) 
        
        if st.button("🔍 執行 OCR 辨識名單", use_container_width=True):
            with st.spinner("正在掃描並修正名單..."):
                img_array = np.array(img)
                gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
                results = reader.readtext(gray)
                
                # 執行 OCR 並執行已知錯誤替換邏輯
                names = []
                for (bbox, text, prob) in results:
                    if len(text) > 1 and prob > 0.2:
                        fixed_name = advanced_name_fix(text)
                        names.append(fixed_name)
                
                if names:
                    # 去重並排序
                    st.session_state.player_list = sorted(list(set(names)))
                    st.success(f"成功辨識到 {len(st.session_state.player_list)} 位玩家！")
                    st.rerun() # 自動重新整理以更新轉盤
                else:
                    st.error("未能辨識到名字，請更換截圖。")
    
    st.divider()
    # 文字編輯區保持不變
    edited_names = st.text_area("✍️ 手動編輯名單 (每行一個)", value="\n".join(st.session_state.player_list), height=200)
    current_list = [n.strip() for n in edited_names.split("\n") if n.strip()]
    if st.button("🎯 同步名單至轉盤", use_container_width=True):
        st.session_state.player_list = current_list

# --- 3. JavaScript 轉盤組件 (強化動畫邏輯：5秒8圈) ---
with col_wheel:
    st.subheader("🎡 步驟二：點擊 SPING! 抽獎")
    json_list = json.dumps(st.session_state.player_list)

    wheel_html = f"""
    <div style="display: flex; flex-direction: column; align-items: center; font-family: 'Microsoft JhengHei', sans-serif;">
        <div id="container" style="position: relative; margin-top: 10px;">
            <canvas id="wheel" width="500" height="500" style="border: 5px solid #333; border-radius: 50%; box-shadow: 0 10px 30px rgba(0,0,0,0.1);"></canvas>
            <div id="pointer" style="position: absolute; top: -15px; left: 50%; transform: translateX(-50%); width: 0; height: 0; border-left: 18px solid transparent; border-right: 18px solid transparent; border-top: 35px solid #333; z-index: 10;"></div>
        </div>
        <button id="spinBtn" style="margin-top: 30px; padding: 12px 70px; font-size: 24px; background: #ff4b4b; color: white; border: none; border-radius: 50px; cursor: pointer; font-weight: bold; transition: 0.3s; box-shadow: 0 4px 10px rgba(0,0,0,0.2);">SPIN! 旋轉</button>
        
        <div id="resultModal" style="margin-top: 25px; text-align: center; display: none; animation: fadeIn 0.5s;">
            <h1 style="color: #ff4b4b; font-size: 42px; margin-bottom: 5px;">🎊 WINNER! 🎊</h1>
            <div id="winnerName" style="font-size: 34px; font-weight: bold; background: #ffff00; padding: 12px 35px; border-radius: 10px; display: inline-block; box-shadow: 0 4px 10px rgba(0,0,0,0.1);"></div>
        </div>
    </div>

    <style>
    @keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(-10px); }} to {{ opacity: 1; transform: translateY(0); }} }}
    #spinBtn:hover {{ background: #cc3333; transform: scale(1.05); }}
    #spinBtn:disabled {{ background: #ccc; cursor: not-allowed; }}
    </style>

    <script>
    const segments = {json_list};
    const canvas = document.getElementById('wheel');
    const ctx = canvas.getContext('2d');
    const spinBtn = document.getElementById('spinBtn');
    const resultModal = document.getElementById('resultModal');
    const winnerName = document.getElementById('winnerName');

    let currentAngle = 0;
    // 預先為不同段落上色 (HSL 自動配色)
    const colors = segments.map((_, i) => `hsl(${{(i * 360 / segments.length)}}, 75%, 60%)`);

    function drawWheel() {{
        const radius = 250;
        const arc = 2 * Math.PI / segments.length;
        ctx.clearRect(0, 0, 500, 500);

        segments.forEach((text, i) => {{
            const angle = currentAngle + i * arc;
            ctx.fillStyle = colors[i];
            ctx.beginPath();
            ctx.moveTo(250, 250);
            ctx.arc(250, 250, radius, angle, angle + arc);
            ctx.fill();
            ctx.strokeStyle = "white";
            ctx.lineWidth = 2;
            ctx.stroke();

            // 繪製文字 (逆時針，頂部對齊)
            ctx.save();
            ctx.fillStyle = "white";
            ctx.translate(250, 250);
            ctx.rotate(angle + arc / 2);
            ctx.textAlign = "right";
            ctx.font = "bold 19px Arial";
            ctx.fillText(text, 235, 10);
            ctx.restore();
        }});
    }}

    function spin() {{
        if (segments.length === 0) return;
        spinBtn.disabled = true;
        resultModal.style.display = "none";
        spinBtn.innerText = "🎲 旋轉中...";
        
        const startTime = Date.now();
        // 關鍵修改 2：旋轉時間延長至 5000 毫秒 (5秒)
        const duration = 5000; 
        // 關鍵修改 3：恆定轉動圈數增加至 8 圈
        const minRounds = 8;   
        // 總旋轉度數 = (8圈 * 360) + 最後停留的隨機角度
        const totalRotation = (minRounds * 360) + Math.random() * 360; 
        const startAngle = currentAngle;

        function animate() {{
            const now = Date.now();
            const elapsed = now - startTime;
            const fraction = elapsed / duration; // 動畫進度 (0 到 1)

            if (fraction < 1) {{
                // 使用 Cubic Ease-Out 減速曲線，讓前 4 秒保持高速，最後 1 秒緩緩停下
                const easeOut = 1 - Math.pow(1 - fraction, 3); 
                // 角度公式：起始角度 + (進度比例 * 總度數 * 弧度)
                const moveAngle = easeOut * totalRotation * (Math.PI / 180);
                currentAngle = startAngle + moveAngle;
                drawWheel();
                // 請求下一影格繼續動畫
                requestAnimationFrame(animate);
            }} else {{
                finishSpin(); // 動畫結束
            }}
        }}
        // 開始動畫循環
        requestAnimationFrame(animate);
    }}

    function finishSpin() {{
        spinBtn.disabled = false;
        spinBtn.innerText = "SPIN! 再抽一次";
        
        // 計算指向頂端指針（-90度或 270度位置）的中獎者
        const totalSegments = segments.length;
        const normalizedAngle = (currentAngle * 180 / Math.PI) % 360;
        const sliceSize = 360 / totalSegments;
        
        // 角度判定邏輯：(360 - ( normalizedAngle % 360 )) / sliceSize
        const index = Math.floor((360 - (normalizedAngle % 360)) / sliceSize) % totalSegments;
        
        // 顯示結果
        winnerName.innerText = segments[index];
        resultModal.style.display = "block";
    }}

    // 按鈕點擊事件監聽
    spinBtn.addEventListener('click', spin);
    // 頁面載入時先繪製一次靜態轉盤
    drawWheel();
    </script>
    """
    # 內嵌 HTML/JS 到 Streamlit 中
    import streamlit.components.v1 as components
    components.html(wheel_html, height=780)