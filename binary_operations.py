# 建立 binary_operations.py → 二進位處理模組
# 整數與二進位列表的轉換、MSB 提取、文字編碼

def int_to_binary(number, bit_length=8):
    """
    功能:
        把整數轉成固定長度的二進位列表
    
    參數:
        number: 要轉換的整數 (0-255)
        bit_length: 二進位位數（預設 8 位）
    
    返回:
        binary: 二進位列表
    
    範例:
        65 → [0, 1, 0, 0, 0, 0, 0, 1]
        255 → [1, 1, 1, 1, 1, 1, 1, 1]
    """
    binary_str = bin(number)[2:]  # 去掉開頭的 '0b'，例如 bin(65) = '0b1000001' → '1000001'
    binary_str = binary_str.zfill(bit_length)  # 不夠長就在前面補 0，例如 '1000001' → '01000001'
    binary = [int(bit) for bit in binary_str]  # 轉成數字列表，例如 '01000001' → [0,1,0,0,0,0,0,1]
    return binary

def binary_to_int(binary):
    """
    功能:
        把二進位列表轉回十進位整數
    
    參數:
        binary: 二進位位元列表
    
    返回:
        number: 對應的十進位整數
    
    範例:
        [0, 1, 0, 0, 0, 0, 0, 1] → 65
        [1, 1, 1, 1, 1, 1, 1, 1] → 255
    """
    binary_str = ''.join(str(bit) for bit in binary)  # 列表轉字串，例如 [1,0,1] → '101'
    number = int(binary_str, 2)  # 二進位字串轉十進位，例如 '101' → 5
    return number

def get_msb(number):
    """
    功能:
        取出一個數字的 MSB（最高有效位元）
    
    參數:
        number: 要檢查的數字 (0-255 的像素值)
    
    返回:
        msb: 最高位元的值（0 或 1）
    
    原理:
        十進位若 < 128 則 MSB = 0，否則 MSB = 1
        等同於二進位最高位的判斷，但運算更快
    
    範例:
        100 → 0（因為 100 < 128）
        200 → 1（因為 200 >= 128）
    """
    msb = 1 if number >= 128 else 0
    return msb

def get_msbs(numbers):
    """
    功能:
        一次取得多個數字的 MSB
    
    參數:
        numbers: 數字列表（平均值們）
    
    返回:
        msbs: 所有數字的 MSB 列表
    
    範例:
        [100, 200, 50, 180] → [0, 1, 0, 1]
    """
    msbs = [get_msb(num) for num in numbers]
    return msbs
