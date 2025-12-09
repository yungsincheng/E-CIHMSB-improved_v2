
# 建立 secret_encoding.py → 機密內容編碼模組
# 處理文字和圖片的二進位轉換

import numpy as np
import math
from PIL import Image

# 文字編碼
def text_to_binary(text):
    """
    功能:
        將文字轉成 UTF-8 二進位列表
    
    參數:
        text: 要編碼的文字字串
    
    返回:
        bits: 二進位列表
    """
    bits = []
    for byte in text.encode('utf-8'):
        for b in format(byte, '08b'):
            bits.append(int(b))
    return bits

def binary_to_text(binary):
    """
    功能:
        將二進位列表轉回文字
    
    參數:
        binary: 二進位列表
    
    返回:
        text: 解碼後的文字
    """
    byte_list = []
    for i in range(0, len(binary), 8):
        byte = binary[i:i+8]
        if len(byte) == 8:
            byte_value = int(''.join(map(str, byte)), 2)
            byte_list.append(byte_value)
    return bytes(byte_list).decode('utf-8', errors='ignore')

# 圖片編碼
def image_to_binary(image, capacity=None):
    """
    功能:
        將圖片轉成二進位列表（含 header）
    
    參數:
        image: PIL Image 物件
        capacity: 可用容量（bits），用於判斷是否需要縮放
    
    返回:
        binary: 二進位列表
        orig_size: 原始尺寸 (width, height)
        mode: 原始色彩模式
    
    Header 結構（66 bits）:
        - 原始寬度: 16 bits
        - 原始高度: 16 bits
        - is_color: 1 bit
        - has_alpha: 1 bit
        - 縮放後寬度: 16 bits
        - 縮放後高度: 16 bits
    """
    orig_size = image.size
    mode = image.mode
    
    # 判斷是否為彩色圖片
    is_color = mode not in ['L', '1', 'LA']
    
    # 判斷是否有透明通道
    if not is_color:
        has_alpha = False
    elif mode == 'P':
        temp_img = image.convert('RGBA')
        alpha_channel = temp_img.split()[-1]
        has_alpha = alpha_channel.getextrema()[0] < 255
    elif mode in ['RGBA', 'PA']:
        has_alpha = True
    else:
        has_alpha = False
    
    # 轉換色彩模式
    if not is_color:
        image = image.convert('L')
        has_alpha = False
    elif mode == 'P':
        image = image.convert('RGBA' if has_alpha else 'RGB')
    elif mode not in ['RGB', 'RGBA']:
        image = image.convert('RGB')
        has_alpha = False
    
    # 建立 header（前 34 bits：原始尺寸 + 模式）
    binary = []
    for b in format(orig_size[0], '016b'):
        binary.append(int(b))
    for b in format(orig_size[1], '016b'):
        binary.append(int(b))
    binary.append(1 if is_color else 0)
    binary.append(1 if has_alpha else 0)
    
    # 計算每像素 bits
    if is_color:
        bpp = 32 if has_alpha else 24
    else:
        bpp = 8
    
    header_bits = 66  # 固定 66 bits
    capacity = capacity or 86016  # 預設 512×512 圖片的容量
    
    # 計算是否需要縮放
    max_pixels = (capacity - header_bits) // bpp
    current_pixels = orig_size[0] * orig_size[1]
    
    if current_pixels <= max_pixels:
        new_size = orig_size
    else:
        ratio = math.sqrt(max_pixels / current_pixels)
        new_w = max(8, (int(orig_size[0] * ratio) // 8) * 8)
        new_h = max(8, (int(orig_size[1] * ratio) // 8) * 8)
        new_size = (new_w, new_h)
    
    # 縮放圖片
    image = image.resize(new_size, Image.Resampling.LANCZOS)
    
    # 加入縮放後尺寸（32 bits）
    for b in format(new_size[0], '016b'):
        binary.append(int(b))
    for b in format(new_size[1], '016b'):
        binary.append(int(b))
    
    # 加入像素資料
    if is_color:
        for px in list(image.getdata()):
            channels = 4 if has_alpha else 3
            for v in px[:channels]:
                for b in format(v, '08b'):
                    binary.append(int(b))
    else:
        for px in list(image.getdata()):
            for b in format(px, '08b'):
                binary.append(int(b))
    
    return binary, orig_size, mode

def binary_to_image(binary):
    """
    功能:
        將二進位列表轉回圖片
    
    參數:
        binary: 二進位列表
    
    返回:
        image: PIL Image 物件（還原到原始尺寸）
        orig_size: 原始尺寸 (width, height)
        is_color: 是否為彩色
    """
    try:
        # 解析 header
        w = int(''.join(map(str, binary[0:16])), 2)
        h = int(''.join(map(str, binary[16:32])), 2)
        is_color = binary[32]
        has_alpha = binary[33]
        idx = 34
        
        # 解析縮放後尺寸
        sw = int(''.join(map(str, binary[idx:idx+16])), 2)
        sh = int(''.join(map(str, binary[idx+16:idx+32])), 2)
        idx += 32
        
        if is_color:
            # 彩色圖片
            pixels = []
            for _ in range(sw * sh):
                if has_alpha and idx + 32 <= len(binary):
                    pixel = tuple(
                        int(''.join(map(str, binary[idx+i*8:idx+(i+1)*8])), 2)
                        for i in range(4)
                    )
                    pixels.append(pixel)
                    idx += 32
                elif idx + 24 <= len(binary):
                    pixel = tuple(
                        int(''.join(map(str, binary[idx+i*8:idx+(i+1)*8])), 2)
                        for i in range(3)
                    )
                    pixels.append(pixel)
                    idx += 24
            
            img = Image.new('RGBA' if has_alpha else 'RGB', (sw, sh))
            img.putdata(pixels[:sw*sh])
        else:
            # 灰階圖片
            pixels = []
            for i in range(sw * sh):
                if idx + (i+1) * 8 <= len(binary):
                    pixel = int(''.join(map(str, binary[idx+i*8:idx+(i+1)*8])), 2)
                    pixels.append(pixel)
            
            img = Image.new('L', (sw, sh))
            img.putdata(pixels[:sw*sh])
        
        # 還原到原始尺寸
        img = img.resize((w, h), Image.Resampling.LANCZOS)
        
        return img, (w, h), is_color
    
    except Exception as e:
        return None, None, None

def encode_secret(secret, secret_type='text', capacity=None):
    """
    功能:
        將機密內容（文字或圖片）編碼成二進位
    
    參數:
        secret: 機密內容（字串或 PIL Image）
        secret_type: 'text' 或 'image'
        capacity: 可用容量（僅圖片需要）
    
    返回:
        binary: 二進位列表
        info: 額外資訊（文字長度或圖片尺寸）
    """
    if secret_type == 'text':
        binary = text_to_binary(secret)
        info = {'type': 'text', 'length': len(secret)}
    else:
        binary, orig_size, mode = image_to_binary(secret, capacity)
        info = {'type': 'image', 'size': orig_size, 'mode': mode}
    
    return binary, info

# 通用編碼
def decode_secret(binary, secret_type='text'):
    """
    功能:
        將二進位解碼成機密內容
    
    參數:
        binary: 二進位列表
        secret_type: 'text' 或 'image'
    
    返回:
        secret: 解碼後的內容
        info: 額外資訊
    """
    if secret_type == 'text':
        text = binary_to_text(binary)
        return text, {'type': 'text', 'length': len(text)}
    else:
        img, orig_size, is_color = binary_to_image(binary)
        return img, {'type': 'image', 'size': orig_size, 'is_color': is_color}

def calculate_required_bits(secret, secret_type='text', capacity=None):
    """
    功能:
        計算機密內容所需的 bits 數量
    
    參數:
        secret: 機密內容
        secret_type: 'text' 或 'image'
        capacity: 可用容量（僅圖片需要）
    
    返回:
        bits: 所需 bits 數量
    """
    if secret_type == 'text':
        return len(secret.encode('utf-8')) * 8
    else:
        binary, _, _ = image_to_binary(secret, capacity)
        return len(binary)
