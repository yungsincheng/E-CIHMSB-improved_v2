# 建立 image_encoding.py → Z 碼圖像編碼模組
# Z 碼與灰階圖像互轉

import numpy as np
import math
from PIL import Image

from binary_operations import int_to_binary, binary_to_int

# ==================== 基礎版（供 main.py 使用）====================
def z_to_image(z_bits):
    """
    功能:
        將 Z 碼位元列表編碼成灰階圖像
    
    參數:
        z_bits: Z 碼位元列表
    
    返回:
        image: PIL Image（灰階）
    
    原理:
        每 8 bits 轉成 1 個像素值（0~255）
    
    範例:
        [0,1,0,0,1,0,0,0, 0,1,1,0,1,0,0,1] → 2 個像素 (72, 105)
    """
    num_bits = len(z_bits)
    num_pixels = math.ceil(num_bits / 8)
    
    # 補齊到 8 的倍數
    if num_bits % 8 != 0:
        padding = 8 - (num_bits % 8)
        z_bits = z_bits + [0] * padding
    
    # 每 8 bits 轉成 1 個像素值
    pixels = []
    for i in range(0, len(z_bits), 8):
        byte = z_bits[i:i+8]
        pixel_value = binary_to_int(byte)
        pixels.append(pixel_value)
    
    # 計算圖像尺寸（盡量接近正方形）
    width = int(math.sqrt(num_pixels))
    height = math.ceil(num_pixels / width)
    
    # 補齊像素數量
    while len(pixels) < width * height:
        pixels.append(0)
    
    # 建立灰階圖像
    pixel_array = np.array(pixels, dtype=np.uint8)
    pixel_array = pixel_array[:width * height].reshape(height, width)
    image = Image.fromarray(pixel_array, mode='L')
    
    return image

def image_to_z(image, original_bit_length=None):
    """
    功能:
        從灰階圖像解碼 Z 碼位元列表
    
    參數:
        image: PIL Image（灰階）
        original_bit_length: 原始位元長度（用於去除補齊的 0）
    
    返回:
        z_bits: Z 碼位元列表
    
    原理:
        每個像素值（0~255）轉成 8 bits
    
    範例:
        2 個像素 (72, 105) → [0,1,0,0,1,0,0,0, 0,1,1,0,1,0,0,1]
    """
    # 圖像轉成像素陣列
    pixel_array = np.array(image)
    pixels = pixel_array.flatten()
    
    # 每個像素轉成 8 bits
    z_bits = []
    for pixel in pixels:
        binary = int_to_binary(pixel, 8)
        z_bits.extend(binary)
    
    # 去除補齊的 0
    if original_bit_length is not None:
        z_bits = z_bits[:original_bit_length]
    
    return z_bits
  
# ==================== 含 Header 版（供 interface.py 使用）====================
def z_to_image_with_header(z_bits, style_num, img_num, img_size):
    """
    功能:
        將 Z 碼編碼成灰階圖像（含 header 資訊）
    
    參數:
        z_bits: Z 碼位元列表
        style_num: 風格編號（1~5）
        img_num: 圖像編號（1~7）
        img_size: 圖像尺寸（64, 128, 256...）
    
    返回:
        image: PIL Image（灰階）
        length: Z 碼長度
    
    Header 結構（共 72 bits）:
        [32 bits Z碼長度] + [8 bits 風格編號] + [16 bits 圖像編號] + [16 bits 尺寸]
    
    完整結構:
        [Header 72 bits] + [Z碼] + [補齊]
    """
    length = len(z_bits)
    
    # 建立 header（72 bits）
    header_bits = []
    header_bits += int_to_binary(length, 32)    # Z碼長度: 32 bits
    header_bits += int_to_binary(style_num, 8)  # 風格編號: 8 bits
    header_bits += int_to_binary(img_num, 16)   # 圖像編號: 16 bits
    header_bits += int_to_binary(img_size, 16)  # 圖像尺寸: 16 bits
    
    # 合併 header 和 Z碼
    full_bits = header_bits + z_bits
    
    # 補齊到 8 的倍數
    if len(full_bits) % 8 != 0:
        padding = 8 - (len(full_bits) % 8)
        full_bits = full_bits + [0] * padding
    
    # 每 8 bits 轉成 1 個像素值
    pixels = []
    for i in range(0, len(full_bits), 8):
        byte = full_bits[i:i+8]
        pixel_value = binary_to_int(byte)
        pixels.append(pixel_value)
    
    # 計算圖像尺寸（盡量接近正方形）
    num_pixels = len(pixels)
    width = int(math.sqrt(num_pixels))
    height = math.ceil(num_pixels / width)
    
    # 補齊像素數量
    while len(pixels) < width * height:
        pixels.append(0)
    
    # 建立灰階圖像
    image = Image.new('L', (width, height))
    image.putdata(pixels[:width * height])
    
    return image, length

def image_to_z_with_header(image):
    """
    功能:
        從灰階圖像解碼 Z 碼（含 header 資訊）
    
    參數:
        image: PIL Image（灰階或彩色，會自動轉灰階）
    
    返回:
        z_bits: Z 碼位元列表
        style_num: 風格編號
        img_num: 圖像編號
        img_size: 圖像尺寸
    
    Header 結構（共 72 bits）:
        [32 bits Z碼長度] + [8 bits 風格編號] + [16 bits 圖像編號] + [16 bits 尺寸]
    """
    # 確保是灰階圖像
    if image.mode != 'L':
        image = image.convert('L')
    
    # 圖像轉成像素列表
    pixels = list(image.getdata())
    
    # 每個像素轉成 8 bits
    all_bits = []
    for pixel in pixels:
        bits = int_to_binary(pixel, 8)
        all_bits.extend(bits)
    
    # 檢查長度（至少需要 72 bits 的 header）
    if len(all_bits) < 72:
        raise ValueError("Z碼圖格式錯誤：太小")
    
    # 解析 header
    z_length = binary_to_int(all_bits[:32])     # Z碼長度
    style_num = binary_to_int(all_bits[32:40])  # 風格編號
    img_num = binary_to_int(all_bits[40:56])    # 圖像編號
    img_size = binary_to_int(all_bits[56:72])   # 圖像尺寸
    
    # 檢查 Z碼長度是否合理
    if z_length <= 0 or z_length > len(all_bits) - 72:
        raise ValueError(f"無效的 Z碼（長度：{z_length}）")
    
    # 提取 Z碼
    z_bits = all_bits[72:72 + z_length]
    
    return z_bits, style_num, img_num, img_size
