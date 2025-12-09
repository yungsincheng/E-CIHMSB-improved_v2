
# 建立 image_encoding.py → Z碼圖編碼模組

import numpy as np
import math

from PIL import Image
from binary_operations import int_to_binary, binary_to_int

def z_to_image(z_bits):
  """
  功能:
    將 Z 碼位元列表編碼成灰階圖片
  """
  num_bits = len(z_bits)
  num_pixels = math.ceil(num_bits / 8)

  if num_bits % 8 != 0:
    padding = 8 - (num_bits % 8)
    z_bits = z_bits + [0] * padding
  
  pixels = []
  for i in range(0, len(z_bits), 8):
    byte = z_bits[i:i+8]
    pixel_value = binary_to_int(byte)
    pixels.append(pixel_value)
  
  width = int(math.sqrt(num_pixels))
  height = math.ceil(num_pixels / width)
  
  while len(pixels) < width * height:
    pixels.append(0)
  
  pixel_array = np.array(pixels, dtype=np.uint8)
  pixel_array = pixel_array[:width * height].reshape(height, width)
  
  image = Image.fromarray(pixel_array, mode='L')
  
  return image

def image_to_z(image, original_bit_length=None):
  """
  功能:
    從灰階圖片解碼 Z 碼位元列表
  """
  pixel_array = np.array(image)
  pixels = pixel_array.flatten()
  
  z_bits = []
  for pixel in pixels:
    binary = int_to_binary(pixel, 8)
    z_bits.extend(binary)
  
  if original_bit_length is not None:
    z_bits = z_bits[:original_bit_length]
  
  return z_bits
