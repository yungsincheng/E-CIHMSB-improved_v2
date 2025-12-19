# 建立 extract.py → 提取模組
# 從載體圖像和 Z 碼提取機密內容

import numpy as np
import hashlib
from PIL import Image

from config import Q_LENGTH, TOTAL_AVERAGES_PER_UNIT, BLOCK_SIZE
from permutation import generate_Q_from_block, apply_Q_three_rounds
from image_processing import calculate_hierarchical_averages
from binary_operations import get_msbs
from mapping import map_from_z
from secret_encoding import text_to_binary, binary_to_text, image_to_binary, binary_to_image, xor_cipher

# 提取
def extract_secret(cover_image, z_bits, secret_type='text', contact_key=None):
    """
    功能:
        從 Z 碼和載體圖像提取機密內容
    
    參數:
        cover_image: numpy array，灰階圖像 (H×W) 或彩色圖像 (H×W×3)
        z_bits: Z 碼位元列表
        secret_type: 'text' 或 'image'
        contact_key: 對象專屬密鑰（字串），用於解密
    
    返回:
        secret: 機密內容（字串或 PIL Image）
        info: 額外資訊（機密內容的相關資訊）
    
    流程:
        1. 圖像預處理（彩色轉灰階、檢查尺寸）
        2. 計算 8×8 區塊數量
        3. 對每個 8×8 區塊進行提取（使用 contact_key 生成 Q）
        4. XOR 解密（使用 contact_key）
        5. 將機密位元轉回原始內容

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
    
    # 步驟 2：計算 8×8 區塊數量
    num_rows = height // BLOCK_SIZE  # 垂直方向有幾個 8×8 區塊
    num_cols = width // BLOCK_SIZE   # 水平方向有幾個 8×8 區塊
    
    # 步驟 3：對每個 8×8 區塊進行提取
    # 流程和 embed.py 相反：從 Z 碼還原加密後的位元
    encrypted_bits = []
    z_bit_index = 0
    finished = False
    
    for i in range(num_rows):      # i = 第幾列區塊
        if finished:
            break
        
        for j in range(num_cols):  # j = 第幾行區塊
            if z_bit_index >= len(z_bits):
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
            
            # 提取排列後的 21 個 MSB（最高有效位元）
            # 例如 156 = 10011100，MSB = 1
            msbs = get_msbs(reordered_averages)
            
            # 反向映射還原加密後的位元
            # 對這個區塊的 21 個位置，逐一還原 M
            for k in range(TOTAL_AVERAGES_PER_UNIT):  # k = 0~20
                if z_bit_index >= len(z_bits):
                    finished = True
                    break
                
                z_bit = z_bits[z_bit_index]             # Z 碼的 bit
                msb = msbs[k]                           # 對應的 MSB
                encrypted_bit = map_from_z(z_bit, msb)  # (Z, MSB) → M
                encrypted_bits.append(encrypted_bit)
                z_bit_index += 1
    
    # 步驟 4：XOR 解密
    # type_marker 不需要解密
    # 如果是圖像，header (34 bits) 也不需要解密，只解密像素資料
    IMAGE_HEADER_SIZE = 34  # 圖像 header 固定 34 bits
    
    if len(encrypted_bits) < 1:
        raise ValueError("提取的位元數不足，無法讀取類型標記")
    
    type_marker = encrypted_bits[0]           # type_marker 沒有被加密
    encrypted_content = encrypted_bits[1:]    # type_marker 之後的所有位元
    
    if type_marker == 1 and len(encrypted_content) > IMAGE_HEADER_SIZE:
        # 圖像解密結構：
        # [type_marker 1 bit] + [header 34 bits] + XOR([像素資料])
        #      不解密              不解密              解密
        image_header = encrypted_content[:IMAGE_HEADER_SIZE]
        encrypted_pixels = encrypted_content[IMAGE_HEADER_SIZE:]
        decrypted_pixels = xor_cipher(encrypted_pixels, contact_key)
        content_bits = image_header + decrypted_pixels
    else:
        # 文字解密結構：
        # [type_marker 1 bit] + XOR([content_bits])
        #      不解密                  解密
        content_bits = xor_cipher(encrypted_content, contact_key)
    
    secret_bits = [type_marker] + content_bits  # 重組完整位元（用於計算 total_bits）

     # 步驟 5：將機密位元轉回原始內容
    if secret_type == 'text':
        secret = binary_to_text(content_bits)
        info = {
            'type': 'text', 
            'length': len(secret),
            'type_marker': type_marker,
            'total_bits': len(secret_bits),
            'content_bits': len(content_bits)
        }
    else:
        try:
            secret, size, is_color = binary_to_image(content_bits)
            info = {
                'type': 'image', 
                'size': size, 
                'is_color': is_color,
                'type_marker': type_marker,
                'total_bits': len(secret_bits),
                'content_bits': len(content_bits)
            }
        except Exception as e:
            # 解碼失敗（Z 碼損壞或載體圖像完全不對）→ 生成 64×64 亂碼圖像
            # 註：選錯對象不會進入這裡，只是圖像內容變亂碼（尺寸正確）
            noise_size = 64
            noise_data = bytes([content_bits[i % len(content_bits)] * 255 if i < len(content_bits) else 128 
                               for i in range(noise_size * noise_size)])
            secret = Image.frombytes('L', (noise_size, noise_size), noise_data)
            info = {
                'type': 'image',
                'size': (noise_size, noise_size),
                'is_color': False,
                'type_marker': type_marker,
                'total_bits': len(secret_bits),
                'content_bits': len(content_bits),
                'error': f'解碼失敗（Z 碼損壞或載體圖像不對）: {str(e)[:50]}'
            }
    
    return secret, info

# 自動偵測類型並提取（重用 extract_secret）
def detect_and_extract(cover_image, z_bits, contact_key=None):
    """
    功能:
        自動偵測機密類型並提取
    
    參數:
        cover_image: 載體圖像
        z_bits: Z 碼位元列表
        contact_key: 對象專屬密鑰（字串），用於解密
    
    返回:
        secret: 機密內容
        secret_type: 'text' 或 'image'
        info: 額外資訊（機密內容的相關資訊）
    
    原理:
        1. 從第一個區塊提取 type_marker（第 1 個 bit）
           類型標記: 0 = 文字, 1 = 圖像
        2. 根據 type_marker 呼叫 extract_secret
    """
    cover_image = np.array(cover_image)
    
    # 圖像預處理（轉灰階）
    if len(cover_image.shape) == 3:
        cover_image = (
            0.299 * cover_image[:, :, 0] + 
            0.587 * cover_image[:, :, 1] + 
            0.114 * cover_image[:, :, 2]
        ).astype(np.uint8)
    
    # 從第一個區塊提取 type_marker
    block = cover_image[0:BLOCK_SIZE, 0:BLOCK_SIZE]                      # 取第一個 8×8 區塊
    Q = generate_Q_from_block(block, Q_LENGTH, contact_key=contact_key)
    averages_21 = calculate_hierarchical_averages(block)
    reordered = apply_Q_three_rounds(averages_21, Q)
    msbs = get_msbs(reordered)
    type_marker = map_from_z(z_bits[0], msbs[0])                         # 用 (Z, MSB) 還原第 1 個 bit
    
    # 根據類型呼叫 extract_secret
    if type_marker == 0:
        secret, info = extract_secret(cover_image, z_bits, secret_type='text', contact_key=contact_key)
        return secret, 'text', info
    else:
        secret, info = extract_secret(cover_image, z_bits, secret_type='image', contact_key=contact_key)
        return secret, 'image', info
