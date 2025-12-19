# 建立 embed.py → 嵌入模組
# 將機密內容嵌入載體圖像，產生 Z 碼

import numpy as np
import hashlib

from config import Q_LENGTH, TOTAL_AVERAGES_PER_UNIT, BLOCK_SIZE
from permutation import generate_Q_from_block, apply_Q_three_rounds
from image_processing import calculate_hierarchical_averages
from binary_operations import get_msbs
from mapping import map_to_z
from secret_encoding import text_to_binary, image_to_binary

# 載體容量計算
def calculate_capacity(image_width, image_height):
    """
    功能:
        計算載體圖像的嵌入容量（可藏多少 bits）
    
    參數:
        image_width: 載體圖像寬度
        image_height: 載體圖像高度
    
    返回:
        capacity: 可嵌入的 bits 數量
    
    公式:
        EC = (W×H) ÷ (8×8) × 21
    """
    num_units = (image_width // BLOCK_SIZE) * (image_height // BLOCK_SIZE)
    capacity = num_units * TOTAL_AVERAGES_PER_UNIT
    
    return capacity
    
# XOR 加密
def xor_encrypt(secret_bits, key):
    """
    功能:
        用 key 對 secret_bits 進行 XOR 加密
    
    參數:
        secret_bits: 要加密的機密位元列表
        key: 密鑰字串
    
    返回:
        encrypted_bits: 加密後的位元列表

    原理:
        XOR 運算：相同為 0，不同為 1
        0 ^ 0 = 0
        0 ^ 1 = 1
        1 ^ 0 = 1
        1 ^ 1 = 0
        
        特性：加密和解密用同一個函式
        原文 XOR 密鑰 = 密文
    """
    if not key:  # 沒有 key 就不加密
        return secret_bits  
    
    # 用 key 生成足夠長的密鑰流
    # SHA-256 每次產生 32 bytes (256 bits)，不夠就重複 hash
    key_bits = []
    key_hash = hashlib.sha256(key.encode()).digest()                # 把 key 轉成 32 bytes 的 hash，例如 "Alice" → 32 bytes
    
    while len(key_bits) < len(secret_bits):
        for byte in key_hash:                                       # 每個 byte (0~255)
            key_bits.extend([int(b) for b in format(byte, '08b')])  # 轉成 8 bits，例如 72 → [0,1,0,0,1,0,0,0]
            if len(key_bits) >= len(secret_bits):
                break
        key_hash = hashlib.sha256(key_hash).digest()                # 不夠就再 hash 一次，產生更多 bits
    
    # XOR 加密
    # 例如: secret_bits = [1,0,1], key_bits = [0,1,1]
    #       結果 = [1^0, 0^1, 1^1] = [1, 1, 0]
    encrypted_bits = [secret_bits[i] ^ key_bits[i] for i in range(len(secret_bits))]
    return encrypted_bits

# 嵌入
def embed_secret(cover_image, secret, secret_type='text', contact_key=None):
    """
    功能:
        將機密內容嵌入載體圖像，產生 Z 碼
    
    參數:
        cover_image: numpy array，灰階圖像 (H×W) 或彩色圖像 (H×W×3)
        secret: 機密內容（字串或 PIL Image）
        secret_type: 'text' 或 'image'
        contact_key: 對象專屬密鑰（字串），用於加密
    
    返回:
        z_bits: Z 碼位元列表
        capacity: 載體圖像的總容量（bits）
        info: 額外資訊（機密內容的相關資訊）
    
    流程:
        1. 圖像預處理（彩色轉灰階、檢查尺寸）
        2. 計算容量並檢查
        3. XOR 加密（使用 contact_key）
        4. 對每個 8×8 區塊進行嵌入（使用 contact_key 生成 Q）
    
    格式:
        [1 bit 類型標記] + [機密內容]
        類型標記: 0 = 文字, 1 = 圖像
    """
    cover_image = np.array(cover_image)
    
    # 步驟 1：圖像預處理
    # 若為彩色圖像，轉成灰階（使用標準權重）
    # len(shape) == 3 表示有 3 個維度（高, 寬, 通道），即彩色圖像
    if len(cover_image.shape) == 3:
        cover_image = (
            0.299 * cover_image[:, :, 0] +  # R × 0.299
            0.587 * cover_image[:, :, 1] +  # G × 0.587
            0.114 * cover_image[:, :, 2]    # B × 0.114
        ).astype(np.uint8)                  # 轉成整數 (0~255)
    
    height, width = cover_image.shape       # 取得圖像尺寸（高, 寬）
    
    # 檢查圖像大小是否為 8 的倍數（系統以 8×8 區塊處理）
    if height % 8 != 0 or width % 8 != 0:
        raise ValueError(f"圖像大小必須是 8 的倍數！當前大小: {width}×{height}")
    
    # 步驟 2：計算容量並檢查
    # 例如 512×512 的圖像：
    # num_rows = 512 ÷ 8 = 64
    # num_cols = 512 ÷ 8 = 64
    # num_units = 64 × 64 = 4096 個區塊
    # capacity = 4096 × 21 = 86,016 bits
    num_rows = height // BLOCK_SIZE                 # 垂直方向有幾個 8×8 區塊
    num_cols = width // BLOCK_SIZE                  # 水平方向有幾個 8×8 區塊
    num_units = num_rows * num_cols                 # 總共幾個區塊
    capacity = num_units * TOTAL_AVERAGES_PER_UNIT  # 每區塊 21 bits
    
    # 將機密內容轉成二進位（加入類型標記）
    if secret_type == 'text':
        type_marker = [0]                      # 0 = 文字
        content_bits = text_to_binary(secret)  # "Hi" → [0,1,0,0,1,0,0,0,...]
        info = {'type': 'text', 'length': len(secret), 'bits': len(content_bits) + 1}
    else:
        type_marker = [1]                                   # 1 = 圖像
        content_bits, size, mode = image_to_binary(secret)  # PIL Image → 二進位
        info = {'type': 'image', 'size': size, 'mode': mode, 'bits': len(content_bits) + 1}
    
    # 組合完整的 secret_bits
    # 例如文字 "H": [0] + [0,1,0,0,1,0,0,0] = [0,0,1,0,0,1,0,0,0]
    #              類型   內容
    secret_bits = type_marker + content_bits
    
    # 檢查容量是否足夠
    if len(secret_bits) > capacity:
        raise ValueError(
            f"機密內容太大！需要 {len(secret_bits)} bits，但容量只有 {capacity} bits"
        )
    
    # 步驟 3：XOR 加密
    # type_marker 不加密（確保類型判斷正確）
    # 圖像的 header (34 bits) 也不加密（確保尺寸正確）
    IMAGE_HEADER_SIZE = 34
    
    if secret_type == 'image' and len(content_bits) > IMAGE_HEADER_SIZE:
        # 圖像加密結構：
        # [type_marker 1 bit] + [header 34 bits] + XOR([像素資料])
        #      不加密              不加密              加密
        image_header = content_bits[:IMAGE_HEADER_SIZE]   # 寬、高、色彩模式
        pixel_data = content_bits[IMAGE_HEADER_SIZE:]     # 像素資料
        encrypted_pixels = xor_encrypt(pixel_data, contact_key)
        encrypted_bits = type_marker + image_header + encrypted_pixels
    else:
        # 文字加密結構：
        # [type_marker 1 bit] + XOR([content_bits])
        #      不加密                  加密
        encrypted_content = xor_encrypt(content_bits, contact_key)
        encrypted_bits = type_marker + encrypted_content
    
    # 步驟 4：對每個 8×8 區塊進行嵌入
    # 遍歷每個區塊，產生 Z 碼
    # 載體圖像分割示意（以 16×16 為例）：
    # ┌────┬────┐
    # │ 0,0│ 0,1│  每格是 8×8 區塊
    # ├────┼────┤
    # │ 1,0│ 1,1│
    # └────┴────┘
    z_bits = []
    secret_bit_index = 0
    finished = False
    
    for i in range(num_rows):      # i = 第幾列區塊
        if finished:
            break
        
        for j in range(num_cols):  # j = 第幾行區塊
            if secret_bit_index >= len(encrypted_bits):
                finished = True
                break
            
            # 提取這個 8×8 區塊
            # 例如 i=1, j=2 時：
            # start_row = 1 × 8 = 8
            # end_row = 8 + 8 = 16
            # start_col = 2 × 8 = 16
            # end_col = 16 + 8 = 24
            # block = cover_image[8:16, 16:24]
            start_row = i * BLOCK_SIZE
            end_row = start_row + BLOCK_SIZE
            start_col = j * BLOCK_SIZE
            end_col = start_col + BLOCK_SIZE
            block = cover_image[start_row:end_row, start_col:end_col]
            
            # 生成這個區塊專屬的排列密鑰 Q
            # 每個區塊的 Q 都不同（基於區塊內容 + contact_key）
            Q = generate_Q_from_block(block, Q_LENGTH, contact_key=contact_key)
            
            # 計算 21 個多層次平均值
            # 第一層: 16 個 (2×2 區塊)
            # 第二層: 4 個 (4×4 區塊)
            # 第三層: 1 個 (8×8 整塊)
            averages_21 = calculate_hierarchical_averages(block)
            
            # 用 Q 重新排列 21 個平均值（分 3 輪，每輪 7 個）
            reordered_averages = apply_Q_three_rounds(averages_21, Q)
            
            # 提取排列後的 21 個 MSB (最高有效位元）
            # 例如 156 = 10011100，MSB = 1
            msbs = get_msbs(reordered_averages)
            
            # 映射產生 Z 碼
            # 對這個區塊的 21 個位置，逐一產生 Z
            for k in range(TOTAL_AVERAGES_PER_UNIT):  # k = 0~20
                if secret_bit_index >= len(encrypted_bits):
                    finished = True
                    break
                
                secret_bit = encrypted_bits[secret_bit_index]  # 要嵌入的 bit
                msb = msbs[k]                                  # 對應的 MSB
                z_bit = map_to_z(secret_bit, msb)              # (M, MSB) → Z
                z_bits.append(z_bit)
                secret_bit_index += 1
    
    return z_bits, capacity, info
