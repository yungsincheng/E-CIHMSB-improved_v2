# extract.py → 提取模組（支援文字和圖片，含對象密鑰）

import numpy as np

from config import Q_LENGTH, TOTAL_AVERAGES_PER_UNIT, BLOCK_SIZE
from permutation import generate_Q_from_block, apply_Q_three_rounds
from image_processing import calculate_hierarchical_averages
from binary_operations import get_msbs
from mapping import map_from_z
from secret_encoding import binary_to_text, binary_to_image

def extract_secret(cover_image, z_bits, secret_type='text', contact_key=None):
    """
    功能:
        從 Z 碼和無載體圖片提取機密內容
    
    參數:
        cover_image: numpy array，灰階圖片 (H×W) 或彩色圖片 (H×W×3)
        z_bits: Z 碼位元列表
        secret_type: 'text' 或 'image'
        contact_key: 對象專屬密鑰（字串），用於解密
    
    返回:
        secret: 還原的機密內容（字串或 PIL Image）
        info: 額外資訊
    
    流程:
        1. 圖片預處理（彩色轉灰階、檢查尺寸）
        2. 計算 8×8 區塊數量
        3. 對每個 8×8 區塊進行提取（使用 contact_key 生成 Q）
        4. 跳過類型標記，將機密位元轉回原始內容
    """
    cover_image = np.array(cover_image)
    
    # ========== 步驟 1：圖片預處理 ==========
    # 1.1 若為彩色圖片，轉成灰階
    if len(cover_image.shape) == 3:
        cover_image = (
            0.299 * cover_image[:, :, 0] + 
            0.587 * cover_image[:, :, 1] + 
            0.114 * cover_image[:, :, 2]
        ).astype(np.uint8)
    
    height, width = cover_image.shape
    
    # 1.2 檢查圖片大小是否為 8 的倍數
    if height % 8 != 0 or width % 8 != 0:
        raise ValueError(f"圖片大小必須是 8 的倍數！當前大小: {width}×{height}")
    
    # ========== 步驟 2：計算 8×8 區塊數量 ==========
    num_rows = height // BLOCK_SIZE
    num_cols = width // BLOCK_SIZE
    
    # ========== 步驟 3：對每個 8×8 區塊進行提取 ==========
    secret_bits = []
    z_bit_index = 0
    finished = False
    
    for i in range(num_rows):
        if finished:
            break
        
        for j in range(num_cols):
            # 檢查是否所有 z_bits 已處理完
            if z_bit_index >= len(z_bits):
                finished = True
                break
            
            # 3.1 提取這個 8×8 區塊
            start_row = i * BLOCK_SIZE
            end_row = start_row + BLOCK_SIZE
            start_col = j * BLOCK_SIZE
            end_col = start_col + BLOCK_SIZE
            block = cover_image[start_row:end_row, start_col:end_col]
            
            # 3.2 生成這個區塊專屬的排列密鑰 Q（加入 contact_key）
            Q = generate_Q_from_block(block, Q_LENGTH, contact_key=contact_key)
            
            # 3.3 計算 21 個多層次平均值
            averages_21 = calculate_hierarchical_averages(block)
            
            # 3.4 用 Q 重新排列 21 個平均值
            reordered_averages = apply_Q_three_rounds(averages_21, Q)
            
            # 3.5 提取排列後的 21 個 MSB
            msbs = get_msbs(reordered_averages)
            
            # 3.6 反向映射還原機密位元
            for k in range(TOTAL_AVERAGES_PER_UNIT):
                if z_bit_index >= len(z_bits):
                    finished = True
                    break
                
                z_bit = z_bits[z_bit_index]
                msb = msbs[k]
                secret_bit = map_from_z(z_bit, msb)
                secret_bits.append(secret_bit)
                
                z_bit_index += 1
    
    # ========== 步驟 4：將機密位元轉回原始內容 ==========
    # 修正：跳過類型標記（第 1 bit）
    if len(secret_bits) < 1:
        raise ValueError("提取的位元數不足，無法讀取類型標記")
    
    type_marker = secret_bits[0]
    content_bits = secret_bits[1:]  # ← 跳過類型標記！
    
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
        secret, orig_size, is_color = binary_to_image(content_bits)
        info = {
            'type': 'image', 
            'size': orig_size, 
            'is_color': is_color,
            'type_marker': type_marker,
            'total_bits': len(secret_bits),
            'content_bits': len(content_bits)
        }
    
    return secret, info


def detect_and_extract(cover_image, z_bits, contact_key=None):
    """
    功能:
        自動偵測機密類型並提取
    
    參數:
        cover_image: 無載體圖片
        z_bits: Z 碼
        contact_key: 對象專屬密鑰（字串），用於解密
    
    返回:
        secret: 機密內容
        secret_type: 'text' 或 'image'
        info: 額外資訊
    
    原理:
        讀取第 1 bit 類型標記來決定解碼方式
        類型標記: 0 = 文字, 1 = 圖片
    """
    # 先提取所有 bits
    cover_image = np.array(cover_image)
    
    if len(cover_image.shape) == 3:
        cover_image = (
            0.299 * cover_image[:, :, 0] + 
            0.587 * cover_image[:, :, 1] + 
            0.114 * cover_image[:, :, 2]
        ).astype(np.uint8)
    
    height, width = cover_image.shape
    num_rows = height // BLOCK_SIZE
    num_cols = width // BLOCK_SIZE
    
    secret_bits = []
    z_bit_index = 0
    finished = False
    
    for i in range(num_rows):
        if finished:
            break
        for j in range(num_cols):
            if z_bit_index >= len(z_bits):
                finished = True
                break
            
            block = cover_image[i*BLOCK_SIZE:(i+1)*BLOCK_SIZE, j*BLOCK_SIZE:(j+1)*BLOCK_SIZE]
            # 使用 contact_key 生成 Q
            Q = generate_Q_from_block(block, Q_LENGTH, contact_key=contact_key)
            averages_21 = calculate_hierarchical_averages(block)
            reordered = apply_Q_three_rounds(averages_21, Q)
            msbs = get_msbs(reordered)
            
            for k in range(TOTAL_AVERAGES_PER_UNIT):
                if z_bit_index >= len(z_bits):
                    finished = True
                    break
                secret_bits.append(map_from_z(z_bits[z_bit_index], msbs[k]))
                z_bit_index += 1
    
    # 檢查是否有足夠的 bits
    if len(secret_bits) < 1:
        raise ValueError("Z 碼太短，無法提取類型標記")
    
    # ========== 讀取類型標記（第 1 bit）==========
    type_marker = secret_bits[0]
    content_bits = secret_bits[1:]  # 跳過類型標記
    
    if type_marker == 0:
        # 文字類型
        try:
            text = binary_to_text(content_bits)
            return text, 'text', {
                'type': 'text', 
                'length': len(text),
                'type_marker': type_marker,
                'total_bits': len(secret_bits),
                'content_bits': len(content_bits)
            }
        except Exception as e:
            raise ValueError(f"文字解碼失敗: {e}")
    else:
        # 圖片類型
        try:
            img, orig_size, is_color = binary_to_image(content_bits)
            if img is not None:
                return img, 'image', {
                    'type': 'image', 
                    'size': orig_size, 
                    'is_color': is_color,
                    'type_marker': type_marker,
                    'total_bits': len(secret_bits),
                    'content_bits': len(content_bits)
                }
            else:
                raise ValueError("圖片解碼返回 None")
        except Exception as e:
            raise ValueError(f"圖片解碼失敗: {e}")
