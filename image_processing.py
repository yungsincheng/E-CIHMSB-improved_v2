
# 建立 image_processing.py → 圖片處理模組

import numpy as np

def calculate_hierarchical_averages(block_8x8):
  """
  功能:
    計算一個 8×8 區塊的多層次平均值（三層結構）

  參數:
    block_8x8: 8×8 的 numpy array

  返回:
    averages_21: 21 個平均值的列表
      - 前 16 個: 第一層 (16 個 2×2 區塊的平均值)
      - 中 4 個: 第二層 (4 個分組的平均值)
      - 最後 1 個: 第三層 (1 個總平均值)

  原理:
    第一層: 將 8×8 圖片切成 16 個 2×2 區塊，計算每個區塊平均值
    第二層: 將第一層的 16 個平均值排成 4×4，分成 4 組 (每組 2×2)，計算每組平均值
    第三層: 將第二層的 4 個平均值計算總平均
  """
  block_8x8 = np.array(block_8x8)

  # ========== 第一層: 16 個 2×2 區塊 (向量化) ==========
  # 把 8×8 reshape 成 (4, 2, 4, 2)，對 axis 1 和 3 取平均
  reshaped = block_8x8.reshape(4, 2, 4, 2)
  layer1 = reshaped.mean(axis=(1, 3))  # 結果: 4×4
  layer1_averages = layer1.flatten().astype(int).tolist()

  # ========== 第二層: 4 個分組 (對第一層的 16 個平均值重新分組) (向量化) ==========
  # 把 4×4 reshape 成 (2, 2, 2, 2)，對 axis 1 和 3 取平均
  layer1_2x2 = layer1.reshape(2, 2, 2, 2)
  layer2 = layer1_2x2.mean(axis=(1, 3))  # 結果: 2×2
  layer2_averages = layer2.flatten().astype(int).tolist()

  # ========== 第三層: 1 個 8×8 整體 (對第二層的 4 個平均值計算總平均) ==========
  layer3_average = int(layer2.mean())

  # ========== 合併三層結果 ==========
  averages_21 = layer1_averages + layer2_averages + [layer3_average]
    
  return averages_21

def process_image_multilayer(image):
  """
  功能:
    處理整張圖片，計算所有 8×8 區塊的多層次平均值

  參數:
    image: numpy array，灰階圖片（H×W）或彩色圖片（H×W×3）

  返回:
    all_averages: 所有 8×8 區塊的平均值列表
                  結構: [[區塊1 的 21 個平均值], [區塊2 的 21 個平均值], ...]
    num_units: 8×8 區塊的數量
  """
  image = np.array(image)

  # 判斷圖片類型，若為彩色則轉成灰階
  if len(image.shape) == 3:  # 彩色圖片
    # 使用標準灰階轉換公式
    # 綠色權重最高 (0.587)，紅色次之 (0.299)，藍色最低 (0.114)
    image = (0.299 * image[:, :, 0] + 0.587 * image[:, :, 1] + 0.114 * image[:, :, 2]).astype(np.uint8)

  height, width = image.shape

  # 檢查圖片大小是否為 8 的倍數
  if height % 8 != 0 or width % 8 != 0:
    raise ValueError(f"圖片大小必須是 8 的倍數！當前大小: {width}×{height}")

  # 計算有多少個 8×8 區塊
  num_rows = height // 8
  num_cols = width // 8
  num_units = num_rows * num_cols

  # ========== 向量化優化: 一次處理所有區塊 ==========
  # 步驟 1: 把整張圖片 reshape 成所有 8×8 區塊
  # (H, W) → (num_rows, 8, num_cols, 8) → (num_units, 8, 8)
  blocks = image.reshape(num_rows, 8, num_cols, 8).transpose(0, 2, 1, 3).reshape(num_units, 8, 8)

  # 步驟 2: 第一層 - 每個區塊的 16 個 2×2 平均值
  # (num_units, 8, 8) → (num_units, 4, 2, 4, 2)
  reshaped = blocks.reshape(num_units, 4, 2, 4, 2)
  layer1 = reshaped.mean(axis=(2, 4))  # (num_units, 4, 4)
  layer1_flat = layer1.reshape(num_units, 16)

  # 步驟 3: 第二層 - 每個區塊的 4 個分組平均值
  # (num_units, 4, 4) → (num_units, 2, 2, 2, 2)
  layer1_2x2 = layer1.reshape(num_units, 2, 2, 2, 2)
  layer2 = layer1_2x2.mean(axis=(2, 4))  # (num_units, 2, 2)
  layer2_flat = layer2.reshape(num_units, 4)

  # 步驟 4: 第三層 - 每個區塊的 1 個總平均
  layer3 = layer2.mean(axis=(1, 2)).reshape(num_units, 1)

  # 步驟 5: 合併三層，轉成整數
  all_averages_array = np.concatenate([layer1_flat, layer2_flat, layer3], axis=1)
  all_averages_array = all_averages_array.astype(int)

  # 轉成列表格式（保持原有介面）
  all_averages = all_averages_array.tolist()

  return all_averages, num_units
