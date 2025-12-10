"""
🔐 藏圖秘語 - 方案 A：等比例縮放版
設計基準：1920×1080，所有螢幕等比例縮放
"""

import streamlit as st
import streamlit.components.v1 as components
import numpy as np
from PIL import Image, ImageDraw
import requests
from io import BytesIO
import os
import math
import time
import base64
import json
import qrcode
import html

# 延遲載入 pyzbar（較慢的套件）
@st.cache_resource
def load_pyzbar():
    from pyzbar.pyzbar import decode as decode_qr
    return decode_qr

from config import *
from embed import embed_secret
from extract import detect_and_extract
from secret_encoding import text_to_binary, image_to_binary, binary_to_image

def is_likely_garbled_text(text):
    """檢測文字是否可能是亂碼"""
    if not text or len(text) == 0:
        return True
    
    # 計算中文字符數量
    chinese_count = 0
    for char in text:
        if '\u4e00' <= char <= '\u9fff':
            chinese_count += 1
    
    # 如果超過 30% 是中文，認為是正常文字
    if (chinese_count / len(text)) > 0.3:
        return False
    
    # 計算「正常」字符的比例（字母、數字、空格、常見標點）
    normal_chars = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 \n\r\t，。！？、；：""''（）')
    normal_count = sum(1 for c in text if c in normal_chars)
    
    # 如果正常字符比例低於 70%，認為是亂碼
    if (normal_count / len(text)) < 0.7:
        return True
    
    return False

def is_likely_garbled_image(image_data):
    """檢測圖像是否可能是亂碼（雜訊圖）"""
    try:
        img = Image.open(BytesIO(image_data))
        img_array = np.array(img.convert('RGB'))
        
        # 計算相鄰像素的差異
        h_diff = np.abs(img_array[:, 1:, :].astype(int) - img_array[:, :-1, :].astype(int))
        v_diff = np.abs(img_array[1:, :, :].astype(int) - img_array[:-1, :, :].astype(int))
        
        avg_diff = (np.mean(h_diff) + np.mean(v_diff)) / 2
        
        # 正常圖片的平均差異通常 < 30，亂碼圖 > 60
        return avg_diff > 50
    except:
        return True
    
# ==================== 生成高質量圖片函數 ====================
def generate_gradient_image(size, color1, color2, direction='horizontal'):
    img = Image.new('RGB', (size, size))
    for i in range(size):
        ratio = i / size
        r = int(color1[0] + (color2[0] - color1[0]) * ratio)
        g = int(color1[1] + (color2[1] - color1[1]) * ratio)
        b = int(color1[2] + (color2[2] - color1[2]) * ratio)
        for j in range(size):
            if direction == 'horizontal':
                img.putpixel((i, j), (r, g, b))
            else:
                img.putpixel((j, i), (r, g, b))
    return img

# ==================== Icon 圖片轉 Base64 ====================
def get_icon_base64(icon_name):
    """讀取 icons 資料夾的圖片並轉成 base64"""
    icon_path = os.path.join("icons", f"{icon_name}.png")
    if os.path.exists(icon_path):
        with open(icon_path, "rb") as f:
            data = base64.b64encode(f.read()).decode()
        return f"data:image/png;base64,{data}"
    return ""

# ==================== 全局緩存 ====================
if 'embed_result' not in st.session_state:
    st.session_state.embed_result = None
if 'extract_result' not in st.session_state:
    st.session_state.extract_result = None

# ==================== 對象管理（Supabase 雲端儲存）====================
def generate_contact_key():
    """生成對象專屬密鑰（32 字元隨機字串）"""
    import secrets
    return secrets.token_hex(16)  # 32 字元的十六進位字串

def get_supabase_client():
    """取得 Supabase 客戶端"""
    try:
        from supabase import create_client
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        return None

def load_contacts():
    """從 Supabase 讀取對象資料"""
    try:
        supabase = get_supabase_client()
        if supabase:
            response = supabase.table("contacts").select("*").execute()
            contacts = {}
            for row in response.data:
                contacts[row["name"]] = {
                    "style": row["style"],
                    "key": row["key"]
                }
            return contacts
    except Exception as e:
        pass
    
    # 如果 Supabase 不可用，嘗試讀取本地 JSON（本地測試用）
    try:
        if os.path.exists("contacts.json"):
            with open("contacts.json", 'r', encoding='utf-8') as f:
                data = json.load(f)
                converted = {}
                for name, value in data.items():
                    if isinstance(value, dict):
                        converted[name] = value
                    else:
                        converted[name] = {"style": value, "key": generate_contact_key()}
                return converted
    except:
        pass
    return {}

def save_contacts(contacts):
    """儲存對象資料到 Supabase"""
    try:
        supabase = get_supabase_client()
        if supabase:
            # 先刪除所有現有資料
            supabase.table("contacts").delete().neq("name", "").execute()
            # 插入新資料
            for name, data in contacts.items():
                supabase.table("contacts").insert({
                    "name": name,
                    "style": data.get("style"),
                    "key": data.get("key")
                }).execute()
            return True
    except Exception as e:
        pass
    
    # 如果 Supabase 不可用，嘗試寫入本地 JSON
    try:
        with open("contacts.json", 'w', encoding='utf-8') as f:
            json.dump(contacts, f, ensure_ascii=False, indent=2)
    except:
        pass
    return False

def get_contact_style(contacts, name):
    """取得對象的風格"""
    if name in contacts:
        data = contacts[name]
        if isinstance(data, dict):
            return data.get("style")
        return data
    return None

def get_contact_key(contacts, name):
    """取得對象的密鑰"""
    if name in contacts:
        data = contacts[name]
        if isinstance(data, dict):
            return data.get("key")
    return None

if 'contacts' not in st.session_state:
    st.session_state.contacts = load_contacts()

# ==================== 圖片庫設定 ====================
# 風格帶編號
STYLE_CATEGORIES = {
    "1. 建築": "建築", 
    "2. 動物": "動物", 
    "3. 植物": "植物",
    "4. 食物": "食物", 
    "5. 交通": "交通",
}

# 風格編號對應表
STYLE_TO_NUM = {
    "1. 建築": 1, "2. 動物": 2, "3. 植物": 3, "4. 食物": 4, "5. 交通": 5,
    "建築": 1, "動物": 2, "植物": 3, "食物": 4, "交通": 5,
}

NUM_TO_STYLE = {1: "建築", 2: "動物", 3: "植物", 4: "食物", 5: "交通"}

AVAILABLE_SIZES = [64, 128, 256, 512, 1024, 2048, 4096]

IMAGE_LIBRARY = {
    "建築": [
        {"id": 29493117, "name": "哈里發塔"},
        {"id": 34132869, "name": "比薩斜塔"},
        {"id": 16457365, "name": "埃菲爾鐵塔"},
        {"id": 236294, "name": "聖彼得大教堂"},
        {"id": 16681013, "name": "謝赫扎耶德大清真寺"},
        {"id": 29144355, "name": "熨斗大樓"},
        {"id": 1650904, "name": "泰坦尼克博物館"},
    ],
    "動物": [
        {"id": 1108099, "name": "拉布拉多"},
        {"id": 568022, "name": "白羊"},
        {"id": 19613749, "name": "兔子"},
        {"id": 7060929, "name": "刺蝟"},
        {"id": 19597261, "name": "松鼠"},
        {"id": 10386190, "name": "梅花鹿"},
        {"id": 34954771, "name": "栗頭蜂虎"},
    ],
    "植物": [
        {"id": 1048024, "name": "仙人掌"},
        {"id": 11259955, "name": "雛菊"},
        {"id": 6830332, "name": "櫻花"},
        {"id": 7048610, "name": "鬱金香"},
        {"id": 18439973, "name": "洋牡丹"},
        {"id": 244796, "name": "木槿花"},
        {"id": 206837, "name": "勿忘我"},
    ],
    "食物": [
        {"id": 28503601, "name": "海鮮燉飯"},
        {"id": 32538755, "name": "紅醬義大利麵"},
        {"id": 1566837, "name": "比薩"},
        {"id": 7245468, "name": "壽司"},
        {"id": 4110272, "name": "水果拼盤"},
        {"id": 6441084, "name": "草莓蛋糕"},
        {"id": 7144558, "name": "鬆餅"},
    ],
    "交通": [
        {"id": 33435422, "name": "摩托車"},
        {"id": 1595483, "name": "自行車"},
        {"id": 2263673, "name": "巴士"},
        {"id": 33519108, "name": "火車"},
        {"id": 33017407, "name": "飛機"},
        {"id": 843633, "name": "遊艇"},
        {"id": 586040, "name": "火箭"},
    ],
}

def get_recommended_size(secret_bits):
    """根據機密大小推薦最小適合尺寸"""
    for size in AVAILABLE_SIZES:
        capacity = calculate_image_capacity(size)
        if capacity >= secret_bits:
            return size
    return AVAILABLE_SIZES[-1]

@st.cache_data(ttl=86400, show_spinner=False)
def download_image_cached(pexels_id, size):
    """下載並快取圖片（持久化）"""
    url = f"https://images.pexels.com/photos/{pexels_id}/pexels-photo-{pexels_id}.jpeg?auto=compress&cs=tinysrgb&w={size}&h={size}&fit=crop"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.content
    except:
        pass
    return None

def download_image_by_id(pexels_id, size):
    """下載指定 ID 和尺寸的圖片"""
    image_data = download_image_cached(pexels_id, size)
    
    if image_data:
        img = Image.open(BytesIO(image_data)).convert('RGB')
        if img.size[0] != size or img.size[1] != size:
            img = img.resize((size, size), Image.LANCZOS)
        img_gray = img.convert('L')
        return img, img_gray
    
    img = generate_gradient_image(size, (100, 150, 200), (150, 200, 250))
    return img, img.convert('L')

# ==================== 輔助函數 ====================
def calculate_image_capacity(size):
    return (size * size) // 64 * 21

