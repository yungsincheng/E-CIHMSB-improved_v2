# 建立 config.py → 配置模組

# 專案資訊
PROJECT_NAME = 'E-CIHMSB Steganography'
VERSION = '2.0.0'

# 區塊處理參數
BLOCK_SIZE = 8  # 固定使用 8×8 作為處理區塊
LAYER1_FRAGMENT_SIZE = 2  # 第一層區塊大小: 2×2
LAYER2_FRAGMENT_SIZE = 4  # 第二層區塊大小: 4×4 (對第一層平均值分組)

# 多層次平均值結構
# 第一層: 將 8×8 切成 16 個 2×2 區塊 → 16 個平均值
# 第二層: 將第一層的 16 個平均值(排成4×4)分成 4 組 → 4 個平均值
# 第三層: 將第二層的 4 個平均值計算總平均 → 1 個平均值
NUM_LAYER1_BLOCKS = (BLOCK_SIZE // LAYER1_FRAGMENT_SIZE) ** 2  # 16 個
NUM_LAYER2_BLOCKS = (BLOCK_SIZE // LAYER2_FRAGMENT_SIZE) ** 2  # 4 個
NUM_LAYER3_BLOCKS = 1  # 1 個

# 總平均值數量: 16+4+1=21
TOTAL_AVERAGES_PER_UNIT = NUM_LAYER1_BLOCKS + NUM_LAYER2_BLOCKS + NUM_LAYER3_BLOCKS

# Q 密鑰參數
Q_LENGTH = 7  # Q 的長度(從圖像第一行取 7 個像素)
Q_ROUNDS = TOTAL_AVERAGES_PER_UNIT // Q_LENGTH  # 重複使用輪數: 21÷7=3

# MSB 映射表
# 正向映射表(論文的表1)：(M,MSB)→Z
MAPPING_TABLE = {
    (0, 0): 1,
    (0, 1): 0,
    (1, 0): 0,
    (1, 1): 1
}

# 反向映射表：(Z,MSB)→M
REVERSE_MAPPING_TABLE = {
    (1, 0): 0,
    (0, 0): 1,
    (1, 1): 1,
    (0, 1): 0
}

# 測試資料 (論文的圖2)
TEST_IMAGE = [
    [44, 61, 72, 58, 70, 79, 66, 79],
    [74, 65, 79, 62, 82, 62, 49, 38],
    [127, 93, 75, 56, 82, 84, 80, 40],
    [112, 117, 103, 60, 98, 88, 92, 79],
    [50, 79, 114, 59, 108, 149, 117, 122],
    [57, 50, 68, 87, 111, 158, 150, 109],
    [89, 85, 64, 84, 134, 116, 90, 105],
    [99, 107, 66, 32, 91, 123, 60, 75]
]

TEST_SECRET = "H"  # 測試機密內容

# 載體容量計算
def calculate_capacity(image_width, image_height):
    """
    功能:
        計算載體圖像的嵌入容量（可藏多少 bits 的機密）
    
    參數:
        image_width: 載體圖像寬度
        image_height: 載體圖像高度
    
    返回:
        capacity: 可嵌入的 bits 數量
    
    公式:
        EC = (W×H) / (8×8) × 21
    
    注意:
        容量以 bits 為單位
        文字採用 UTF-8 編碼 (英文 1 byte, 中文 3 bytes)
    """
    num_units = (image_width // BLOCK_SIZE) * (image_height // BLOCK_SIZE)
    capacity = num_units * TOTAL_AVERAGES_PER_UNIT
    
    return capacity
