# 建立 secret_encoding.py → 機密內容編碼模組
# 處理文字和圖像的二進位轉換

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
    
    for byte in text.encode('utf-8'):  # 把文字轉成 bytes，例如 "H" → 72
        for b in format(byte, '08b'):  # 把數字轉成 8 位元二進位字串，例如 72 → "01001000"
            bits.append(int(b))  # 把字元 '0' 或 '1' 轉成數字 0 或 1
    
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
    
    for i in range(0, len(binary), 8):  # 每 8 個 bits 為一組
        byte = binary[i:i+8]  # 取出這一組的 8 個 bits
        if len(byte) == 8:
            byte_value = int(''.join(map(str, byte)), 2)  # 二進位列表 → 十進位數字，例如 [0,1,0,0,1,0,0,0] → 72
            byte_list.append(byte_value)  # 收集起來
    
    return bytes(byte_list).decode('utf-8', errors='ignore')  # bytes 轉回文字，例如 [72] → "H"

# 圖像編碼
def image_to_binary(image):
    """
    功能:
        將機密圖像轉成二進位列表（含 header）
    
    參數:
        image: PIL Image 物件
    
    返回:
        binary: 二進位列表
        size: 機密圖像尺寸 (width, height)
        mode: 機密圖像色彩模式
    
    Header 結構（34 bits）:
        - 機密圖像寬度: 16 bits
        - 機密圖像高度: 16 bits
        - is_color: 1 bit
        - has_alpha: 1 bit
    """
    orig_size = image.size  # 取得圖像尺寸，例如 (64, 64)
    mode = image.mode  # 取得色彩模式，例如 'RGB', 'L', 'RGBA'
    
    # 判斷是否為彩色圖像
    is_color = mode not in ['L', '1', 'LA']  # 'L' = 灰階(0~255), '1' = 純黑白(只有0和1), 'LA' = 灰階+透明
    
    # 判斷是否有透明通道
    if not is_color:  # 灰階圖沒有透明
        has_alpha = False                                  
    elif mode == 'P':  # 調色盤模式（PNG 常用）
        temp_img = image.convert('RGBA')  # 先轉成 RGBA
        alpha_channel = temp_img.split()[-1]  # 取出第 4 個通道（透明度）
        has_alpha = alpha_channel.getextrema()[0] < 255  # getextrema() 回傳 (最小值, 最大值)，如果最小值 < 255，表示有些像素是透明的
    elif mode in ['RGBA', 'PA']:  # 模式名稱有 'A' 就是有透明通道
        has_alpha = True
    else:  # RGB 等其他模式沒有透明
        has_alpha = False                                  
    
    # 統一色彩模式
    if not is_color:
        image = image.convert('L')  # 黑白 '1' 或灰階+透明 'LA' → 統一轉灰階 'L'
        has_alpha = False  # 不保留透明
    elif mode == 'P':  # 調色盤模式
        image = image.convert('RGBA' if has_alpha else 'RGB')  # 有透明 → 轉 RGBA，沒透明 → 轉 RGB
    elif mode not in ['RGB', 'RGBA']:  # 其他奇怪的模式（如 'CMYK'）
        image = image.convert('RGB')  # 統一轉 RGB
        has_alpha = False  # 不保留透明
    
    # 建立 header（ 34 bits：原始尺寸 + 模式）
    binary = []
    
    for b in format(orig_size[0], '016b'):  # 機密圖像寬度 → 16 bits
        binary.append(int(b))
    for b in format(orig_size[1], '016b'):  # 機密圖像高度 → 16 bits
        binary.append(int(b))
        
    binary.append(1 if is_color else 0)  # 是否彩色 → 1 bit
    binary.append(1 if has_alpha else 0)   # 是否透明 → 1 bit
    
    # 加入像素資料
    if is_color:
        for px in list(image.getdata()):  # 取得所有像素，例如 (255, 128, 64)
            channels = 4 if has_alpha else 3  # RGBA=4 個通道, RGB=3 個通道
            for v in px[:channels]:  # 每個通道的值 (0~255)
                for b in format(v, '08b'):  # 轉成 8 bits
                    binary.append(int(b))
    else:
        for px in list(image.getdata()):  # 灰階像素，例如 128
            for b in format(px, '08b'):  # 轉成 8 bits
                binary.append(int(b))
    
    return binary, orig_size, mode

def binary_to_image(binary):
    """
    功能:
        將二進位列表轉回機密圖像
    
    參數:
        binary: 二進位列表
    
    返回:
        image: PIL Image 物件
        orig_size: 機密圖像尺寸 (width, height)
        is_color: 是否為彩色

    Header 結構（34 bits）:
        - 機密圖像寬度: 16 bits
        - 機密圖像高度: 16 bits
        - is_color: 1 bit
        - has_alpha: 1 bit
    """
    try:
        # 解析 Header（34 bits）
        w = int(''.join(map(str, binary[0:16])), 2)  # 機密圖像寬度
        h = int(''.join(map(str, binary[16:32])), 2)  # 機密圖像高度
        is_color = binary[32]  # 是否彩色
        has_alpha = binary[33]  # 是否透明
        idx = 34  # 從第 34 bit 開始讀像素
        
        # 讀取像素資料
        if is_color:
            pixels = []
            
            for _ in range(w * h):   # 讀 w×h 個像素
                if has_alpha and idx + 32 <= len(binary):  # RGBA: 每像素 32 bits
                    pixel = tuple(
                        int(''.join(map(str, binary[idx+i*8:idx+(i+1)*8])), 2)
                        for i in range(4)  # 讀 4 個通道 (R, G, B, A)
                    )
                    pixels.append(pixel)  # 收集像素
                    idx += 32   # 移動到下一個像素
                elif idx + 24 <= len(binary):   # RGB: 每像素 24 bits
                    pixel = tuple(
                        int(''.join(map(str, binary[idx+i*8:idx+(i+1)*8])), 2)
                        for i in range(3)  # 讀 3 個通道 (R, G, B)
                    )
                    pixels.append(pixel)  # 收集像素
                    idx += 24  # 移動到下一個像素
            
            img = Image.new('RGBA' if has_alpha else 'RGB', (w, h))  # 建立空白圖像
            img.putdata(pixels[:w*h])  # 把像素放進圖像
        
        else:
            pixels = []
            
            for i in range(w * h):  # 灰階: 每像素 8 bits
                if idx + (i+1) * 8 <= len(binary):
                    pixel = int(''.join(map(str, binary[idx+i*8:idx+(i+1)*8])), 2)  # 讀 8 bits 轉成數字
                    pixels.append(pixel)  # 收集像素
            
            img = Image.new('L', (w, h))  # 建立灰階圖像
            img.putdata(pixels[:w*h])  # 把像素放進圖像
        
        return img, (w, h), is_color
    
    except Exception as e:
        return None, None, None  # 解碼失敗回傳 None
