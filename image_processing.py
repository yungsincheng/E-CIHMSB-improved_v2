# 建立 image_processing.py → 圖像處理模組
# 多層次平均值計算

import numpy as np

def calculate_hierarchical_averages(block_8x8):
    """
    功能:
        計算一個 8×8 區塊的多層次平均值（三層結構）
    
    參數:
        block_8x8: 8×8 的 numpy array
    
    返回:
        averages_21: 21 個平均值的列表
            - 前 16 個: 第一層（16 個 2×2 區塊的平均值）
            - 中 4 個: 第二層（4 個分組的平均值）
            - 最後 1 個: 第三層（1 個總平均值）
    
    原理:
        第一層: 將 8×8 區塊切成 16 個 2×2 子區塊，計算每個子區塊平均值
        第二層: 將第一層的 16 個平均值排成 4×4，分成 4 組（每組 2×2），計算每組平均值
        第三層: 將第二層的 4 個平均值計算總平均
    """
    block_8x8 = np.array(block_8x8)
    
    # ========== 第一層: 16 個 2×2 區塊（向量化）==========
    # 把 8×8 reshape 成 (4, 2, 4, 2)，對 axis 1 和 3 取平均
    reshaped = block_8x8.reshape(4, 2, 4, 2)
    layer1 = reshaped.mean(axis=(1, 3))  # 結果: 4×4
    layer1_averages = layer1.flatten().astype(int).tolist()
    
    # ========== 第二層: 4 個分組（對第一層的 16 個平均值重新分組）（向量化）==========
    # 把 4×4 reshape 成 (2, 2, 2, 2)，對 axis 1 和 3 取平均
    layer1_2x2 = layer1.reshape(2, 2, 2, 2)
    layer2 = layer1_2x2.mean(axis=(1, 3))  # 結果: 2×2
    layer2_averages = layer2.flatten().astype(int).tolist()
    
    # ========== 第三層: 1 個 8×8 整體（對第二層的 4 個平均值計算總平均）==========
    layer3_average = int(layer2.mean())
    
    # ========== 合併三層結果 ==========
    averages_21 = layer1_averages + layer2_averages + [layer3_average]
    
    return averages_21
