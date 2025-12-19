# 建立 permutation.py → 排列密鑰模組
# Q 密鑰生成與排列操作

import numpy as np
import hashlib

def generate_Q_from_block(block, q_length=7, contact_key=None):
    """
    功能:
        從 8×8 區塊的第一行前 q_length 個像素生成排列密鑰 Q
        如果提供 contact_key，會將其混入計算，使不同對象產生不同的 Q
    
    參數:
        block: numpy array，8×8 灰階區塊或 8×8×3 彩色區塊
        q_length: Q 的長度，預設 7
        contact_key: 對象專屬密鑰（字串），用於區分不同對象
    
    返回:
        Q: 排列順序列表（1-based 索引）
    
    原理:
        1. 取區塊第一行前 7 個像素值
        2. 按值排序，得到 Q
        3. 用 contact_key 對 Q 進行額外置換（增加安全性）
    
    範例:
        像素值 [44, 61, 72, 58, 70, 79, 66]
        排序後 [44, 58, 61, 66, 70, 72, 79]
                ↓   ↓   ↓   ↓   ↓   ↓   ↓
        索引   [1,  4,  2,  7,  5,  3,  6]
        Q = [1, 4, 2, 7, 5, 3, 6]
    """
    block = np.array(block)
    
    # 判斷圖像類型並取第一行
    # 彩色區塊需轉灰階（使用標準權重）
    if len(block.shape) == 3:  # 彩色區塊
        first_row = (
            0.299 * block[0, :, 0] + 
            0.587 * block[0, :, 1] + 
            0.114 * block[0, :, 2]
        ).astype(np.float64)
    else:  # 灰階區塊
        first_row = block[0, :].astype(np.float64)
    
    # 只取前 q_length 個像素
    first_row = first_row[:q_length]
    
    # 排序後得到每個數值在排序中的位置（0-based）
    sorted_indices = np.argsort(first_row)
    
    # 轉換成 1-based 索引
    Q = (sorted_indices + 1).tolist()
    
    # 用 contact_key 對 Q 進行額外置換
    if contact_key:
        # 步驟 1：用 SHA-256 把 contact_key 轉成固定的 hash 值
        # 例如 "Alice" → 32 bytes 的 hash
        key_hash = hashlib.sha256(contact_key.encode('utf-8')).digest()

        # 步驟 2：取 hash 的前 4 bytes 作為種子
        # 同一個 contact_key 永遠產生同一個種子
        perm_seed = int.from_bytes(key_hash[:4], 'big')
        
        # 步驟 3：用種子建立隨機數生成器，生成置換順序
        # 同一個種子永遠產生同一個置換順序
        rng = np.random.default_rng(perm_seed)
        perm_order = list(range(q_length))  # 建立索引列表 [0,1,2,3,4,5,6]
        rng.shuffle(perm_order)             # 打亂順序，例如 [3,0,5,1,6,2,4]
        
        # 步驟 4：用置換順序重新排列 Q
        # 例如 Q = [1,4,2,7,5,3,6], perm_order = [3,0,5,1,6,2,4]
        #      新 Q = [Q[3], Q[0], Q[5], Q[1], Q[6], Q[2], Q[4]]
        #           = [7, 1, 3, 4, 6, 2, 5]
        Q = [Q[i] for i in perm_order]
    
    return Q

def apply_permutation(values, Q):
    """
    功能:
        使用 Q 重新排列一組值
    
    參數:
        values: 要排列的值列表（長度應等於 len(Q)）
        Q: 排列順序（1-based 索引）
    
    返回:
        reordered: 重新排列後的值列表
    
    範例:
        values = [A, B, C, D, E, F, G]
        Q = [3, 1, 4, 2, 7, 5, 6]
        
        位置 1 ← 原位置 3 的值: C
        位置 2 ← 原位置 1 的值: A
        位置 3 ← 原位置 4 的值: D
        ...
        reordered = [C, A, D, B, G, E, F]
    """
    if len(values) != len(Q):
        raise ValueError(f"值的數量 ({len(values)}) 必須等於 Q 的長度 ({len(Q)})")
    
    # Q 是 1-based，轉成 0-based
    Q_zero_based = [q - 1 for q in Q]
    reordered = [values[i] for i in Q_zero_based]
    
    return reordered

def apply_Q_three_rounds(averages_21, Q):
    """
    功能:
        將 21 個平均值分成 3 輪，每輪使用相同的 Q 進行排列
    
    參數:
        averages_21: 21 個平均值的列表
        Q: 排列順序（長度為 7 的列表）
    
    返回:
        reordered_all: 重新排列後的 21 個平均值
    
    原理:
        21 個平均值分成 3 輪：
        第 1 輪: averages_21[0:7]   → 用 Q 排列
        第 2 輪: averages_21[7:14]  → 用 Q 排列
        第 3 輪: averages_21[14:21] → 用 Q 排列
    """
    if len(averages_21) != 21:
        raise ValueError(f"必須提供 21 個平均值，但收到 {len(averages_21)} 個")
    if len(Q) != 7:
        raise ValueError(f"Q 的長度必須是 7，但收到 {len(Q)} 個")
    
    round1 = apply_permutation(averages_21[0:7], Q)    # 第 1 輪
    round2 = apply_permutation(averages_21[7:14], Q)   # 第 2 輪
    round3 = apply_permutation(averages_21[14:21], Q)  # 第 3 輪
    
    reordered_all = round1 + round2 + round3
    return reordered_all
