# permutation.py → 密鑰 Q 生成模組（含對象密鑰支援）

import numpy as np
import hashlib

def generate_Q_from_block(block, q_length=7, contact_key=None):
    """
    功能:
        從 8×8 區塊的第一行前 q_length 個像素生成排列密鑰 Q
        如果提供 contact_key，會將其混入計算，使不同對象產生不同的 Q
    
    參數:
        block: numpy array，8×8 灰階區塊 或 8×8×3 彩色區塊
        q_length: Q 的長度，預設 7
        contact_key: 對象專屬密鑰（字串），用於區分不同對象
    
    返回:
        Q: 排列順序列表 (1-based 索引)
    
    原理:
        1. 取區塊第一行前 7 個像素值
        2. 如果有 contact_key，用它對最終的 Q 進行額外置換
        3. 按值排序，得到 Q
    """
    # 取出圖片
    block = np.array(block)
    
    # 判斷圖片類型並取第一行
    if len(block.shape) == 3:  # 彩色區塊
        first_row = (0.299 * block[0, :, 0] + 0.587 * block[0, :, 1] + 0.114 * block[0, :, 2]).astype(np.float64)
    else:  # 灰階區塊
        first_row = block[0, :].astype(np.float64)
    
    # 只取前 q_length 個像素
    first_row = first_row[:q_length]
    
    # 排序後得到每個數值在排序中的位置 (0-based)
    sorted_indices = np.argsort(first_row)
    
    # 轉換成 1-based 索引
    Q = (sorted_indices + 1).tolist()
    
    # 如果有 contact_key，對 Q 進行額外的確定性置換
    if contact_key:
        # 用 contact_key 生成一個固定的置換種子
        key_hash = hashlib.sha256(contact_key.encode('utf-8')).digest()
        perm_seed = int.from_bytes(key_hash[:4], 'big')
        
        # 用這個種子生成一個固定的置換
        rng = np.random.default_rng(perm_seed)
        perm_order = list(range(q_length))
        rng.shuffle(perm_order)
        
        # 對 Q 應用這個置換
        Q = [Q[i] for i in perm_order]
    
    return Q


def apply_permutation(values, Q):
    """
    功能:
        使用 Q 重新排列一組值
    
    參數:
        values: 要排列的值列表 (長度應等於 len(Q))
        Q: 排列順序 (1-based 索引)
    
    返回:
        reordered: 重新排列後的值列表
    """
    if len(values) != len(Q):
        raise ValueError(f"值的數量 ({len(values)}) 必須等於 Q 的長度 ({len(Q)})")
    
    Q_zero_based = [q - 1 for q in Q]
    reordered = [values[i] for i in Q_zero_based]
    
    return reordered


def apply_Q_three_rounds(averages_21, Q):
    """
    功能:
        將 21 個平均值分成 3 輪，每輪使用相同的 Q 進行排列
    
    參數:
        averages_21: 21 個平均值的列表
        Q: 排列順序 (長度為 7 的列表)
    
    返回:
        reordered_all: 重新排列後的 21 個平均值
    """
    if len(averages_21) != 21:
        raise ValueError(f"必須提供 21 個平均值，但收到 {len(averages_21)} 個")
    if len(Q) != 7:
        raise ValueError(f"Q 的長度必須是 7，但收到 {len(Q)} 個")
    
    round1 = apply_permutation(averages_21[0:7], Q)
    round2 = apply_permutation(averages_21[7:14], Q)
    round3 = apply_permutation(averages_21[14:21], Q)
    
    reordered_all = round1 + round2 + round3
    
    return reordered_all
