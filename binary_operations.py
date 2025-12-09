
# 建立 binary_operations.py → 二進位處理模組

def int_to_binary(number, bit_length=8):
  """
  功能:
    把整數轉成固定長度的二進位列表

  參數:
    number: 要轉換的整數 (0-255)
    bit_length: 二進位位數（預設8位）

  返回:
    binary: 二進位列表，例如 [0, 1, 0, 0, 0, 0, 0, 1] 代表 65
  """
  binary_str = bin(number)[2:]  # 去掉開頭的'0b'
  binary_str = binary_str.zfill(bit_length)  # 不夠長就在前面補0
  binary = [int(bit) for bit in binary_str]  # 轉成數字列表

  return binary

def get_msb(number):
  """
  功能:
    取出一個數字的 MSB (最高有效位)

  參數:
    number: 要檢查的數字 (0-255 的像素值)

  返回:
    msb: 最高位元的值

  原理:
    十進位平均值若小於 128 則 MSB=0，否則為 1
    （等同於二進位最高位的判斷，但運算更快）
  """
  msb = 1 if number >= 128 else 0
    
  return msb

def binary_to_int(binary):
  """
  功能:
    把二進位列表轉回十進位整數

  參數:
    binary: 二進位位元列表

  返回:
    number: 對應的十進位整數
  """
  # 將二進位列表轉成二進位字串，例如: [1, 0, 1] → "101"
  binary_str = ''.join(str(bit) for bit in binary)

  # 將二進位字串轉成十進位整數 (base 2)
  number = int(binary_str, 2)

  return number

def get_msbs(numbers):
  """
  功能:
    一次取得多個數字的 MSB

  參數:
    numbers: 數字列表（平均值們）

  返回:
    msbs: 所有數字的 MSB 列表
  """
  msbs = [get_msb(num) for num in numbers]

  return msbs

def text_to_utf8(text):
  """
  功能:
    將文字轉換成 UTF-8 編碼的二進位列表

  參數:
    text: 要編碼的文字字串

  返回:
    bits: UTF-8 編碼的二進位列表

  原理:
    使用 UTF-8 編碼
    - ASCII 字元: 1 byte = 8 bits
    - 中文字元: 3 bytes = 24 bits
  """
  bits = []

  # 將字串編碼成 UTF-8
  text_bytes = text.encode('utf-8')

  # 將每個 byte 轉換成 8 bits
  for byte in text_bytes:
    binary = int_to_binary(byte, 8)
    bits.extend(binary)

  return bits

def utf8_to_text(bits):
  """
  功能:
    將 UTF-8 編碼的二進位列表轉回文字

  參數:
    bits: UTF-8 編碼的二進位列表

  返回:
    text: 解碼後的文字字串
  """
  byte_list = []

  # 每 8 個 bit 組成一個 byte
  for i in range(0, len(bits), 8):
    byte = bits[i:i+8]
    if len(byte) == 8:
      byte_value = int(''.join(map(str, byte)), 2)
      byte_list.append(byte_value)

  try:
    # 用 UTF-8 解碼
    text = bytes(byte_list).decode('utf-8', errors='ignore')

    return text

  except:
    # 解碼失敗時，用替代字元處理
    text = bytes(byte_list).decode('utf-8', errors='replace')

    return text