def calculate_required_bits_for_image(image, target_capacity=None):
    original_size, original_mode = image.size, image.mode
    is_color = original_mode not in ['L', '1', 'LA']
    
    if not is_color:
        has_alpha = False
    elif original_mode == 'P':
        temp_img = image.convert('RGBA')
        if temp_img.mode == 'RGBA':
            alpha_channel = temp_img.split()[-1]
            has_alpha = alpha_channel.getextrema()[0] < 255
        else:
            has_alpha = False
    elif original_mode in ['RGBA', 'PA']:
        has_alpha = True
    else:
        has_alpha = False
    
    if is_color:
        header_bits = 66
        bits_per_pixel = 32 if has_alpha else 24
    else:
        header_bits, bits_per_pixel = 66, 8
    
    if target_capacity is None:
        w, h = original_size[0], original_size[1]
        return header_bits + w * h * bits_per_pixel, (w, h)
    
    max_pixels = (target_capacity - header_bits) // bits_per_pixel
    current_pixels = original_size[0] * original_size[1]
    if current_pixels <= max_pixels:
        scaled = original_size
    else:
        ratio = math.sqrt(max_pixels / current_pixels)
        scaled = (max(8, (int(original_size[0] * ratio) // 8) * 8), max(8, (int(original_size[1] * ratio) // 8) * 8))
    return header_bits + scaled[0] * scaled[1] * bits_per_pixel, scaled

# ==================== Z碼圖編碼/解碼 ====================
def encode_z_as_image_with_header(z_bits, style_num, img_num, img_size):
    """Z碼圖編碼（含風格編號、圖像編號和尺寸）"""
    length = len(z_bits)
    header_bits = [int(b) for b in format(length, '032b')]
    header_bits += [int(b) for b in format(style_num, '08b')]  # 風格編號 8 bits
    header_bits += [int(b) for b in format(img_num, '016b')]
    header_bits += [int(b) for b in format(img_size, '016b')]
    full_bits = header_bits + z_bits
    
    if len(full_bits) % 8 != 0:
        padding = 8 - (len(full_bits) % 8)
        full_bits = full_bits + [0] * padding
    
    pixels = []
    for i in range(0, len(full_bits), 8):
        byte = full_bits[i:i+8]
        pixel_value = int(''.join(map(str, byte)), 2)
        pixels.append(pixel_value)
    
    num_pixels = len(pixels)
    width = int(math.sqrt(num_pixels))
    height = math.ceil(num_pixels / width)
    
    while len(pixels) < width * height:
        pixels.append(0)
    
    image = Image.new('L', (width, height))
    image.putdata(pixels[:width * height])
    
    return image, length

def decode_image_to_z_with_header(image):
    """Z碼圖解碼（含風格編號、圖像編號和尺寸）"""
    if image.mode != 'L':
        image = image.convert('L')
    
    pixels = list(image.getdata())
    
    all_bits = []
    for pixel in pixels:
        bits = [int(b) for b in format(pixel, '08b')]
        all_bits.extend(bits)
    
    if len(all_bits) < 72:  # 32 + 8 + 16 + 16 = 72
        raise ValueError("Z碼圖格式錯誤：太小")
    
    z_length = int(''.join(map(str, all_bits[:32])), 2)
    style_num = int(''.join(map(str, all_bits[32:40])), 2)
    img_num = int(''.join(map(str, all_bits[40:56])), 2)
    img_size = int(''.join(map(str, all_bits[56:72])), 2)
    
    if z_length <= 0 or z_length > len(all_bits) - 72:
        raise ValueError(f"無效的 Z碼（長度：{z_length}）")
    
    z_bits = all_bits[72:72 + z_length]
    
    return z_bits, style_num, img_num, img_size

# ==================== Streamlit 頁面配置 ====================
st.set_page_config(page_title="🔐 高效能無載體之機密編碼技術", page_icon="🔐", layout="wide", initial_sidebar_state="collapsed")

# ==================== CSS 樣式 ====================
st.markdown("""
<style>
/* 背景圖片 */
.stApp {
    background-image: url('https://i.pinimg.com/736x/53/1a/01/531a01457eca178f01c83ac2ede3f102.jpg');
    background-size: 100% 100%;
    background-position: center;
    background-repeat: no-repeat;
    background-attachment: fixed;
}

/* 隱藏 Streamlit 預設元素 */
header[data-testid="stHeader"],
#MainMenu, footer, .stDeployButton, div[data-testid="stToolbar"],
.viewerBadge_container__r5tak, .viewerBadge_link__qRIco,
div[class*="viewerBadge"], div[class*="StatusWidget"],
[data-testid="manage-app-button"], .stApp > footer,
iframe[title="Streamlit"], div[class*="styles_viewerBadge"],
.stAppDeployButton, section[data-testid="stStatusWidget"] {
    display: none !important;
    visibility: hidden !important;
}

.block-container { padding-top: 1rem !important; }

/* 隱藏側邊欄控制按鈕 */
button[data-testid="collapsedControl"],
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapsedControl"],
button[data-testid="baseButton-header"],
[data-testid="stSidebarNavCollapseIcon"],
[data-testid="stSidebar"] > button,
[data-testid="stSidebarNav"] button,
[data-testid="stSidebarNavSeparator"],
[data-testid="stSidebarCollapseButton"],
section[data-testid="stSidebar"] > div > button,
section[data-testid="stSidebar"] button[kind="header"],
.st-emotion-cache-1rtdyuf,
.st-emotion-cache-eczf16 {
    display: none !important;
    visibility: hidden !important;
    width: 0 !important;
    height: 0 !important;
    opacity: 0 !important;
    pointer-events: none !important;
}

/* 自訂標籤：可點擊 */
#sidebar-toggle-label {
    position: fixed;
    top: 77px;
    left: 0;
    color: white;
    writing-mode: vertical-rl;
    padding: 15px 8px;
    border-radius: 0 6px 6px 0;
    font-size: 24px;
    font-weight: bold;
    z-index: 999999;
    cursor: pointer;
    box-shadow: 2px 0 8px rgba(0,0,0,0.15);
    transition: all 0.3s ease;
}
#sidebar-toggle-label:hover {
    padding-left: 12px;
}

/* 主內容區 */
[data-testid="stMain"] {
    margin-left: 0 !important;
    width: 100% !important;
}

/* 側邊欄樣式 */
[data-testid="stSidebar"] {
    position: fixed !important;
    left: 0 !important;
    top: 0 !important;
    height: 100vh !important;
    width: 18rem !important;
    min-width: 18rem !important;
    z-index: 999 !important;
    transition: transform 0.3s ease !important;
    transform: translateX(-100%);
    background-image: url('https://i.pinimg.com/736x/53/1a/01/531a01457eca178f01c83ac2ede3f102.jpg') !important;
    background-size: cover !important;
    background-position: center !important;
    box-shadow: 4px 0 15px rgba(0,0,0,0.2) !important;
}

[data-testid="stSidebar"].sidebar-open {
    transform: translateX(0) !important;
}

[data-testid="stSidebar"] * { color: #443C3C !important; }

[data-testid="stSidebar"] input,
[data-testid="stSidebar"] textarea {
    background-color: #ecefef !important;
    color: #333 !important;
    border: 1px solid #ccc !important;
}

[data-testid="stSidebar"] h3 {
    font-size: 38px !important;
    font-weight: bold !important;
    color: #4A6B8A !important;
    text-align: center !important;
}

[data-testid="stSidebar"] strong { font-size: 18px !important; }

[data-testid="stSidebar"] [data-testid="stExpander"] summary,
[data-testid="stSidebar"] details summary span {
    font-size: 24px !important;
}

[data-testid="stSidebar"] [data-testid="stExpander"] {
    width: 100% !important;
    background-color: #f7f3ec !important;
    border: 2px solid rgba(200, 200, 200, 0.6) !important;
    border-radius: 10px !important;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1) !important;
    margin-bottom: 8px !important;
}

/* Expander 標題列背景 */
[data-testid="stSidebar"] [data-testid="stExpander"] > details > summary {
    background-color: #f7f3ec !important;
    border-radius: 8px !important;
}

/* Expander 展開後內容背景 */
[data-testid="stSidebar"] [data-testid="stExpander"] > div {
    background-color: transparent !important;
}

[data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stExpanderDetails"] {
    background-color: #e9ded0 !important;
}

/* 側邊欄下拉選單 */
[data-testid="stSidebar"] .stSelectbox > div > div {
    background-color: #ecefef !important;
    color: #333 !important;
    border: 1px solid #ccc !important;
    min-height: 45px !important;
    display: flex !important;
    align-items: center !important;
}

[data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] span,
[data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] div {
    color: #333 !important;
    font-size: 22px !important;
    overflow: visible !important;
}

[data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] > div {
    padding-top: 3px !important;
    padding-bottom: 6px !important;
}

/* 只禁用 selectbox 的搜索輸入，不影響 text_input */
[data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] input {
    pointer-events: none !important;
    caret-color: transparent !important;
    opacity: 0 !important;
    width: 1px !important;
}

/* 側邊欄輸入框 - 確保可以輸入 */
[data-testid="stSidebar"] .stTextInput input {
    background-color: #ecefef !important;
    color: #333 !important;
    border: 1px solid #ccc !important;
    pointer-events: auto !important;
    opacity: 1 !important;
    caret-color: #333 !important;
}

[data-testid="stSidebar"] input,
[data-testid="stSidebar"] select,
[data-testid="stSidebar"] button {
    font-size: 22px !important;
}

/* 側邊欄按鈕白色背景 */
[data-testid="stSidebar"] .stButton button {
    background-color: #ecefef !important;
    color: #333 !important;
    border: 1px solid #ccc !important;
}

[data-testid="stSidebar"] .stButton button:hover {
    background-color: #e8e8e8 !important;
    border-color: #4f7343 !important;
}

/* 側邊欄 primary 按鈕 */
[data-testid="stSidebar"] .stButton button[kind="primary"] {
    background: #8ba7c8 !important;
    color: white !important;
    border: none !important;
}

[data-testid="stSidebar"] [data-testid="stBaseButton-header"],
[data-testid="stSidebar"] button[kind="header"] {
    display: none !important;
}

/* 首頁樣式 */
.home-fullscreen {
    width: 100%;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    align-items: center;
    padding: 35px 0;
    box-sizing: border-box;
}

.welcome-title {
    font-size: 68px;
    font-weight: bold;
    letter-spacing: 0.18em;
    padding-left: 0.18em;
    white-space: nowrap;
    background: linear-gradient(135deg, #4A6B8A 0%, #7D5A6B 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}

.cards-container {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 40px;
}

.footer-credits {
    text-align: center;
    color: #5D5D5D;
    font-size: 28px;
    font-weight: 500;
}

/* 動畫卡片 */
.anim-card {
    width: 500px;
    height: 340px;
    padding: 30px 40px;
    border-radius: 20px;
    text-align: center;
    cursor: pointer;
    transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
    position: relative;
    overflow: hidden;
    box-shadow: 8px 8px 0px 0px rgba(60, 80, 100, 0.4);
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
}

.anim-card:hover {
    transform: translateY(-8px) scale(1.02);
    box-shadow: 12px 12px 0px 0px rgba(60, 80, 100, 0.5);
}

.anim-card-embed { background: linear-gradient(145deg, #7BA3C4 0%, #5C8AAD 100%); }
.anim-card-extract { background: linear-gradient(145deg, #C4A0AB 0%, #A67B85 100%); }

.anim-flow {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    margin-bottom: 20px;
    font-size: 36px;
    height: 100px;
}

.anim-flow img { width: 90px !important; height: 90px !important; }
.anim-flow .arrow { width: 70px !important; height: 70px !important; }

.anim-title {
    font-size: 56px;
    font-weight: bold;
    color: #FFFFFF;
    margin-bottom: 8px;
    text-shadow: 1px 1px 2px rgba(0,0,0,0.2);
}

.anim-desc {
    font-size: 36px;
    color: rgba(255,255,255,0.9);
    line-height: 1.5;
    white-space: nowrap;
}

/* 功能頁面樣式 */
.page-title-embed {
    font-size: clamp(36px, 4vw, 56px);
    font-weight: bold;
    background: linear-gradient(135deg, #4A6B8A 0%, #5C8AAD 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}

.page-title-extract {
    font-size: clamp(36px, 4vw, 56px);
    font-weight: bold;
    background: linear-gradient(135deg, #7D5A6B 0%, #A67B85 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}

/* 訊息框 */
.success-box {
    background: linear-gradient(135deg, #4A6B8A 0%, #5C8AAD 100%);
    color: white; padding: 20px 30px; border-radius: 10px;
    margin: 10px 0; display: inline-block; font-size: clamp(20px, 2.5vw, 28px); min-width: 300px;
}
.info-box {
    background: linear-gradient(135deg, #4A6B8A 0%, #5C8AAD 100%);
    color: white; padding: 20px 30px; border-radius: 10px;
    margin: 10px 0; display: inline-block; font-size: clamp(18px, 2vw, 26px); line-height: 1.9; min-width: 300px;
}
.error-box {
    background: linear-gradient(135deg, #8B5A5A 0%, #A67B7B 100%);
    color: white; padding: 20px 30px; border-radius: 10px;
    margin: 10px 0; display: inline-block; font-size: clamp(18px, 2vw, 26px); min-width: 300px;
}

/* 字體放大 */
[data-testid="stMain"] .stMarkdown p,
[data-testid="stMain"] .stText p {
    font-size: clamp(22px, 2.5vw, 30px) !important;
    font-weight: bold !important;
}

/* 驗證對比文字 - 小字體 */
[data-testid="stMain"] .stMarkdown p.verify-label {
    font-size: 14px !important;
    font-weight: bold !important;
    color: #443C3C !important;
}

[data-testid="stMain"] .stMarkdown p.verify-content {
    font-size: 12px !important;
    font-weight: normal !important;
    color: #666 !important;
}

/* 小提示文字樣式 */
[data-testid="stMain"] .stMarkdown p.hint-text,
[data-testid="stMain"] .stMarkdown div.hint-text,
p.hint-text,
div.hint-text {
    font-size: 22px !important;
    font-weight: bold !important;
    color: #4f7343 !important;
}

/* Tab 切換按鈕樣式 */
.tab-container {
    display: flex;
    gap: 10px;
    margin-bottom: 8px;
}
.tab-btn {
    flex: 1;
    padding: 12px 20px;
    font-size: 22px;
    font-weight: bold;
    border: 2px solid #ccc;
    border-radius: 8px;
    background: #ecefef;
    color: #666;
    cursor: pointer;
    transition: all 0.2s;
    text-align: center;
}
.tab-btn:hover {
    border-color: #999;
    background: #e0e0e0;
}
.tab-btn.active {
    background: #4A6B8A;
    color: white;
    border-color: #4A6B8A;
}
.tab-btn-extract.active {
    background: #7D5A6B;
    border-color: #7D5A6B;
}

/* bits 資訊專用樣式 */
.bits-info {
    font-size: 28px !important;
    color: #4f7343 !important;
    font-weight: bold !important;
}

/* 已選擇資訊專用樣式 */
.selected-info {
    font-size: 28px !important;
    color: #4f7343 !important;
    font-weight: bold !important;
}

h3 { font-size: clamp(28px, 3vw, 36px) !important; font-weight: bold !important; }

/* 按鈕樣式 */
.stButton button span,
.stButton button p {
    font-size: 18px !important;
    font-weight: bold !important;
}

[data-testid="stMain"] .stButton button[kind="primary"] {
    background: #4A6B8A !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-size: 24px !important;
    padding: 8px 20px !important;
    min-width: 80px !important;
}

[data-testid="stMain"] .stButton button[kind="secondary"] {
    background: #ecefef !important;
    color: #666 !important;
    border: 2px solid #ccc !important;
    border-radius: 8px !important;
    font-size: 24px !important;
    padding: 8px 20px !important;
    min-width: 80px !important;
}

[data-testid="stMain"] .stButton button[kind="secondary"]:hover {
    background: #e0e0e0 !important;
    border-color: #4f7343 !important;
}

[data-testid="stMain"] .stButton button[kind="primary"] span,
[data-testid="stMain"] .stButton button[kind="primary"] p {
    font-size: 24px !important;
}

[data-testid="stMain"] .stButton button[kind="secondary"] span,
[data-testid="stMain"] .stButton button[kind="secondary"] p {
    font-size: 24px !important;
}

[data-testid="stSidebar"] .stButton button[kind="primary"] {
    background: #8ba7c8 !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
}

/* 表單元素標題 - 放大字體（只限主內容區）*/
[data-testid="stMain"] .stSelectbox label, 
[data-testid="stMain"] .stSelectbox label p,
[data-testid="stMain"] .stRadio label, 
[data-testid="stMain"] .stTextArea label, 
[data-testid="stMain"] .stFileUploader label,
[data-testid="stMain"] [data-testid="stWidgetLabel"] p {
    font-size: 24px !important;
    font-weight: bold !important;
    color: #443C3C !important;
}

/* 側邊欄表單標籤 - 較小字體 */
[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] .stTextInput label,
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {
    font-size: 22px !important;
    font-weight: bold !important;
    color: #443C3C !important;
}

/* 側邊欄輸入框文字 */
[data-testid="stSidebar"] .stTextInput input {
    font-size: 22px !important;
}

/* 側邊欄下拉選單文字 */
[data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] span,
[data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] div {
    font-size: 22px !important;
}

/* 側邊欄按鈕文字 */
[data-testid="stSidebar"] .stButton button {
    font-size: 22px !important;
}
[data-testid="stSidebar"] .stButton button span,
[data-testid="stSidebar"] .stButton button p {
    font-size: 22px !important;
}

.stRadio [role="radiogroup"] label,
.stRadio [role="radiogroup"] label p {
    font-size: 30px !important;
    color: #443C3C !important;
    font-weight: bold !important;
}

/* Radio 按鈕水平對齊 */
.stRadio [role="radiogroup"] label {
    display: flex !important;
    align-items: center !important;
}

.stRadio [role="radiogroup"] label > div:first-child {
    display: flex !important;
    align-items: center !important;
}

/* Radio 按鈕樣式 - 圓形 */
.stRadio [data-baseweb="radio"] > div:first-child {
    width: 22px !important;
    height: 22px !important;
    min-width: 22px !important;
    min-height: 22px !important;
    border-radius: 50% !important;
    border: 2px solid #443C3C !important;
    background-color: #ecefef !important;
}

/* 選中時內部圓點填滿 */
.stRadio [data-baseweb="radio"] > div:first-child > div {
    background-color: #443C3C !important;
    border-radius: 50% !important;
}

.stTextArea textarea {
    font-size: 24px !important;
    background-color: #ecefef !important;
    border: 1px solid #ccc !important;
    border-radius: 8px !important;
    color: #333 !important;
    padding: 12px !important;
    caret-color: #333 !important;
}

.stTextArea textarea:focus {
    outline: none !important;
    border-color: #ccc !important;
}

.stTextArea textarea::placeholder {
    color: #888 !important;
    opacity: 1 !important;
}

/* 移除 textarea 底部黑線 */
.stTextArea [data-baseweb="textarea"] {
    border: none !important;
    background-color: transparent !important;
}

.stTextArea [data-baseweb="base-input"] {
    border-bottom: none !important;
    border: none !important;
    background-color: transparent !important;
}

.stTextArea > div > div {
    border-bottom: none !important;
    background-color: transparent !important;
}

.stTextArea > div > div > div {
    border-bottom: none !important;
    background-color: #ecefef !important;
}

.stTextArea [data-baseweb="textarea"]::after,
.stTextArea [data-baseweb="base-input"]::after {
    display: none !important;
}

/* 隱藏 Ctrl+Enter 提示 */
.stTextArea [data-testid="stTextAreaRootContainer"] > div:last-child,
.stTextArea .st-emotion-cache-1gulkj5 {
    display: none !important;
}

/* ===== 強制隱藏 textarea 所有滾動條 ===== */
.stTextArea,
.stTextArea > div,
.stTextArea > div > div,
.stTextArea > div > div > div,
.stTextArea [data-baseweb="textarea"],
.stTextArea [data-baseweb="textarea"] > div,
.stTextArea [data-baseweb="base-input"],
.stTextArea [data-testid="stTextAreaRootContainer"],
.stTextArea [data-testid="stTextAreaRootContainer"] > div,
.stTextArea [data-testid="stTextAreaRootContainer"] > div > div {
    overflow: hidden !important;
    overflow-y: hidden !important;
    overflow-x: hidden !important;
    scrollbar-width: none !important;
    -ms-overflow-style: none !important;
}

/* 隱藏外層所有滾動條軌道 */
.stTextArea *:not(textarea)::-webkit-scrollbar {
    display: none !important;
    width: 0 !important;
    height: 0 !important;
    background: transparent !important;
}

/* textarea 本身也隱藏滾動條但可滾動 */
.stTextArea textarea {
    overflow: auto !important;
    overflow-y: auto !important;
    scrollbar-width: none !important;
    -ms-overflow-style: none !important;
}

/* 隱藏 textarea 本身的滾動條 */
.stTextArea textarea::-webkit-scrollbar {
    display: none !important;
    width: 0 !important;
    height: 0 !important;
}

/* 額外強制：所有 stTextArea 相關元素的滾動條 */
[data-testid="stTextAreaRootContainer"],
[data-testid="stTextAreaRootContainer"] *,
.stTextArea [class*="TextArea"],
.stTextArea [class*="textarea"] {
    scrollbar-width: none !important;
    -ms-overflow-style: none !important;
}

[data-testid="stTextAreaRootContainer"]::-webkit-scrollbar,
[data-testid="stTextAreaRootContainer"] *::-webkit-scrollbar {
    display: none !important;
    width: 0 !important;
    height: 0 !important;
}

.stCaption, [data-testid="stCaptionContainer"] {
    color: #443C3C !important;
    font-size: clamp(16px, 1.8vw, 22px) !important;
}

/* FileUploader 樣式 */
[data-testid="stFileUploader"] > div > div {
    background-color: #ecefef !important;
}

[data-testid="stFileUploader"] [data-testid="stFileUploaderDropzone"] {
    background-color: #ecefef !important;
}

/* Browse files 按鈕背景顏色 */
[data-testid="stFileUploader"] button,
[data-testid="stFileUploader"] [data-testid="stBaseButton-secondary"],
[data-testid="stFileUploader"] [data-testid="stFileUploaderDropzone"] button {
    background-color: #ecefef !important;
    color: #443C3C !important;
    border: 1px solid #ccc !important;
}

/* 已上傳檔案名稱和大小的字體顏色 */
[data-testid="stFileUploader"] [data-testid="stFileUploaderFile"],
[data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] span,
[data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] small,
[data-testid="stFileUploader"] small,
[data-testid="stFileUploader"] .uploadedFileName,
[data-testid="stFileUploader"] div[data-testid="stMarkdownContainer"] p {
    color: #443C3C !important;
}

/* 檔案資訊區塊 */
[data-testid="stFileUploader"] section > div {
    color: #443C3C !important;
}

[data-testid="stFileUploader"] section small {
    color: #443C3C !important;
}

/* 已上傳檔案列表 - 強制覆蓋所有文字顏色 */
[data-testid="stFileUploader"] section,
[data-testid="stFileUploader"] section *,
[data-testid="stFileUploader"] section div,
[data-testid="stFileUploader"] section span,
[data-testid="stFileUploader"] section p,
[data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] *,
.uploadedFile,
.uploadedFile *,
[class*="uploadedFile"] *,
[data-testid="stFileUploader"] li,
[data-testid="stFileUploader"] li * {
    color: #443C3C !important;
}

/* Selectbox 樣式 */
[data-testid="stMain"] .stSelectbox > div > div {
    background-color: #ecefef !important;
    border-radius: 8px !important;
    min-height: 55px !important;
    border: 1px solid #ccc !important;
    padding-top: 4px !important;
    padding-bottom: 4px !important;
}

[data-testid="stMain"] .stSelectbox [data-baseweb="select"] span,
[data-testid="stMain"] .stSelectbox [data-baseweb="select"] div {
    font-size: 24px !important;
    font-weight: bold !important;
    color: #333 !important;
    overflow: visible !important;
    line-height: 1.4 !important;
}

[data-baseweb="popover"] li {
    background-color: #ecefef !important;
    font-size: 22px !important;
    font-weight: normal !important;
    color: #333 !important;
    min-height: 50px !important;
    padding: 12px 16px !important;
}

/* 下拉列表容器背景 */
[data-baseweb="popover"],
[data-baseweb="popover"] > div,
ul[role="listbox"] {
    background-color: #ecefef !important;
}

[data-baseweb="popover"] li span,
[data-baseweb="popover"] li div,
[data-baseweb="popover"] [role="option"],
[data-baseweb="popover"] [role="option"] *,
[data-baseweb="menu"] li,
[data-baseweb="menu"] li *,
ul[role="listbox"] li,
ul[role="listbox"] li * {
    color: #333 !important;
    background-color: #ecefef !important;
    font-size: 22px !important;
    font-weight: normal !important;
}

ul[role="listbox"] li:hover,
[data-baseweb="menu"] li:hover {
    background-color: #dce0e0 !important;
}

/* ===== 下拉選單勾選標記顏色 ===== */
[data-baseweb="menu"] li svg,
[data-baseweb="select"] svg[data-baseweb="icon"],
ul[role="listbox"] li svg,
[data-baseweb="popover"] li svg,
[data-baseweb="menu"] [aria-selected="true"] svg,
ul[role="listbox"] [aria-selected="true"] svg {
    fill: #443C3C !important;
    color: #443C3C !important;
}

/* ===== 下拉選單滾動條樣式 ===== */
[data-baseweb="menu"]::-webkit-scrollbar,
[data-baseweb="popover"]::-webkit-scrollbar,
[data-baseweb="popover"] > div::-webkit-scrollbar,
[data-baseweb="popover"] ul::-webkit-scrollbar,
ul[role="listbox"]::-webkit-scrollbar,
div[data-baseweb="popover"] *::-webkit-scrollbar {
    width: 8px !important;
    background: #f5f0e6 !important;
}

[data-baseweb="menu"]::-webkit-scrollbar-track,
[data-baseweb="popover"]::-webkit-scrollbar-track,
[data-baseweb="popover"] > div::-webkit-scrollbar-track,
[data-baseweb="popover"] ul::-webkit-scrollbar-track,
ul[role="listbox"]::-webkit-scrollbar-track,
div[data-baseweb="popover"] *::-webkit-scrollbar-track {
    background: #f5f0e6 !important;
    border-radius: 4px !important;
}

[data-baseweb="menu"]::-webkit-scrollbar-thumb,
[data-baseweb="popover"]::-webkit-scrollbar-thumb,
[data-baseweb="popover"] > div::-webkit-scrollbar-thumb,
[data-baseweb="popover"] ul::-webkit-scrollbar-thumb,
ul[role="listbox"]::-webkit-scrollbar-thumb,
div[data-baseweb="popover"] *::-webkit-scrollbar-thumb {
    background: #b8a88a !important;
    border-radius: 4px !important;
}

[data-baseweb="menu"]::-webkit-scrollbar-thumb:hover,
[data-baseweb="popover"]::-webkit-scrollbar-thumb:hover,
[data-baseweb="popover"] > div::-webkit-scrollbar-thumb:hover,
[data-baseweb="popover"] ul::-webkit-scrollbar-thumb:hover,
ul[role="listbox"]::-webkit-scrollbar-thumb:hover,
div[data-baseweb="popover"] *::-webkit-scrollbar-thumb:hover {
    background: #9a8b6e !important;
}

/* Firefox 滾動條 */
[data-baseweb="menu"],
[data-baseweb="popover"],
[data-baseweb="popover"] > div,
[data-baseweb="popover"] ul,
ul[role="listbox"] {
    scrollbar-width: thin !important;
    scrollbar-color: #b8a88a #f5f0e6 !important;
}

/* 全局下拉選單滾動條覆蓋 */
body div[data-baseweb="popover"] *::-webkit-scrollbar,
body [data-baseweb="select"] ~ div *::-webkit-scrollbar,
[data-baseweb="base-popover"] *::-webkit-scrollbar {
    width: 8px !important;
    background: #f5f0e6 !important;
}

body div[data-baseweb="popover"] *::-webkit-scrollbar-thumb,
body [data-baseweb="select"] ~ div *::-webkit-scrollbar-thumb,
[data-baseweb="base-popover"] *::-webkit-scrollbar-thumb {
    background: #b8a88a !important;
    border-radius: 4px !important;
}

body div[data-baseweb="popover"] *::-webkit-scrollbar-track,
body [data-baseweb="select"] ~ div *::-webkit-scrollbar-track,
[data-baseweb="base-popover"] *::-webkit-scrollbar-track {
    background: #f5f0e6 !important;
    border-radius: 4px !important;
}

/* 確保選中的值完整顯示 */
[data-baseweb="select"] > div {
    min-height: 45px !important;
    padding: 8px !important;
}

[data-baseweb="select"] [data-testid="stMarkdownContainer"],
[data-baseweb="select"] .css-1dimb5e-singleValue,
[data-baseweb="select"] div[class*="singleValue"] {
    overflow: visible !important;
    text-overflow: unset !important;
    white-space: nowrap !important;
}

/* 固定按鈕容器 */
.fixed-btn-next {
    position: fixed !important;
    bottom: 50px !important;
    right: 30px !important;
    z-index: 1000 !important;
}

.fixed-btn-back {
    position: fixed !important;
    bottom: 50px !important;
    left: 30px !important;
    z-index: 1000 !important;
}

.fixed-btn-next button,
.fixed-btn-back button {
    font-size: 18px !important;
    padding: 12px 36px !important;
    min-width: 120px !important;
    border-radius: 8px !important;
}

/* 間距調整 */
.block-container {
    padding-top: 0.5rem !important;
    padding-bottom: 3rem !important;
    max-width: 1400px !important;
    margin: 0 auto !important;
}

/* 功能頁面容器居中 */
[data-testid="stMain"] > .block-container {
    max-width: 1400px !important;
    margin: 0 auto !important;
    padding-left: 2rem !important;
    padding-right: 2rem !important;
}

/* 內容區域對齊步驟條 */
[data-testid="stMain"] .stSelectbox,
[data-testid="stMain"] .stTextArea,
[data-testid="stMain"] .stFileUploader,
[data-testid="stMain"] .stRadio {
    max-width: 1200px !important;
    margin-left: auto !important;
    margin-right: auto !important;
}

[data-testid="stMain"] .stMarkdown {
    max-width: 1200px !important;
    margin-left: auto !important;
    margin-right: auto !important;
}

/* 大螢幕優化 */
@media (min-width: 1600px) {
    [data-testid="stMain"] > .block-container {
        max-width: 1500px !important;
        padding-left: 3rem !important;
        padding-right: 3rem !important;
    }
    
    .page-title-embed, .page-title-extract {
        font-size: 56px !important;
    }
}

/* 全螢幕模式優化 */
@media (min-height: 900px) {
    .block-container {
        padding-top: 1rem !important;
    }
}

.stMarkdown hr { margin: 0.5rem 0 !important; }
.stSelectbox, .stTextArea, .stFileUploader, .stRadio { margin-bottom: 0.3rem !important; }

[data-testid="stHorizontalBlock"] {
    flex-wrap: nowrap !important;
    gap: 0.3rem !important;
    max-width: 1200px !important;
    margin-left: auto !important;
    margin-right: auto !important;
}

</style>
""", unsafe_allow_html=True)

# JavaScript 強制修改下拉選單滾動條顏色 + 隱藏 textarea 滾動條 + 勾選樣式
components.html("""
<script>
function injectScrollbarStyle() {
    const css = `
        /* 只針對下拉選單滾動條 - 米色風格 */
        [data-baseweb="popover"]::-webkit-scrollbar,
        [data-baseweb="popover"] > div::-webkit-scrollbar,
        [data-baseweb="popover"] ul::-webkit-scrollbar,
        [data-baseweb="menu"]::-webkit-scrollbar,
        ul[role="listbox"]::-webkit-scrollbar,
        div[data-baseweb="popover"] *::-webkit-scrollbar {
            width: 8px !important;
        }
        [data-baseweb="popover"]::-webkit-scrollbar-track,
        [data-baseweb="popover"] > div::-webkit-scrollbar-track,
        [data-baseweb="popover"] ul::-webkit-scrollbar-track,
        [data-baseweb="menu"]::-webkit-scrollbar-track,
        ul[role="listbox"]::-webkit-scrollbar-track,
        div[data-baseweb="popover"] *::-webkit-scrollbar-track {
            background: #f5f0e6 !important;
            border-radius: 4px !important;
        }
        [data-baseweb="popover"]::-webkit-scrollbar-thumb,
        [data-baseweb="popover"] > div::-webkit-scrollbar-thumb,
        [data-baseweb="popover"] ul::-webkit-scrollbar-thumb,
        [data-baseweb="menu"]::-webkit-scrollbar-thumb,
        ul[role="listbox"]::-webkit-scrollbar-thumb,
        div[data-baseweb="popover"] *::-webkit-scrollbar-thumb {
            background: #b8a88a !important;
            border-radius: 4px !important;
        }
        [data-baseweb="popover"]::-webkit-scrollbar-thumb:hover,
        [data-baseweb="popover"] > div::-webkit-scrollbar-thumb:hover,
        [data-baseweb="menu"]::-webkit-scrollbar-thumb:hover,
        ul[role="listbox"]::-webkit-scrollbar-thumb:hover {
            background: #9a8b6e !important;
        }
        [data-baseweb="popover"],
        [data-baseweb="popover"] > div,
        [data-baseweb="popover"] ul,
        [data-baseweb="menu"],
        ul[role="listbox"] {
            scrollbar-width: thin !important;
            scrollbar-color: #b8a88a #f5f0e6 !important;
        }
        
        /* textarea 完全隱藏滾動條 */
        .stTextArea::-webkit-scrollbar,
        .stTextArea *::-webkit-scrollbar {
            display: none !important;
            width: 0 !important;
            height: 0 !important;
        }
        .stTextArea,
        .stTextArea * {
            scrollbar-width: none !important;
            -ms-overflow-style: none !important;
        }
    `;
    
    // 注入到 parent document (Streamlit 主頁面)
    if (window.parent && window.parent.document && window.parent.document.head) {
        const style = document.createElement('style');
        style.textContent = css;
        style.id = 'custom-scrollbar-style';
        const oldStyle = window.parent.document.getElementById('custom-scrollbar-style');
        if (oldStyle) oldStyle.remove();
        window.parent.document.head.appendChild(style);
    }
}

// 強制隱藏 textarea 所有滾動條
function fixTextareaScrollbar() {
    if (window.parent && window.parent.document) {
        // 直接操作 DOM 元素設定 inline style（最高優先級）
        const textareas = window.parent.document.querySelectorAll('.stTextArea');
        textareas.forEach(ta => {
            // 設定容器本身
            ta.style.cssText += 'overflow:hidden!important;scrollbar-width:none!important;';
            
            // 設定所有子元素（排除 textarea）
            const allElements = ta.querySelectorAll('*');
            allElements.forEach(el => {
                if (el.tagName !== 'TEXTAREA') {
                    el.style.cssText += 'overflow:hidden!important;scrollbar-width:none!important;-ms-overflow-style:none!important;';
                }
            });
            
            // textarea 本身可以滾動但隱藏滾動條
            const textarea = ta.querySelector('textarea');
            if (textarea) {
                textarea.style.cssText += 'overflow-y:auto!important;scrollbar-width:none!important;-ms-overflow-style:none!important;';
            }
        });
    }
}

injectScrollbarStyle();
fixTextareaScrollbar();
setTimeout(injectScrollbarStyle, 300);
setTimeout(fixTextareaScrollbar, 300);
setTimeout(injectScrollbarStyle, 1000);
setTimeout(fixTextareaScrollbar, 1000);
setTimeout(fixTextareaScrollbar, 2000);

// 監聽 DOM 變化，新元素出現時也套用樣式
if (window.parent && window.parent.document) {
    const observer = new MutationObserver(() => {
        injectScrollbarStyle();
        fixTextareaScrollbar();
    });
    observer.observe(window.parent.document.body, { childList: true, subtree: true });
}
</script>
""", height=0)

# ==================== 初始化狀態 ====================
if 'current_mode' not in st.session_state:
    st.session_state.current_mode = None

# ==================== 側邊欄 - 對象管理 ====================
if st.session_state.current_mode is not None:
    # 根據當前模式設定顏色
    sidebar_title_color = "#4A6B8A" if st.session_state.current_mode == 'embed' else "#7D5A6B"
    
    with st.sidebar:
        st.markdown(f"""
        <style>
        section[data-testid="stSidebar"] details summary span p {{ font-size: 22px !important; }}
        #built-contacts-title {{ font-size: 28px !important; font-weight: bold !important; margin-bottom: 10px !important; text-align: center !important; }}
        [data-testid="stSidebar"] .sidebar-title {{ font-size: 36px !important; margin-bottom: 15px !important; color: {sidebar_title_color} !important; font-weight: bold !important; text-align: center !important; }}
        </style>
        <div id="sidebar-close-btn" style="position: absolute; top: -15px; right: 0px; 
            width: 30px; height: 30px; background: #e0e0e0; border-radius: 50%; 
            display: flex; align-items: center; justify-content: center; 
            cursor: pointer; font-size: 18px; color: #666; z-index: 9999;">✕</div>
        """, unsafe_allow_html=True)
        
        st.markdown(f'<div class="sidebar-title" style="color: {sidebar_title_color} !important;">對象管理</div>', unsafe_allow_html=True)
        
        contacts = st.session_state.contacts
        style_options = ["選擇"] + list(STYLE_CATEGORIES.keys())
        
        # 新增對象
        with st.expander("新增對象", expanded=False):
            add_counter = st.session_state.get('add_contact_counter', 0)
            new_name = st.text_input("名稱", key=f"sidebar_new_name_{add_counter}")
            new_style = st.selectbox("綁定風格", style_options, key=f"sidebar_new_style_{add_counter}")
            
            can_add = new_name and new_name.strip() and new_style != "選擇"
            if st.button("新增", key="sidebar_add_btn", use_container_width=True, disabled=not can_add, type="primary" if can_add else "secondary"):
                try:
                    new_key = generate_contact_key()
                    st.session_state.contacts[new_name.strip()] = {
                        "style": new_style,
                        "key": new_key
                    }
                    save_contacts(st.session_state.contacts)
                    st.toast(f"✅ 已新增「{new_name.strip()}」")
                    st.session_state.add_contact_counter = add_counter + 1
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ 新增失敗：{e}")
        
        st.markdown("---")
        st.markdown('<div id="built-contacts-title">對象列表</div>', unsafe_allow_html=True)
        
        if contacts:
            for name, contact_data in contacts.items():
                # 取得風格（支援新舊格式）
                style = get_contact_style(contacts, name)
                style_display = STYLE_CATEGORIES.get(style, style) if style else "未綁定"
                display_text = f"{name}（{style_display}）"
                
                with st.expander(display_text, expanded=False):
                    new_nickname = st.text_input("名稱", value=name, key=f"new_name_{name}")
                    new_style_edit = st.selectbox("風格", style_options, 
                        index=style_options.index(style) if style in style_options else 0,
                        key=f"new_style_{name}")
                    
                    has_change = (new_nickname.strip() != name) or (new_style_edit != style)
                    
                    if st.button("儲存修改", key=f"save_{name}", use_container_width=True, type="primary" if has_change else "secondary"):
                        # 保留原有的密鑰
                        old_key = get_contact_key(contacts, name)
                        if new_nickname.strip() != name:
                            del st.session_state.contacts[name]
                        st.session_state.contacts[new_nickname.strip()] = {
                            "style": new_style_edit if new_style_edit != "選擇" else None,
                            "key": old_key or generate_contact_key()
                        }
                        save_contacts(st.session_state.contacts)
                        st.rerun()
                    
                    if st.button("刪除", key=f"del_{name}", use_container_width=True):
                        del st.session_state.contacts[name]
                        save_contacts(st.session_state.contacts)
                        st.rerun()
        else:
            st.markdown('<p style="font-size: 22px; color: #666;">尚無對象</p>', unsafe_allow_html=True)

# ==================== 主要邏輯 ====================
if st.session_state.current_mode is None:
    # ==================== 首頁 ====================
    
    st.markdown("""
    <style>
    html, body, [data-testid="stAppViewContainer"], .main, [data-testid="stMain"] {
        overflow: hidden !important;
        height: 100vh !important;
    }
    .block-container {
        padding-bottom: 0 !important;
        height: 100vh !important;
        overflow: hidden !important;
    }
    iframe {
        height: calc(100vh - 20px) !important;
        min-height: 700px !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    icon_secret = get_icon_base64("secret-message")
    icon_image = get_icon_base64("public-image")
    icon_arrow = get_icon_base64("arrow")
    icon_zcode = get_icon_base64("z-code")
    
    # 使用 Flexbox 佈局的首頁
    components.html(f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    html, body {{ 
        height: 100%;
        min-height: 100vh;
    }}
    body {{ 
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        background: transparent;
        overflow: hidden;
        display: flex;
        justify-content: center;
        align-items: center;
    }}
    
    /* ===== Flexbox 佈局 ===== */
    .home-fullscreen {{
        width: 100%;
        height: 100%;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        align-items: center;
        padding: 1.2vh 0 14vh 0;
    }}
    
    /* 區塊1: 標題 */
    .welcome-container {{
        text-align: center;
        flex-shrink: 0;
    }}
    
    /* 區塊2: 卡片 */
    .cards-container {{
        display: flex;
        justify-content: center;
        align-items: center;
        gap: clamp(40px, 6vw, 100px);
        flex-shrink: 0;
    }}
    
    /* 區塊3: 組員 */
    .footer-credits {{
        text-align: center;
        color: #5D5D5D;
        font-size: clamp(24px, 3.5vw, 60px);
        font-weight: 500;
        flex-shrink: 0;
    }}
    
    .welcome-title {{
        font-size: clamp(35px, 5.5vw, 100px);
        font-weight: bold;
        letter-spacing: 0.1em;
        white-space: nowrap;
        background: linear-gradient(135deg, #4A6B8A 0%, #7D5A6B 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }}
    
    .anim-card {{
        width: clamp(280px, 38vw, 620px);
        height: clamp(200px, 28vw, 420px);
        padding: clamp(15px, 2vw, 35px) clamp(20px, 3vw, 50px);
        border-radius: 20px;
        text-align: center;
        cursor: pointer;
        transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        box-shadow: 8px 8px 0px 0px rgba(60, 80, 100, 0.4);
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
    }}
    
    .anim-card:hover {{
        transform: translateY(-8px) scale(1.02);
        box-shadow: 12px 12px 0px 0px rgba(60, 80, 100, 0.5);
    }}
    
    .anim-card-embed {{ background: linear-gradient(145deg, #7BA3C4 0%, #5C8AAD 100%); }}
    .anim-card-extract {{ background: linear-gradient(145deg, #C4A0AB 0%, #A67B85 100%); }}
    
    .anim-flow {{
        display: flex;
        align-items: center;
        justify-content: center;
        gap: clamp(5px, 1vw, 10px);
        margin-bottom: clamp(15px, 2vw, 32px);
        height: clamp(60px, 10vw, 150px);
    }}
    
    .anim-flow img {{
        width: clamp(50px, 8vw, 130px);
        height: clamp(45px, 7vw, 110px);
        object-fit: contain;
    }}
    
    .anim-flow img.arrow {{
        width: clamp(40px, 6vw, 100px);
        height: clamp(35px, 5vw, 85px);
    }}
    
    .anim-flow span {{
        font-size: clamp(24px, 3.5vw, 52px);
        color: white;
        font-weight: bold;
    }}
    
    .anim-title {{
        font-size: clamp(28px, 4.5vw, 68px);
        font-weight: bold;
        color: white;
        margin-bottom: clamp(10px, 1.5vw, 22px);
        text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
    }}
    
    .anim-desc {{
        font-size: clamp(18px, 3vw, 52px);
        color: rgba(255,255,255,0.9);
        line-height: 1.4;
        white-space: nowrap;
    }}
    
    /* 統一脈動動畫 - 排除載體圖（第2張） */
    .anim-card-embed img:not(:nth-of-type(2)),
    .anim-card-extract img:not(:nth-of-type(2)) {{
        animation: pulse 1.5s ease-in-out infinite;
    }}
    
    @keyframes pulse {{
        0%, 100% {{ transform: scale(1); }}
        50% {{ transform: scale(1.2); }}
    }}
    </style>
    </head>
    <body>
    <div class="home-fullscreen">
        <div class="welcome-container">
            <div class="welcome-title">高效能無載體之機密編碼技術</div>
        </div>
        
        <div class="cards-container">
            <div class="anim-card anim-card-embed" onclick="clickEmbed()">
                <div class="anim-flow">
                    <img src="{icon_secret}" alt="secret">
                    <span>+</span>
                    <img src="{icon_image}" alt="image">
                    <img src="{icon_arrow}" class="arrow" alt="arrow">
                    <img src="{icon_zcode}" alt="zcode">
                </div>
                <div class="anim-title">嵌入機密</div>
                <div class="anim-desc">基於載體圖像<br>生成編碼圖像</div>
            </div>
            
            <div class="anim-card anim-card-extract" onclick="clickExtract()">
                <div class="anim-flow">
                    <img src="{icon_zcode}" alt="zcode">
                    <span>+</span>
                    <img src="{icon_image}" alt="image">
                    <img src="{icon_arrow}" class="arrow" alt="arrow">
                    <img src="{icon_secret}" alt="secret">
                </div>
                <div class="anim-title">提取機密</div>
                <div class="anim-desc">參考相同載體圖像<br>重建機密訊息</div>
            </div>
        </div>
        
        <div class="footer-credits">
            組員：鄭凱譽、劉佳典、王于婕
        </div>
    </div>
    
    <script>
    const parentDoc = window.parent.document;
    
    function clickEmbed() {{
        const buttons = parentDoc.querySelectorAll('button');
        buttons.forEach(b => {{ if (b.innerText.includes('嵌入')) b.click(); }});
    }}
    
    function clickExtract() {{
        const buttons = parentDoc.querySelectorAll('button');
        buttons.forEach(b => {{ if (b.innerText.includes('提取')) b.click(); }});
    }}
    
    function hideStreamlitBadges() {{
        const selectors = [
            '[class*="viewerBadge"]',
            'a[href*="streamlit.io"]',
            '[class*="StatusWidget"]',
            '[data-testid="manage-app-button"]',
            '.stAppDeployButton',
            'section[data-testid="stStatusWidget"]',
            '[class*="stDeployButton"]',
            '[class*="AppDeployButton"]'
        ];
        selectors.forEach(sel => {{
            parentDoc.querySelectorAll(sel).forEach(el => {{
                el.style.display = 'none';
            }});
        }});
    }}
    
    hideStreamlitBadges();
    setTimeout(hideStreamlitBadges, 500);
    setTimeout(hideStreamlitBadges, 1000);
    setTimeout(hideStreamlitBadges, 2000);
    </script>
    </body>
    </html>
    """, height=900, scrolling=False)
    
    # 動態調整 iframe 高度
    components.html("""
    <script>
    (function() {
        const iframe = window.frameElement;
        if (iframe) {
            iframe.style.height = 'calc(100vh - 50px)';
            iframe.style.minHeight = '700px';
        }
    })();
    </script>
    """, height=0)
    
    # 隱藏的按鈕
    col1, col2 = st.columns(2)
    with col1:
        if st.button("開始嵌入", key="btn_embed", use_container_width=True):
            st.session_state.current_mode = 'embed'
            st.session_state.prev_embed_image_select = None
            st.session_state.prev_contact = None
            st.rerun()
    with col2:
        if st.button("開始提取", key="btn_extract", use_container_width=True):
            st.session_state.current_mode = 'extract'
            st.rerun()
    
    components.html("""
<script>
const doc = window.parent.document;
function hideHomeButtons() {
    const buttons = doc.querySelectorAll('button');
    buttons.forEach(btn => {
        const text = btn.innerText || btn.textContent;
        if (text.includes('開始嵌入') || text.includes('開始提取')) {
            btn.style.cssText = 'position:fixed!important;top:-9999px!important;left:-9999px!important;opacity:0!important;';
        }
    });
}
hideHomeButtons();
setTimeout(hideHomeButtons, 100);
new MutationObserver(hideHomeButtons).observe(doc.body, { childList: true, subtree: true });
</script>
""", height=0)


elif st.session_state.current_mode == 'embed':
    # ==================== 嵌入模式 ====================
    
    if 'embed_page' not in st.session_state:
        st.session_state.embed_page = 'input'
    
    # 結果頁
    if st.session_state.embed_page == 'result' and st.session_state.embed_result and st.session_state.embed_result.get('success'):
        st.markdown('<style>.main { overflow: auto !important; }</style>', unsafe_allow_html=True)
        
        r = st.session_state.embed_result
        
        st.markdown('<div class="page-title-embed" style="text-align: center; margin-bottom: 30px;">嵌入結果</div>', unsafe_allow_html=True)
        
        # 下載按鈕樣式
        st.markdown("""
        <style>
        /* 下載 Z碼圖 按鈕樣式 */
        [data-testid="stDownloadButton"] button {
            background-color: #c9b89a !important;
            color: #443C3C !important;
            border: none !important;
            font-weight: 700 !important;
            font-size: 24px !important;
            min-width: 120px !important;
            padding: 8px 18px !important;
        }
        [data-testid="stDownloadButton"] button p,
        [data-testid="stDownloadButton"] button span {
            font-weight: 700 !important;
            font-size: 24px !important;
        }
        [data-testid="stDownloadButton"] button:hover {
            background-color: #b8a788 !important;
        }
        [data-testid="stDownloadButton"] button:active,
        [data-testid="stDownloadButton"] button:focus {
            background-color: #d9c8aa !important;
        }
        </style>
        """, unsafe_allow_html=True)
        
        spacer_left, col_left, col_gap, col_right, spacer_right = st.columns([0.4, 3.2, 0.6, 2, 0.1])
        
        with col_left:
            # 嵌入成功 - 無框版
            st.markdown(f'<p style="font-size: 32px; font-weight: bold; color: #4f7343; margin-bottom: 25px;">嵌入成功！({r["elapsed_time"]:.2f} 秒)</p>', unsafe_allow_html=True)
            
            style_num = r.get("style_num", 1)
            style_name = NUM_TO_STYLE.get(style_num, "建築")
            img_num = r["embed_image_choice"].split("-")[1]
            img_name = r.get("image_name", "")
            img_size = r.get("image_size", "")
            secret_filename = r.get("secret_filename", "")
            secret_bits = r.get("secret_bits", 0)
            capacity = r.get("capacity", 0)
            usage_percent = r.get("usage_percent", 0)
            
            if r['embed_secret_type'] == "文字":
                # 截斷顯示：超過30字顯示省略號
                original_text = r["secret_desc"].replace('文字: "', '').rstrip('"')
                if len(original_text) > 30:
                    truncated_text = original_text[:30] + "..."
                    secret_display = f'文字："{truncated_text}"'
                else:
                    secret_display = f'文字："{original_text}"'
            else:
                size_info = r["secret_desc"].replace("圖像: ", "")
                secret_display = f'圖像：{secret_filename} ({size_info})' if secret_filename else r["secret_desc"]
            
            # 嵌入資訊 - 無框版
            st.markdown(f'''
            <div style="font-size: 28px; color: #4f7343; line-height: 2;">
                <p style="font-weight: bold; font-size: 32px; margin-bottom: 8px; color: #4f7343;">嵌入資訊</p>
                <b>載體風格：{style_num}. {style_name}</b><br>
                <b>載體圖像編號：{img_num}（{img_name}）</b><br>
                <b>載體圖像尺寸：{img_size}×{img_size}</b><br>
                <b>機密內容：</b><br>
                <b>{secret_display}</b>
            </div>
            ''', unsafe_allow_html=True)
        
        with col_right:
            if r['embed_secret_type'] == "文字":
                z_text = ''.join(str(b) for b in r['z_bits'])
                style_num = r.get("style_num", 1)
                img_num = r["embed_image_choice"].split("-")[1]
                img_size = r["embed_image_choice"].split("-")[2]
                # 格式: 風格編號-圖像編號-尺寸|Z碼
                qr_content = f"{style_num}-{img_num}-{img_size}|{z_text}"
                
                try:
                    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=2)
                    qr.add_data(qr_content)
                    qr.make(fit=True)
                    qr_pil = qr.make_image(fill_color="black", back_color="white").convert('RGB')
                    
                    buf = BytesIO()
                    qr_pil.save(buf, format='PNG')
                    qr_bytes = buf.getvalue()
                    
                    st.markdown('<p style="font-size: 38px; font-weight: bold; color: #443C3C; margin-bottom: 25px;">Z碼圖</p>', unsafe_allow_html=True)
                    st.image(qr_bytes, width=200)
                    st.download_button("下載 Z碼圖", qr_bytes, "z_code.png", "image/png", key="dl_z_qr")
                    st.markdown('<p style="font-size: 38px; color: #443C3C; margin-top: 25px; margin-bottom: 0;">傳送 Z碼圖給對方</p>', unsafe_allow_html=True)
                    st.markdown('<p style="font-size: 30px; color: #888; margin-top: 5px; white-space: nowrap;">接收方需要此 Z碼圖才能提取機密</p>', unsafe_allow_html=True)
                except:
                    style_num_int = int(style_num)
                    img_num_int = int(img_num)
                    img_size_int = int(img_size)
                    z_img, _ = encode_z_as_image_with_header(r['z_bits'], style_num_int, img_num_int, img_size_int)
                    
                    st.markdown('<p style="font-size: 38px; font-weight: bold; color: #443C3C; margin-bottom: 25px;">Z碼圖</p>', unsafe_allow_html=True)
                    st.image(z_img, width=200)
                    buf = BytesIO()
                    z_img.save(buf, format='PNG')
                    st.download_button("下載 Z碼圖", buf.getvalue(), "z_code.png", "image/png", key="dl_z_img_fallback")
                    st.markdown('<p style="font-size: 38px; color: #443C3C; margin-top: 25px; margin-bottom: 0;">傳送 Z碼圖給對方</p>', unsafe_allow_html=True)
                    st.markdown('<p style="font-size: 30px; color: #888; margin-top: 5px; white-space: nowrap;">接收方需要此 Z碼圖才能提取機密</p>', unsafe_allow_html=True)
            else:
                style_num = r.get("style_num", 1)
                img_num = int(r["embed_image_choice"].split("-")[1])
                img_size = int(r["embed_image_choice"].split("-")[2])
                z_img, _ = encode_z_as_image_with_header(r['z_bits'], style_num, img_num, img_size)
                
                st.markdown('<p style="font-size: 38px; font-weight: bold; color: #443C3C; margin-bottom: 25px;">Z碼圖</p>', unsafe_allow_html=True)
                st.image(z_img, width=200)
                buf = BytesIO()
                z_img.save(buf, format='PNG')
                st.download_button("下載 Z碼圖", buf.getvalue(), "z_code.png", "image/png", key="dl_z_img")
                st.markdown('<p style="font-size: 38px; color: #443C3C; margin-top: 25px; margin-bottom: 0;">傳送 Z碼圖給對方</p>', unsafe_allow_html=True)
                st.markdown('<p style="font-size: 30px; color: #888; margin-top: 5px; white-space: nowrap;">接收方需要此 Z碼圖才能提取機密</p>', unsafe_allow_html=True)
        
        # 返回首頁按鈕 - 和開始嵌入按鈕一樣固定在底部
        _, btn_col, _ = st.columns([1, 1, 1])
        with btn_col:
            if st.button("返回首頁", key="back_to_home_from_embed", type="primary"):
                st.session_state.embed_page = 'input'
                st.session_state.embed_result = None
                st.session_state.embed_step = 1
                st.session_state.current_mode = None
                st.rerun()
        
        # 固定定位到底部中央（和開始嵌入按鈕一樣）
        components.html("""
        <script>
        function fixBackButton() {
            const buttons = window.parent.document.querySelectorAll('button');
            for (let btn of buttons) { 
                if (btn.innerText === '返回首頁') {
                    let container = btn.closest('.stButton') || btn.parentElement.parentElement.parentElement;
                    if (container) {
                        container.style.cssText = 'position:fixed!important;bottom:85px!important;left:50%!important;transform:translateX(-50%)!important;width:auto!important;z-index:1000!important;';
                    }
                }
            }
        }
        fixBackButton();
        setTimeout(fixBackButton, 100);
        setTimeout(fixBackButton, 300);
        </script>
        """, height=0)
    
    # 輸入頁
    else:
        st.session_state.embed_page = 'input'
        st.markdown('<div id="sidebar-toggle-label" style="background: #4A6B8A !important;">對象管理</div>', unsafe_allow_html=True)
        
        components.html("""
<script>
(function() {
    const doc = window.parent.document;
    const label = doc.getElementById('sidebar-toggle-label');
    if (label) {
        label.style.setProperty('background', '#4A6B8A', 'important');
    }
    
    function closeSidebar() {
        const sidebar = doc.querySelector('[data-testid="stSidebar"]');
        const label = doc.getElementById('sidebar-toggle-label');
        if (sidebar) sidebar.classList.remove('sidebar-open');
        if (label) label.style.display = 'block';
    }
    
    function openSidebar() {
        const sidebar = doc.querySelector('[data-testid="stSidebar"]');
        const label = doc.getElementById('sidebar-toggle-label');
        if (sidebar) sidebar.classList.add('sidebar-open');
        if (label) label.style.display = 'none';
    }
    
    function setup() {
        const label = doc.getElementById('sidebar-toggle-label');
        if (label && !label.hasAttribute('data-bound')) {
            label.setAttribute('data-bound', 'true');
            label.addEventListener('click', openSidebar);
        }
        const closeBtn = doc.getElementById('sidebar-close-btn');
        if (closeBtn) closeBtn.onclick = closeSidebar;
    }
    
    setup();
    setTimeout(setup, 100);
    setTimeout(setup, 500);
    new MutationObserver(setup).observe(doc.body, { childList: true, subtree: true });
})();
</script>
""", height=0)
        
        st.markdown('<div class="page-title-embed" style="text-align: center; margin-bottom: 10px; margin-top: -0.8rem;">嵌入機密</div>', unsafe_allow_html=True)
        
        embed_text, embed_image, secret_bits_needed = None, None, 0
        embed_image_choice, selected_size = None, None
        
        contacts = st.session_state.contacts
        contact_names = list(contacts.keys())
        
        # 初始化狀態
        if 'embed_step1_done' not in st.session_state:
            st.session_state.embed_step1_done = False
        if 'embed_step2_done' not in st.session_state:
            st.session_state.embed_step2_done = False
        
        # 檢查各步驟完成狀態
        selected_contact = st.session_state.get('selected_contact_saved', None)
        step1_done = selected_contact and selected_contact != "選擇"
        
        secret_bits_saved = st.session_state.get('secret_bits_saved', 0)
        step2_done = secret_bits_saved > 0
        
        # 三欄並排佈局 - 加大寬度 + 固定不滾動
        st.markdown("""
        <style>
        /* 強制允許頁面滾動 - 覆蓋首頁的 overflow: hidden */
        html, body, [data-testid="stAppViewContainer"], .main, [data-testid="stMain"] {
            overflow: auto !important;
            height: auto !important;
            min-height: 100vh !important;
        }
        
        [data-testid="stMain"] [data-testid="stHorizontalBlock"] {
            max-width: 100% !important;
            width: 100% !important;
            gap: 2rem !important;
        }
        
        /* 頁面可滾動 */
        .block-container {
            padding-bottom: 120px !important;
            overflow: auto !important;
            height: auto !important;
        }
        
        /* 小螢幕適配 (14吋筆電通常 ≤ 900px 高度) */
        @media (max-height: 800px) {
            .block-container {
                padding-bottom: 140px !important;
            }
        }
        </style>
        """, unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([1, 1.4, 1.4], gap="large")
        
        # ===== 第一步：選擇對象 =====
        with col1:
            st.markdown(f"""
            <div style="text-align: center; padding: 10px; border-bottom: 4px solid #4A6B8A; margin-bottom: 8px;">
                <span style="font-size: 32px; font-weight: bold; color: #4A6B8A;">第一步：選擇對象</span>
            </div>
            """, unsafe_allow_html=True)
            
            if contact_names:
                options = ["選擇"] + contact_names
                saved_contact = st.session_state.get('selected_contact_saved', None)
                default_idx = options.index(saved_contact) if saved_contact and saved_contact in options else 0
                
                selected = st.selectbox("對象", options, index=default_idx, key="contact_select_h", label_visibility="collapsed")
                
                if selected != "選擇":
                    st.session_state.selected_contact_saved = selected
                    st.markdown(f'<div class="selected-info">已選擇對象：{selected}</div>', unsafe_allow_html=True)
                    step1_done = True
                else:
                    st.session_state.selected_contact_saved = None
                    step1_done = False
                    # 未選擇時顯示提示
                    st.markdown('<div class="hint-text" style="margin-top: 10px; font-size: 22px !important;">💡 點擊「對象管理」可修改資料</div>', unsafe_allow_html=True)
            else:
                st.markdown("""<div style="background: #fff2cc; border: none; border-radius: 8px; padding: 15px; text-align: center;">
                    <div style="font-size: 24px; font-weight: bold; color: #856404;">⚠️ 尚無對象</div>
                    <div style="font-size: 24px; color: #856404; margin-top: 8px;">點擊「對象管理」新增</div>
                </div>""", unsafe_allow_html=True)
        
        # ===== 第二步：機密內容 =====
        with col2:
            st.markdown(f"""
            <div style="text-align: center; padding: 10px; border-bottom: {'4px solid #B8C8D8' if not step1_done else '4px solid #4A6B8A'}; margin-bottom: 8px;">
                <span style="font-size: 32px; font-weight: bold; color: {'#B8C8D8' if not step1_done else '#4A6B8A'};">第二步：機密內容</span>
            </div>
            """, unsafe_allow_html=True)
            
            if step1_done:
                saved_type = st.session_state.get('embed_secret_type_saved', '文字')
                
                # Tab 按鈕切換
                tab_col1, tab_col2 = st.columns([1, 1], gap="small")
                with tab_col1:
                    if st.button("文字", key="tab_text_btn", use_container_width=True, type="primary" if saved_type == "文字" else "secondary"):
                        if saved_type != "文字":
                            # 從圖像切換到文字，清除圖像資料
                            for key in ['embed_secret_image_data', 'embed_secret_image_name']:
                                if key in st.session_state:
                                    del st.session_state[key]
                            st.session_state.secret_bits_saved = 0
                            st.session_state.embed_secret_type_saved = "文字"
                            st.rerun()
                with tab_col2:
                    if st.button("圖像", key="tab_image_btn", use_container_width=True, type="primary" if saved_type == "圖像" else "secondary"):
                        if saved_type != "圖像":
                            # 從文字切換到圖像，清除文字資料
                            if 'embed_text_saved' in st.session_state:
                                del st.session_state['embed_text_saved']
                            st.session_state.secret_bits_saved = 0
                            st.session_state.embed_secret_type_saved = "圖像"
                            st.rerun()
                
                embed_secret_type = saved_type
                
                if embed_secret_type == "文字":
                    saved_text = st.session_state.get('embed_text_saved', '')
                    embed_text_raw = st.text_area("輸入機密", value=saved_text, placeholder="輸入機密訊息...", height=150, key="embed_text_h", label_visibility="collapsed")
                    if embed_text_raw and embed_text_raw.strip():
                        embed_text = embed_text_raw.strip()
                        secret_bits_needed = len(text_to_binary(embed_text))
                        st.session_state.secret_bits_saved = secret_bits_needed
                        st.session_state.embed_text_saved = embed_text
                        st.session_state.embed_secret_type_saved = "文字"
                        
                        # 計算字數
                        char_count = len(embed_text)
                        st.markdown(f'<div class="bits-info">機密文字：{char_count} 字<br>所需容量：{secret_bits_needed:,} bits</div>', unsafe_allow_html=True)
                        step2_done = True
                    else:
                        st.session_state.secret_bits_saved = 0
                        step2_done = False
                else:
                    embed_img_file = st.file_uploader("上傳圖像", type=["jpg", "jpeg", "png"], key="embed_img_h", label_visibility="collapsed")
                    if embed_img_file:
                        embed_img_file.seek(0)
                        secret_img = Image.open(embed_img_file)
                        secret_bits_needed, _ = calculate_required_bits_for_image(secret_img)
                        st.session_state.secret_bits_saved = secret_bits_needed
                        st.session_state.embed_secret_type_saved = "圖像"
                        embed_img_file.seek(0)
                        st.session_state.embed_secret_image_data = embed_img_file.read()
                        st.session_state.embed_secret_image_name = embed_img_file.name
                        st.image(secret_img, width=180)
                        st.markdown(f'<div class="bits-info">機密圖像：{st.session_state.embed_secret_image_name} ({secret_img.size[0]}×{secret_img.size[1]} px)<br>所需容量：{secret_bits_needed:,} bits</div>', unsafe_allow_html=True)
                        step2_done = True
                    elif st.session_state.get('embed_secret_image_data'):
                        secret_img = Image.open(BytesIO(st.session_state.embed_secret_image_data))
                        st.image(secret_img, width=180)
                        secret_img_name = st.session_state.get('embed_secret_image_name', 'image.png')
                        st.markdown(f'<div class="bits-info">機密圖像：{secret_img_name} ({secret_img.size[0]}×{secret_img.size[1]} px)<br>所需容量：{st.session_state.get("secret_bits_saved", 0):,} bits</div>', unsafe_allow_html=True)
                        step2_done = True
                    else:
                        st.session_state.secret_bits_saved = 0
                        step2_done = False
            else:
                st.markdown('<p style="font-size: 24px; color: #999; text-align: center;">請先完成第一步</p>', unsafe_allow_html=True)
        
        # ===== 第三步：載體圖像 =====
        with col3:
            st.markdown(f"""
            <div style="text-align: center; padding: 10px; border-bottom: {'4px solid #B8C8D8' if not step2_done else '4px solid #4A6B8A'}; margin-bottom: 8px;">
                <span style="font-size: 32px; font-weight: bold; color: {'#B8C8D8' if not step2_done else '#4A6B8A'};">第三步：載體圖像</span>
            </div>
            """, unsafe_allow_html=True)
            
            if step2_done:
                secret_bits_needed = st.session_state.get('secret_bits_saved', 0)
                selected_contact = st.session_state.get('selected_contact_saved', '選擇')
                
                style_list = list(STYLE_CATEGORIES.keys())
                auto_style = get_contact_style(contacts, selected_contact)
                # 找到對應的帶編號風格
                default_style_index = 0
                if auto_style:
                    for i, style_key in enumerate(style_list):
                        if STYLE_CATEGORIES[style_key] == auto_style or style_key == auto_style:
                            default_style_index = i
                            break
                
                # 第一行：風格、圖像
                row1_col1, row1_col2 = st.columns([1.5, 2.5])
                
                with row1_col1:
                    selected_style = st.selectbox("風格", style_list, index=default_style_index, key="embed_style_h")
                
                style_name = STYLE_CATEGORIES.get(selected_style, "建築")
                style_num = STYLE_TO_NUM.get(selected_style, 1)
                images = IMAGE_LIBRARY.get(style_name, [])
                
                if images:
                    image_options = [f"{i+1}. {images[i]['name']}" for i in range(len(images))]
                    
                    with row1_col2:
                        img_idx = st.selectbox("圖像", range(len(images)), format_func=lambda i: image_options[i], key="embed_img_select_h")
                    
                    available_sizes = [s for s in AVAILABLE_SIZES if calculate_image_capacity(s) >= secret_bits_needed]
                    if not available_sizes:
                        available_sizes = [AVAILABLE_SIZES[-1]]
                    recommended_size = available_sizes[0]
                    
                    size_options = [f"{s}×{s} ⭐ 推薦" if s == recommended_size else f"{s}×{s}" for s in available_sizes]
                    
                    # 第二行：尺寸
                    size_idx = st.selectbox("尺寸", range(len(available_sizes)), format_func=lambda i: size_options[i], key="embed_size_h")
                    selected_size = available_sizes[size_idx]
                    
                    selected_image = images[img_idx]
                    
                    # 載體圖和容量信息並排（水平對齊）
                    capacity = calculate_image_capacity(selected_size)
                    usage = secret_bits_needed / capacity * 100
                    
                    st.markdown(f'''
                    <div style="display: flex; align-items: center; gap: 25px; margin-top: 10px;">
                        <div style="flex-shrink: 0;">
                            <img src="https://images.pexels.com/photos/{selected_image["id"]}/pexels-photo-{selected_image["id"]}.jpeg?auto=compress&cs=tinysrgb&w=200&h=200&fit=crop" 
                                 style="width: 200px; height: 200px; object-fit: cover; border-radius: 8px;">
                        </div>
                        <div style="color: #4f7343; font-size: 28px; font-weight: bold; line-height: 1.8; white-space: nowrap;">
                            機密大小：{secret_bits_needed:,} bits<br>
                            圖像容量：{capacity:,} bits<br>
                            使用率：{usage:.1f}%
                        </div>
                    </div>
                    ''', unsafe_allow_html=True)
                    
                    st.session_state.embed_image_id = selected_image["id"]
                    st.session_state.embed_image_size = selected_size
                    st.session_state.embed_image_name = selected_image["name"]
                    st.session_state.embed_style_num = style_num
                    embed_image_choice = f"{style_name}-{img_idx+1}-{selected_size}"
            else:
                st.markdown('<p style="font-size: 24px; color: #999; text-align: center;">請先完成第二步</p>', unsafe_allow_html=True)
        
        # ===== 返回按鈕（左下角）=====
        if st.button("返回", key="embed_back_btn", type="secondary"):
            # 清除嵌入相關狀態
            for key in ['selected_contact_saved', 'secret_bits_saved', 'embed_text_saved', 
                        'embed_secret_type_saved', 'embed_secret_image_data', 'embed_secret_image_name',
                        'embed_image_id', 'embed_image_size', 'embed_image_name', 'embed_style_num']:
                if key in st.session_state:
                    del st.session_state[key]
            st.session_state.current_mode = None
            st.rerun()
        
        # ===== 開始嵌入按鈕 =====
        all_done = step1_done and step2_done and st.session_state.get('embed_image_id')
        
        if all_done:
            btn_col1, btn_col2, btn_col3 = st.columns([1, 0.5, 1])
            with btn_col2:
                if st.button("開始嵌入", type="primary", key="embed_btn_horizontal", use_container_width=True):
                    st.session_state.trigger_embed = True
            
            # 固定開始嵌入按鈕到底部中央
            components.html("""
            <script>
            function fixEmbedButton() {
                const buttons = window.parent.document.querySelectorAll('button');
                for (let btn of buttons) { 
                    if (btn.innerText === '開始嵌入') {
                        btn.style.cssText += 'min-width:120px!important;padding:0.5rem 2rem!important;';
                        let container = btn.closest('.stButton') || btn.parentElement.parentElement.parentElement;
                        if (container) {
                            container.style.cssText = 'position:fixed!important;bottom:85px!important;left:50%!important;transform:translateX(-50%)!important;width:auto!important;z-index:1000!important;';
                        }
                    }
                }
            }
            fixEmbedButton();
            setTimeout(fixEmbedButton, 100);
            setTimeout(fixEmbedButton, 300);
            </script>
            """, height=0)
        
        # 固定返回按鈕到左下角
        components.html("""
        <script>
        function fixEmbedBackButton() {
            const buttons = window.parent.document.querySelectorAll('button');
            for (let btn of buttons) { 
                if (btn.innerText === '返回') {
                    btn.style.cssText += 'min-width:60px!important;padding:0.3rem 0.8rem!important;font-size:16px!important;';
                    let container = btn.closest('.stButton') || btn.parentElement.parentElement.parentElement;
                    if (container) {
                        container.style.cssText = 'position:fixed!important;bottom:85px!important;left:80px!important;width:auto!important;z-index:1000!important;';
                    }
                }
            }
        }
        fixEmbedBackButton();
        setTimeout(fixEmbedBackButton, 100);
        setTimeout(fixEmbedBackButton, 300);
        </script>
        """, height=0)
        
        if all_done and st.session_state.get('trigger_embed'):
            st.session_state.trigger_embed = False
            processing_placeholder = st.empty()
            processing_placeholder.markdown("""
            <div style="position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); z-index: 9999; display: flex; justify-content: center; align-items: center;">
                <div style="background: white; padding: 40px 60px; border-radius: 16px; text-align: center;">
                    <div style="font-size: 32px; font-weight: bold; color: #5D6D7E; margin-bottom: 10px;">🔄 嵌入中...</div>
                    <div style="font-size: 20px; color: #888;">請稍候，正在處理您的機密資料</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            try:
                start = time.time()
                image_id = st.session_state.get('embed_image_id')
                image_size = st.session_state.get('embed_image_size')
                style_num = st.session_state.get('embed_style_num', 1)
                _, img_process = download_image_by_id(image_id, image_size)
                capacity = calculate_image_capacity(image_size)
                
                # 取得對象密鑰
                selected_contact = st.session_state.get('selected_contact_saved', None)
                contact_key = get_contact_key(st.session_state.contacts, selected_contact) if selected_contact else None
                
                embed_secret_type = st.session_state.get('embed_secret_type_saved', '文字')
                embed_text = st.session_state.get('embed_text_saved', None)
                
                if embed_secret_type == "文字" and embed_text:
                    secret_content = embed_text
                    secret_type_flag = 'text'
                    secret_desc = f'文字: "{embed_text}"'
                    secret_filename = None
                elif embed_secret_type == "圖像":
                    secret_img_data = st.session_state.get('embed_secret_image_data')
                    if secret_img_data:
                        secret_content = Image.open(BytesIO(secret_img_data))
                        secret_type_flag = 'image'
                        secret_desc = f"圖像: {secret_content.size[0]}×{secret_content.size[1]} px"
                        secret_filename = st.session_state.get('embed_secret_image_name', 'image.png')
                
                # 傳入 contact_key 進行嵌入
                z_bits, used_capacity, info = embed_secret(img_process, secret_content, secret_type=secret_type_flag, contact_key=contact_key)
                processing_placeholder.empty()
                
                st.session_state.embed_result = {
                    'success': True, 'elapsed_time': time.time()-start,
                    'embed_image_choice': embed_image_choice, 'secret_desc': secret_desc,
                    'embed_secret_type': embed_secret_type, 'z_bits': z_bits,
                    'image_name': st.session_state.get('embed_image_name', ''),
                    'image_size': image_size, 'secret_filename': secret_filename,
                    'secret_bits': info['bits'], 'capacity': capacity,
                    'usage_percent': info['bits']*100/capacity,
                    'style_num': style_num
                }
                for key in ['selected_contact_saved', 'secret_bits_saved', 'embed_text_saved', 'embed_secret_type_saved', 'embed_secret_image_data', 'embed_secret_image_name']:
                    if key in st.session_state:
                        del st.session_state[key]
                st.session_state.embed_page = 'result'
                st.rerun()
            except Exception as e:
                processing_placeholder.empty()
                st.markdown(f'<div class="error-box">❌ 嵌入失敗! {e}</div>', unsafe_allow_html=True)

else:
    # ==================== 提取模式 ====================
    
    if 'extract_page' not in st.session_state:
        st.session_state.extract_page = 'input'
    
    # 結果頁
    if st.session_state.extract_page == 'result' and st.session_state.extract_result and st.session_state.extract_result.get('success'):
        st.markdown("""
        <style>
        .main { overflow: auto !important; }
        
        /* 下載圖像按鈕樣式 */
        [data-testid="stDownloadButton"] button {
            background-color: #c9b89a !important;
            color: #443C3C !important;
            border: none !important;
            font-weight: 700 !important;
            font-size: 24px !important;
            min-width: 120px !important;
            padding: 8px 18px !important;
        }
        [data-testid="stDownloadButton"] button p,
        [data-testid="stDownloadButton"] button span {
            font-weight: 700 !important;
            font-size: 24px !important;
        }
        [data-testid="stDownloadButton"] button:hover {
            background-color: #b8a788 !important;
        }
        </style>
        """, unsafe_allow_html=True)
        
        r = st.session_state.extract_result
        
        st.markdown('<div class="page-title-extract" style="text-align: center; margin-bottom: 30px;">提取結果</div>', unsafe_allow_html=True)
        
        if r['type'] == 'text':
            is_garbled = r.get('is_garbled', False)
            
            # 格式化函數
            def format_text_display(text):
                result = html.escape(text)
                result = result.replace('\r\n', '<br>')
                result = result.replace('\n', '<br>')
                result = result.replace('\r', '<br>')
                return result
            
            if is_garbled:
                # ===== 亂碼情況：提取失敗（置中）=====
                spacer1, center_col, spacer2 = st.columns([1, 2, 1])
                
                with center_col:
                    st.markdown(f'<p style="font-size: 28px; font-weight: bold; color: #C62828; margin-bottom: 15px; text-align: center;">提取失敗 ({r["elapsed_time"]:.2f} 秒)</p>', unsafe_allow_html=True)
                    st.markdown('<p style="font-size: 24px; font-weight: bold; color: #C62828; text-align: center;">機密文字:</p>', unsafe_allow_html=True)
                    display_text = r["content"][:100] + "..." if len(r["content"]) > 100 else r["content"]
                    st.markdown(f'<p style="font-size: 18px; color: #666; line-height: 1.6; word-break: break-all; text-align: center;">{html.escape(display_text)}</p>', unsafe_allow_html=True)
            
            else:
                # ===== 正常情況：提取成功 =====
                col1, col2, col3 = st.columns([1.4, 1.2, 1.4])
                
                with col1:
                    st.markdown(f'<p style="font-size: 28px; font-weight: bold; color: #4f7343; margin-bottom: 15px;">提取成功！({r["elapsed_time"]:.2f} 秒)</p>', unsafe_allow_html=True)
                    st.markdown('<p style="font-size: 24px; font-weight: bold; color: #4f7343;">機密文字:</p>', unsafe_allow_html=True)
                    content_html = format_text_display(r["content"])
                    st.markdown(f'<p style="font-size: 20px; color: #4f7343; line-height: 1.8;">{content_html}</p>', unsafe_allow_html=True)
                
                with col2:
                    st.markdown('<p style="font-size: 24px; font-weight: bold; color: #443C3C;">驗證</p>', unsafe_allow_html=True)
                    verify_input = st.text_area("輸入原始機密", key="verify_text_input", height=180, placeholder="貼上嵌入時的原始機密內容...", label_visibility="collapsed")
                    verify_clicked = st.button("驗證", key="verify_btn")
                    if verify_clicked and verify_input:
                        st.session_state.verify_result = {
                            'input': verify_input,
                            'match': verify_input == r['content']
                        }
                    
                    components.html("""
                    <script>
                    function fixVerifyTextBtn() {
                        const buttons = window.parent.document.querySelectorAll('button');
                        for (let btn of buttons) { 
                            if (btn.innerText === '驗證') {
                                btn.style.setProperty('background-color', '#c9b89a', 'important');
                                btn.style.setProperty('border-color', '#c9b89a', 'important');
                                btn.style.setProperty('color', '#443C3C', 'important');
                                btn.style.setProperty('font-size', '16px', 'important');
                                btn.style.setProperty('font-weight', '700', 'important');
                                btn.style.setProperty('padding', '4px 12px', 'important');
                                btn.style.setProperty('min-width', '60px', 'important');
                            }
                        }
                    }
                    fixVerifyTextBtn();
                    setTimeout(fixVerifyTextBtn, 100);
                    setTimeout(fixVerifyTextBtn, 300);
                    </script>
                    """, height=0)
                
                with col3:
                    st.markdown('<p style="font-size: 24px; font-weight: bold; color: #443C3C;">結果</p>', unsafe_allow_html=True)
                    if 'verify_result' in st.session_state and st.session_state.verify_result:
                        vr = st.session_state.verify_result
                        if vr['match']:
                            st.markdown('<p style="font-size: 22px; font-weight: bold; color: #4f7343; margin-bottom: 10px;">完全一致！</p>', unsafe_allow_html=True)
                        else:
                            st.markdown('<p style="font-size: 22px; font-weight: bold; color: #C62828; margin-bottom: 10px;">不一致！</p>', unsafe_allow_html=True)
                        
                        input_html = format_text_display(vr["input"])
                        result_html = format_text_display(r["content"])
                        st.markdown(f'''
                        <div style="display: flex; gap: 15px;">
                            <div style="flex: 1;">
                                <p style="font-size: 14px; font-weight: bold; color: #443C3C; margin-bottom: 5px;">原始輸入：</p>
                                <p style="font-size: 12px; color: #666; line-height: 1.6;">{input_html}</p>
                            </div>
                            <div style="flex: 1;">
                                <p style="font-size: 14px; font-weight: bold; color: #443C3C; margin-bottom: 5px;">提取結果：</p>
                                <p style="font-size: 12px; color: #666; line-height: 1.6;">{result_html}</p>
                            </div>
                        </div>
                        ''', unsafe_allow_html=True)
                    else:
                        st.markdown('<p style="font-size: 16px; color: #999; margin-top: 30px;">← 輸入原始機密後<br>按「驗證」查看結果</p>', unsafe_allow_html=True)
        
        else:
            is_garbled = r.get('is_garbled', False)
            
            if is_garbled:
                # ===== 亂碼情況：提取失敗（置中）=====
                img_b64 = base64.b64encode(r['image_data']).decode()
                st.markdown(f'''
                <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; width: 100%;">
                    <p style="font-size: 28px; font-weight: bold; color: #C62828; margin-bottom: 15px;">提取失敗 ({r["elapsed_time"]:.2f} 秒)</p>
                    <p style="font-size: 24px; font-weight: bold; color: #C62828;">機密圖像:</p>
                    <img src="data:image/png;base64,{img_b64}" style="width: 300px !important; min-width: 300px !important; height: auto; border-radius: 8px; margin-top: 10px;">
                </div>
                ''', unsafe_allow_html=True)
            
            else:
                # ===== 正常情況：提取成功 =====
                spacer_left, col_left, col_gap, col_right, spacer_right = st.columns([0.4, 2.5, 0.1, 2.2, 0.1])
                with col_left:
                    st.markdown(f'<p style="font-size: 32px; font-weight: bold; color: #4f7343; margin-bottom: 25px;">提取成功！({r["elapsed_time"]:.2f} 秒)</p>', unsafe_allow_html=True)
                    st.markdown('<p style="font-size: 32px; font-weight: bold; color: #4f7343;">機密圖像:</p>', unsafe_allow_html=True)
                    st.image(Image.open(BytesIO(r['image_data'])), width=200)
                    st.download_button("下載圖像", r['image_data'], "recovered.png", "image/png", key="dl_rec")
                
                with col_right:
                    st.markdown('<p style="font-size: 34px; font-weight: bold; color: #443C3C;">驗證結果</p>', unsafe_allow_html=True)
                    verify_img = st.file_uploader("上傳原始機密圖像", type=["png", "jpg", "jpeg"], key="verify_img_upload")
                    if verify_img:
                        orig_img = Image.open(verify_img)
                        extracted_img = Image.open(BytesIO(r['image_data']))
                        
                        col_orig, col_ext = st.columns(2)
                        with col_orig:
                            st.markdown('<p style="font-size: 20px; font-weight: bold; color: #443C3C;">原始圖像</p>', unsafe_allow_html=True)
                            st.image(orig_img, width=150)
                        with col_ext:
                            st.markdown('<p style="font-size: 20px; font-weight: bold; color: #443C3C;">提取結果</p>', unsafe_allow_html=True)
                            st.image(extracted_img, width=150)
                        
                        if st.button("驗證", key="verify_img_btn"):
                            orig_arr = np.array(orig_img.convert('RGB'))
                            ext_arr = np.array(extracted_img.convert('RGB'))
                            
                            if orig_arr.shape == ext_arr.shape:
                                mse = np.mean((orig_arr.astype(int) - ext_arr.astype(int)) ** 2)
                                st.session_state.verify_img_result = {
                                    'mse': mse,
                                    'same_size': True
                                }
                            else:
                                st.session_state.verify_img_result = {
                                    'same_size': False,
                                    'orig_size': orig_img.size,
                                    'ext_size': extracted_img.size
                                }
                        
                        components.html("""
                        <script>
                        function fixVerifyImgBtn() {
                            const buttons = window.parent.document.querySelectorAll('button');
                            for (let btn of buttons) { 
                                if (btn.innerText === '驗證') {
                                    btn.style.setProperty('background-color', '#c9b89a', 'important');
                                    btn.style.setProperty('border-color', '#c9b89a', 'important');
                                    btn.style.setProperty('color', '#443C3C', 'important');
                                    btn.style.setProperty('font-size', '16px', 'important');
                                    btn.style.setProperty('font-weight', '700', 'important');
                                    btn.style.setProperty('padding', '4px 12px', 'important');
                                    btn.style.setProperty('min-width', '60px', 'important');
                                }
                            }
                        }
                        fixVerifyImgBtn();
                        setTimeout(fixVerifyImgBtn, 100);
                        setTimeout(fixVerifyImgBtn, 300);
                        </script>
                        """, height=0)
                        
                        if 'verify_img_result' in st.session_state and st.session_state.verify_img_result:
                            vr = st.session_state.verify_img_result
                            if vr.get('same_size'):
                                mse = vr['mse']
                                if mse == 0:
                                    st.markdown(f'<p style="font-size: 16px; color: #4f7343;">MSE：{mse:.4f} - 完全一致！</p>', unsafe_allow_html=True)
                                else:
                                    st.markdown(f'<p style="font-size: 16px; color: #F57C00;">MSE：{mse:.4f} - 圖像有差異</p>', unsafe_allow_html=True)
                            else:
                                st.markdown(f'<p style="font-size: 16px; color: #C62828;">尺寸不同，無法比較<br>原始：{vr["orig_size"][0]}×{vr["orig_size"][1]} vs 提取：{vr["ext_size"][0]}×{vr["ext_size"][1]}</p>', unsafe_allow_html=True)
        
        # 返回首頁按鈕 - 固定在底部中央
        _, btn_col, _ = st.columns([1, 1, 1])
        with btn_col:
            if st.button("返回首頁", key="back_to_home_from_extract", type="primary"):
                st.session_state.extract_page = 'input'
                st.session_state.extract_result = None
                st.session_state.current_mode = None
                st.session_state.verify_result = None
                st.session_state.verify_img_result = None
                st.rerun()
        
        components.html("""
        <script>
        function fixExtractBackButton() {
            const buttons = window.parent.document.querySelectorAll('button');
            for (let btn of buttons) { 
                if (btn.innerText === '返回首頁') {
                    // 按鈕顏色改成提取結果標題顏色
                    btn.style.setProperty('background-color', '#7D5A6B', 'important');
                    btn.style.setProperty('border-color', '#7D5A6B', 'important');
                    let container = btn.closest('.stButton') || btn.parentElement.parentElement.parentElement;
                    if (container) {
                        container.style.cssText = 'position:fixed!important;bottom:85px!important;left:50%!important;transform:translateX(-50%)!important;width:auto!important;z-index:1000!important;';
                    }
                }
                if (btn.innerText === '驗證') {
                    // 驗證按鈕顏色和下載Z碼圖一樣
                    btn.style.setProperty('background-color', '#c9b89a', 'important');
                    btn.style.setProperty('border-color', '#c9b89a', 'important');
                    btn.style.setProperty('color', '#443C3C', 'important');
                    btn.style.setProperty('font-size', '16px', 'important');
                    btn.style.setProperty('font-weight', '700', 'important');
                    btn.style.setProperty('padding', '4px 12px', 'important');
                    btn.style.setProperty('min-width', '60px', 'important');
                }
            }
        }
        fixExtractBackButton();
        setTimeout(fixExtractBackButton, 100);
        setTimeout(fixExtractBackButton, 300);
        setTimeout(fixExtractBackButton, 500);
        </script>
        """, height=0)
    
    # 輸入頁
    else:
        st.session_state.extract_page = 'input'
        st.markdown('<div id="sidebar-toggle-label" style="background: #7D5A6B !important;">對象管理</div>', unsafe_allow_html=True)
        
        components.html("""
<script>
(function() {
    const doc = window.parent.document;
    const label = doc.getElementById('sidebar-toggle-label');
    if (label) {
        label.style.setProperty('background', '#7D5A6B', 'important');
    }
    
    function closeSidebar() {
        const sidebar = doc.querySelector('[data-testid="stSidebar"]');
        const label = doc.getElementById('sidebar-toggle-label');
        if (sidebar) sidebar.classList.remove('sidebar-open');
        if (label) label.style.display = 'block';
    }
    function openSidebar() {
        const sidebar = doc.querySelector('[data-testid="stSidebar"]');
        const label = doc.getElementById('sidebar-toggle-label');
        if (sidebar) sidebar.classList.add('sidebar-open');
        if (label) label.style.display = 'none';
    }
    function setup() {
        const label = doc.getElementById('sidebar-toggle-label');
        if (label && !label.hasAttribute('data-bound')) {
            label.setAttribute('data-bound', 'true');
            label.addEventListener('click', openSidebar);
        }
        const closeBtn = doc.getElementById('sidebar-close-btn');
        if (closeBtn) closeBtn.onclick = closeSidebar;
    }
    setup();
    setTimeout(setup, 100);
    new MutationObserver(setup).observe(doc.body, { childList: true, subtree: true });
})();
</script>
""", height=0)
        
        st.markdown('<div class="page-title-extract" style="text-align: center; margin-bottom: 20px; margin-top: -0.8rem;">提取機密</div>', unsafe_allow_html=True)
        
        extract_z_text, extract_style_num, extract_img_num, extract_img_size = None, None, None, None
        
        contacts = st.session_state.contacts
        contact_names = list(contacts.keys())
        
        # 兩欄並排佈局 - 和嵌入機密一樣
        st.markdown("""
        <style>
        /* 強制允許頁面滾動 - 覆蓋首頁的 overflow: hidden */
        html, body, [data-testid="stAppViewContainer"], .main, [data-testid="stMain"] {
            overflow: auto !important;
            height: auto !important;
            min-height: 100vh !important;
        }
        
        [data-testid="stMain"] [data-testid="stHorizontalBlock"] {
            max-width: 100% !important;
            width: 100% !important;
            gap: 2rem !important;
        }
        .block-container {
            padding-bottom: 120px !important;
            overflow: auto !important;
            height: auto !important;
        }
        
        /* 小螢幕適配 */
        @media (max-height: 800px) {
            .block-container {
                padding-bottom: 140px !important;
            }
        }
        </style>
        """, unsafe_allow_html=True)
        
        # 預先從 session_state 讀取狀態
        saved_contact = st.session_state.get('extract_contact_saved', None)
        step1_done = saved_contact is not None and saved_contact in contact_names
        
        # 初始化提取變量
        extract_z_text = None
        extract_style_num = None
        extract_img_num = None
        extract_img_size = None
        
        col1, col2 = st.columns([1, 1], gap="large")
        
        # ===== 第一步：選擇對象 =====
        with col1:
            st.markdown(f"""
            <div style="text-align: center; padding: 10px; border-bottom: 4px solid #7D5A6B; margin-bottom: 8px;">
                <span style="font-size: 32px; font-weight: bold; color: #7D5A6B;">第一步：選擇對象</span>
            </div>
            """, unsafe_allow_html=True)
            
            if contact_names:
                options = ["選擇"] + contact_names
                default_idx = options.index(saved_contact) if saved_contact and saved_contact in options else 0
                
                selected_contact = st.selectbox("對象", options, index=default_idx, key="extract_contact_select", label_visibility="collapsed")
                
                if selected_contact != "選擇":
                    st.session_state.extract_contact_saved = selected_contact
                    st.markdown(f'<div class="selected-info">已選擇對象：{selected_contact}</div>', unsafe_allow_html=True)
                    step1_done = True
                else:
                    # 未選擇時顯示提示
                    st.markdown('<div class="hint-text" style="margin-top: 10px; font-size: 22px !important;">💡 點擊「對象管理」可修改資料</div>', unsafe_allow_html=True)
            else:
                st.markdown("""<div style="background: #fff2cc; border: none; border-radius: 8px; padding: 15px; text-align: center;">
                    <div style="font-size: 24px; font-weight: bold; color: #856404;">⚠️ 尚無對象</div>
                    <div style="font-size: 24px; color: #856404; margin-top: 8px;">點擊「對象管理」新增</div>
                </div>""", unsafe_allow_html=True)
        
        # ===== 第二步：上傳 Z碼圖 =====
        with col2:
            st.markdown(f"""
            <div style="text-align: center; padding: 10px; border-bottom: {'4px solid #D8C0C8' if not step1_done else '4px solid #7D5A6B'}; margin-bottom: 8px;">
                <span style="font-size: 32px; font-weight: bold; color: {'#D8C0C8' if not step1_done else '#7D5A6B'};">第二步：上傳 Z碼圖</span>
            </div>
            """, unsafe_allow_html=True)
            
            if step1_done:
                extract_file = st.file_uploader("上傳 QR Code 或 Z碼圖", type=["png", "jpg", "jpeg"], key="extract_z_upload", label_visibility="collapsed")
                
                if extract_file:
                    uploaded_img = Image.open(extract_file)
                    detected = False
                    success_msg = ""
                    error_msg = ""
                    
                    # 先嘗試 QR Code
                    try:
                        decode_qr = load_pyzbar()
                        decoded = decode_qr(uploaded_img)
                        if decoded:
                            qr_content = decoded[0].data.decode('utf-8')
                            if '|' in qr_content:
                                header, z_text = qr_content.split('|', 1)
                                parts = header.split('-')
                                if len(parts) == 3:
                                    # 新格式: 風格編號-圖像編號-尺寸
                                    extract_style_num = int(parts[0])
                                    extract_img_num = int(parts[1])
                                    extract_img_size = int(parts[2])
                                    extract_z_text = z_text
                                    style_name = NUM_TO_STYLE.get(extract_style_num, "建築")
                                    images = IMAGE_LIBRARY.get(style_name, [])
                                    img_name = images[extract_img_num - 1]['name'] if extract_img_num <= len(images) else str(extract_img_num)
                                    success_msg = f"Z碼圖額外資訊：<br>風格：{extract_style_num}. {style_name}，載體圖像：{extract_img_num}（{img_name}），尺寸：{extract_img_size}×{extract_img_size}"
                                    detected = True
                                elif len(parts) == 2:
                                    # 舊格式兼容: 圖像編號-尺寸
                                    extract_style_num = 1  # 默認建築
                                    extract_img_num = int(parts[0])
                                    extract_img_size = int(parts[1])
                                    extract_z_text = z_text
                                    style_name = NUM_TO_STYLE.get(extract_style_num, "建築")
                                    images = IMAGE_LIBRARY.get(style_name, [])
                                    img_name = images[extract_img_num - 1]['name'] if extract_img_num <= len(images) else str(extract_img_num)
                                    success_msg = f"Z碼圖額外資訊：<br>風格：{extract_style_num}. {style_name}，載體圖像：{extract_img_num}（{img_name}），尺寸：{extract_img_size}×{extract_img_size}"
                                    detected = True
                    except Exception as e:
                        error_msg = f"QR: {str(e)}"
                    
                    # 如果 QR 失敗，嘗試 Z碼圖
                    if not detected:
                        try:
                            z_bits, style_num, img_num, img_size = decode_image_to_z_with_header(uploaded_img)
                            extract_style_num = style_num
                            extract_img_num = img_num
                            extract_img_size = img_size
                            extract_z_text = ''.join(str(b) for b in z_bits)
                            style_name = NUM_TO_STYLE.get(extract_style_num, "建築")
                            images = IMAGE_LIBRARY.get(style_name, [])
                            img_name = images[extract_img_num - 1]['name'] if extract_img_num <= len(images) else str(extract_img_num)
                            success_msg = f"Z碼圖額外資訊：<br>風格：{extract_style_num}. {style_name}，載體圖像：{extract_img_num}（{img_name}），尺寸：{extract_img_size}×{extract_img_size}"
                            detected = True
                        except Exception as e:
                            if error_msg:
                                error_msg += f", {str(e)}"
                            else:
                                error_msg = str(e)
                    
                    # 顯示上傳的圖像和識別結果（並排）
                    if detected:
                        img_bytes = extract_file.getvalue()
                        img_b64 = base64.b64encode(img_bytes).decode()
                        st.markdown(f'''
                        <div style="display: flex; align-items: center; gap: 20px; margin-top: 10px;">
                            <div style="flex-shrink: 0;">
                                <img src="data:image/png;base64,{img_b64}" style="width: 180px; border-radius: 8px;">
                            </div>
                            <div style="font-size: 26px; color: #4f7343; font-weight: bold; line-height: 1.6;">
                                {success_msg}
                            </div>
                        </div>
                        ''', unsafe_allow_html=True)
                    else:
                        st.image(uploaded_img, width=150)
                        st.markdown(f'<p style="font-size: 22px; color: #C62828; margin-top: 10px;">無法識別</p>', unsafe_allow_html=True)
                        if error_msg:
                            st.markdown(f'<p style="font-size: 14px; color: #443C3C;">{error_msg}</p>', unsafe_allow_html=True)
            else:
                st.markdown('<p style="font-size: 24px; color: #999; text-align: center;">請先完成第一步</p>', unsafe_allow_html=True)
        
        # ===== 返回按鈕（左下角）=====
        if st.button("返回", key="extract_back_btn", type="secondary"):
            # 清除提取相關狀態
            for key in ['extract_contact_saved']:
                if key in st.session_state:
                    del st.session_state[key]
            st.session_state.current_mode = None
            st.rerun()
        
        # ===== 開始提取按鈕 =====
        if step1_done and extract_z_text and extract_style_num and extract_img_num and extract_img_size:
            btn_col1, btn_col2, btn_col3 = st.columns([1, 0.5, 1])
            with btn_col2:
                extract_btn = st.button("開始提取", type="primary", key="extract_start_btn")
            
            components.html("""
            <script>
            function fixExtractButtons() {
                const buttons = window.parent.document.querySelectorAll('button');
                for (let btn of buttons) { 
                    if (btn.innerText === '開始提取') {
                        // 按鈕顏色和寬度
                        btn.style.setProperty('background-color', '#7D5A6B', 'important');
                        btn.style.setProperty('border-color', '#7D5A6B', 'important');
                        btn.style.setProperty('color', 'white', 'important');
                        btn.style.setProperty('width', 'auto', 'important');
                        btn.style.setProperty('min-width', '60px', 'important');
                        btn.style.setProperty('padding', '0.5rem 1rem', 'important');
                        // 固定定位到底部中央
                        let container = btn.closest('.stButton') || btn.parentElement.parentElement.parentElement;
                        if (container) {
                            container.style.cssText = 'position:fixed!important;bottom:85px!important;left:50%!important;transform:translateX(-50%)!important;width:auto!important;z-index:1000!important;';
                        }
                    }
                }
            }
            fixExtractButtons();
            setTimeout(fixExtractButtons, 100);
            setTimeout(fixExtractButtons, 300);
            setTimeout(fixExtractButtons, 500);
            </script>
            """, height=0)
            
            if extract_btn:
                processing_placeholder = st.empty()
                processing_placeholder.markdown("""
                <div style="position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); z-index: 9999; display: flex; justify-content: center; align-items: center;">
                    <div style="background: white; padding: 40px 60px; border-radius: 16px; text-align: center;">
                        <div style="font-size: 32px; font-weight: bold; color: #5D6D7E; margin-bottom: 10px;">🔄 提取中...</div>
                        <div style="font-size: 20px; color: #888;">請稍候，正在解析您的機密資料</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                try:
                    start = time.time()
                    clean = ''.join(c for c in extract_z_text.strip() if c in '01')
                    Z = [int(b) for b in clean] if clean else None
                    
                    # 取得對象密鑰
                    selected_contact = st.session_state.get('extract_contact_saved', None)
                    contact_key = get_contact_key(st.session_state.contacts, selected_contact) if selected_contact else None
                    
                    if Z:
                        style_name = NUM_TO_STYLE.get(extract_style_num, "建築")
                        images = IMAGE_LIBRARY.get(style_name, [])
                        img_idx = extract_img_num - 1
                        
                        if img_idx < len(images):
                            selected_image = images[img_idx]
                            _, img_process = download_image_by_id(selected_image["id"], extract_img_size)
                            
                            # 傳入 contact_key 進行提取
                            secret, secret_type, info = detect_and_extract(img_process, Z, contact_key=contact_key)
                            processing_placeholder.empty()
                            
                            if secret_type == 'text':
                                is_garbled = is_likely_garbled_text(secret)
                                st.session_state.extract_result = {
                                    'success': True, 
                                    'type': 'text', 
                                    'elapsed_time': time.time()-start, 
                                    'content': secret,
                                    'is_garbled': is_garbled
                                }
                                
                            else:
                                buf = BytesIO()
                                secret.save(buf, format='PNG')
                                is_garbled = 'error' in info or is_likely_garbled_image(buf.getvalue())
                                st.session_state.extract_result = {
                                    'success': True, 
                                    'type': 'image', 
                                    'elapsed_time': time.time()-start, 
                                    'image_data': buf.getvalue(),
                                    'is_garbled': is_garbled
                                }
                            
                            for key in ['extract_contact_saved']:
                                if key in st.session_state:
                                    del st.session_state[key]
                            st.session_state.extract_page = 'result'
                            st.rerun()
                except Exception as e:
                    processing_placeholder.empty()
                    st.markdown(f'<div class="error-box">❌ 提取失敗! {e}</div>', unsafe_allow_html=True)
        
        # 固定返回按鈕到左下角
        components.html("""
        <script>
        function fixExtractBackButton() {
            const buttons = window.parent.document.querySelectorAll('button');
            for (let btn of buttons) { 
                if (btn.innerText === '返回') {
                    btn.style.cssText += 'min-width:60px!important;padding:0.3rem 0.8rem!important;font-size:16px!important;';
                    let container = btn.closest('.stButton') || btn.parentElement.parentElement.parentElement;
                    if (container) {
                        container.style.cssText = 'position:fixed!important;bottom:85px!important;left:80px!important;width:auto!important;z-index:1000!important;';
                    }
                }
            }
        }
        fixExtractBackButton();
        setTimeout(fixExtractBackButton, 100);
        setTimeout(fixExtractBackButton, 300);
        </script>
        """, height=0)
