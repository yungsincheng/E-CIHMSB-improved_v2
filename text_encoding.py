# 建立 text_encoding.py → Z 碼文字編碼模組
# Z 碼與二進位字串互轉

def z_to_text(z_bits):
    """
    功能:
        將 Z 碼編碼成文字格式（二進位字串）
    
    參數:
        z_bits: Z 碼位元列表
    
    返回:
        z_text: 二進位字串
    
    範例:
        [1, 0, 1, 1] → "1011"
    """
    z_text = ''.join(str(bit) for bit in z_bits)
    return z_text

def text_to_z(z_text):
    """
    功能:
        從文字格式解碼 Z 碼
    
    參數:
        z_text: 二進位字串
    
    返回:
        z_bits: Z 碼位元列表
    
    範例:
        "1011" → [1, 0, 1, 1]
    """
    z_bits = [int(bit) for bit in z_text]
    return z_bits
