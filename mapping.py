# 建立 mapping.py → 映射模組
# MSB 映射表與映射函式

# ==================== MSB 映射表 ====================
# 正向映射表（論文的表 1）：(M, MSB) → Z
MAPPING_TABLE = {
    (0, 0): 1,
    (0, 1): 0,
    (1, 0): 0,
    (1, 1): 1
}

# 反向映射表：(Z, MSB) → M
REVERSE_MAPPING_TABLE = {
    (1, 0): 0,
    (0, 0): 1,
    (1, 1): 1,
    (0, 1): 0
}

# ==================== 映射函式 ====================
def map_to_z(secret_bit, msb):
    """
    功能:
        正向映射：將秘密位元 M 與 MSB 結合，轉換為 Z 碼
    
    參數:
        secret_bit: 秘密位元
        msb: 對應平均值的 MSB
    
    返回:
        z_bit: 映射後的 Z 碼位元
    
    映射表:
        (M=0, MSB=0) → Z=1
        (M=0, MSB=1) → Z=0
        (M=1, MSB=0) → Z=0
        (M=1, MSB=1) → Z=1
    """
    key = (secret_bit, msb)
    z_bit = MAPPING_TABLE[key]
    
    return z_bit

def map_from_z(z_bit, msb):
    """
    功能:
        反向映射：使用 Z 碼和 MSB 還原秘密位元 M
    
    參數:
        z_bit: Z 碼位元
        msb: 對應平均值的 MSB
    
    返回:
        secret_bit: 還原的秘密位元
    
    反向映射表:
        (Z=1, MSB=0) → M=0
        (Z=0, MSB=0) → M=1
        (Z=1, MSB=1) → M=1
        (Z=0, MSB=1) → M=0
    """
    key = (z_bit, msb)
    secret_bit = REVERSE_MAPPING_TABLE[key]
    
    return secret_bit
