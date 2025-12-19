# 建立 main.py → 完整流程展示

import numpy as np

from config import PROJECT_NAME, VERSION, TEST_IMAGE, TEST_SECRET
from config import BLOCK_SIZE, TOTAL_AVERAGES_PER_UNIT, Q_LENGTH, Q_ROUNDS
from embed import calculate_capacity
from binary_operations import int_to_binary, binary_to_int, get_msbs
from secret_encoding import text_to_binary, binary_to_text
from permutation import generate_Q_from_block, apply_permutation, apply_Q_three_rounds
from image_processing import calculate_hierarchical_averages
from mapping import map_to_z, map_from_z
from embed import embed_secret
from extract import extract_secret
from text_encoding import z_to_text, text_to_z
from image_encoding import z_to_image, image_to_z

def print_section(title):
    print()
    print("=" * 40)
    print(title)
    print("=" * 40)
    print()

def demo_complete_process():
    """
    功能:
        完整展示多層次 E-CIHMSB 隱寫術流程，包含發送方和接收方的所有步驟

    流程:
     【發送方 Alice】
      1. 從圖片產生密鑰 Q
      2. 計算多層次平均值 (三層結構)
      3. 使用 Q 分 3 輪排列平均值
      4. 提取排列後平均值的 MSB
      5. 嵌入秘密訊息並生成 Z 碼
      6. Z 碼編碼 (文字或圖片格式)
      7. 傳送檔案

     【接收方 Bob】
      1. 重建密鑰 Q
      2. 解碼 Z 碼
      3. 重建多層次平均值
      4. 重建 MSB 序列
      5. 提取秘密訊息
      6. 驗證結果
    """
    # 準備測試資料
    image = np.array(TEST_IMAGE)
    secret_message = TEST_SECRET
    rows, cols = image.shape

    print("=" * 40)
    print(f"       {PROJECT_NAME}")
    print(f"       Version {VERSION}")
    print("=" * 40)
    print()

    # ==================== 顯示原始圖片 ====================
    print_section(f"{rows}×{cols} 灰階圖片 (掩護圖片)")

    print("原始像素值:")
    for row in image:
        print("  " + "  ".join(f"{val:3d}" for val in row))
    print()

    # 計算容量
    capacity = calculate_capacity(cols, rows)
    print(f"圖片容量: {capacity} 位元")
    print(f"(共 {(rows//8) * (cols//8)} 個 8×8 區塊，每個區塊 {TOTAL_AVERAGES_PER_UNIT} 位元)")
    print()
    
    # ==================== 發送方 Alice ====================
    print()
    print("=" * 40)
    print()
    print()
    print("【發送方 Alice】")

    # ==================== 步驟1: 生成密鑰Q ====================
    print_section("步驟1: 從圖片產生密鑰 Q")

    first_row = image[0, :]
    print("▸ 取出圖片第一行的前 7 個像素:")
    print(" " + " ".join(f"{val:3d}" for val in first_row[:7]))
    print()

    sorted_pairs = sorted(enumerate(first_row[:7]), key=lambda x: x[1])
    print("▸ 按像素值從小到大排序:")
    print("  索引 | 像素值")
    print("  -----+-------")
    for pos, val in sorted_pairs:
        print(f"   {pos}   |  {val:3d}")
    print()

    Q = generate_Q_from_block(image, Q_LENGTH)
    positions = [str(p[0]) for p in sorted_pairs]
    print(f"  排序後的索引順序: {', '.join(positions)}")
    print(f"  生成密鑰 Q: {Q}")
    print()
    print(f"▸ Q 中的數字 1-7 表示「取排序後的第幾個位置」")
    print(f"▸ Q 將重複使用 {Q_ROUNDS} 輪")
    print()

    # ==================== 步驟2: 多層次結構計算 ====================
    print_section("步驟2: 計算多層次平均值")

    print(f"對 8×8 圖片計算三層結構的 {TOTAL_AVERAGES_PER_UNIT} 個平均值:")
    print()

    averages_21 = calculate_hierarchical_averages(image)

    # 顯示第一層詳細過程
    print("【第一層】16 個 2×2 blocks (切割原始圖片):")
    print()

    layer1_index = 0
    for i in range(4):      # 4 行
        for j in range(4):  # 4 列
            start_row = i * 2
            end_row = start_row + 2
            start_col = j * 2
            end_col = start_col + 2

            block_2x2 = image[start_row:end_row, start_col:end_col]
            avg = averages_21[layer1_index]

            print(f" 區塊{layer1_index+1:2d}:")
            for row in block_2x2:
                print("  " + " ".join(f"{val:3d}" for val in row))
            pixel_sum = np.sum(block_2x2)
            pixel_count = block_2x2.size
            print(f" 平均值: {pixel_sum}/{pixel_count} = {avg}")
            print()

            layer1_index += 1

    print(f" 第一層平均值: {averages_21[:16]}")
    print()
    print()

    # 顯示第二層詳細過程
    print("【第二層】4 個分組 (對第一層的 16 個平均值重新分組):")
    print()
    print(" 將第一層的 16 個平均值排成 4×4 矩陣:")
    layer1_matrix = np.array(averages_21[:16]).reshape(4, 4)
    for row in layer1_matrix:
        print(" " + " ".join(f"{val:3d}" for val in row))
    print()

    layer2_index = 0
    for i in range(2):      # 2 行
        for j in range(2):  # 2 列
            start_row = i * 2
            end_row = start_row + 2
            start_col = j * 2
            end_col = start_col + 2

            group_values = layer1_matrix[start_row:end_row, start_col:end_col]
            avg = averages_21[16 + layer2_index]

            print(f" 分組 {layer2_index+1}:")
            for row in group_values:
                print(" " + " ".join(f"{val:3d}" for val in row))
            group_sum = np.sum(group_values)
            group_count = group_values.size
            print(f" 平均值: {group_sum}/{group_count} = {avg}")
            print()

            layer2_index += 1

    print(f" 第二層平均值: {averages_21[16:20]}")
    print()
    print()

    # 顯示第三層詳細過程
    print("【第三層】1 個總平均 (對第二層的 4 個平均值計算平均):")
    print()
    layer2_values = averages_21[16:20]
    print(f" 第二層的 4 個平均值: {layer2_values}")
    layer3_sum = sum(layer2_values)
    layer3_count = len(layer2_values)
    layer3_avg = averages_21[20]
    print(f" 總平均值: {layer3_sum}/{layer3_count} = {layer3_avg}")
    print()
    print()

    print(f" 三層結構總共 21 個平均值: {averages_21}")
    print()

    # ==================== 步驟3: 使用Q重新排列 ====================
    print_section("步驟3: 使用 Q 分 3 輪排列平均值")

    print(f"將 21 個平均值分成 3 輪，每輪 7 個，用 Q={Q} 排列")
    print()

    print(f"第 1 輪 (前 7 個平均值): {averages_21[0:7]}")
    print(f"用 Q={Q} 排列")
    round1 = apply_permutation(averages_21[0:7], Q)
    print("排列過程:")
    for i, q in enumerate(Q):
        print(f"位置 {i+1} ← 原位置 {q} 的值: {averages_21[q-1]}")
    print(f"排列後: {round1}")
    print()

    print(f"第 2 輪 (中 7 個平均值): {averages_21[7:14]}")
    print(f"用 Q={Q} 排列")
    round2 = apply_permutation(averages_21[7:14], Q)
    print("排列過程:")
    for i, q in enumerate(Q):
        print(f"位置 {i+1} ← 原位置 {q} 的值: {averages_21[7+q-1]}")
    print(f"排列後: {round2}")
    print()

    print(f"第 3 輪 (後 7 個平均值): {averages_21[14:21]}")
    print(f"用 Q={Q} 排列")
    round3 = apply_permutation(averages_21[14:21], Q)
    print("排列過程:")
    for i, q in enumerate(Q):
        print(f"位置 {i+1} ← 原位置 {q} 的值: {averages_21[14+q-1]}")
    print(f"排列後: {round3}")
    print()
    print()

    reordered_all = round1 + round2 + round3
    print(f"排列後的 21 個平均值: {reordered_all}")
    print()

    # ==================== 步驟4: 提取MSB ====================
    print_section("步驟4: 提取排列後平均值的 MSB")

    print("▸ 平均值轉二進位並提取 MSB:")
    print("-" * 40)
    print("  序號 | 平均值 |  二進位  | MSB")
    print("-" * 40)

    msbs = get_msbs(reordered_all)
    for i, avg in enumerate(reordered_all):
        binary = int_to_binary(avg, 8)
        binary_str = ''.join(map(str, binary))
        msb = msbs[i]
        print(f"   {i+1:2d}  |  {avg:3d}  | {binary_str} |  {msb}")

    print()
    print(f"MSB 序列 (21 個): {msbs}")
    print()

    # ==================== 步驟5: 嵌入秘密訊息 ====================
    print_section("步驟5: 嵌入秘密訊息並生成 Z 碼")

    print(f"秘密訊息: \"{secret_message}\"")
    content_bits = text_to_binary(secret_message)
    print(f"UTF-8 編碼: {content_bits}")
    print(f"內容需要 {len(content_bits)} 位元")
    print()

    # 加入類型標記（和 embed.py 一致）
    type_marker = [0]  # 0 = 文字
    secret_bits = type_marker + content_bits
    print(f"▸ 加入類型標記:")
    print(f"  類型標記: {type_marker} (0 = 文字, 1 = 圖片)")
    print(f"  完整 secret_bits: {secret_bits}")
    print(f"  總共 {len(secret_bits)} 位元 (1 bit 類型 + {len(content_bits)} bit 內容)")
    print()

    # 執行嵌入
    z_bits, capacity_result, info = embed_secret(image, secret_message, secret_type='text')

    print("▸ 映射過程: (M,MSB)→Z")
    print("-" * 50)
    print("  i | M[i] | MSB | (M,MSB) | Z[i] | 說明")
    print("-" * 50)

    for i in range(len(secret_bits)):
        bit = secret_bits[i]
        msb = msbs[i]
        z_bit = z_bits[i]
        pair = f"({bit},{msb})"
        if i == 0:
            note = "類型標記"
        else:
            note = f"'{secret_message}' 的第 {i} bit"
        print(f" {i:2d} |  {bit}   |  {msb}  |  {pair}   |  {z_bit}   | {note}")

    print("-" * 50)
    print()
    print(f"Z 碼 ({len(z_bits)} bits): {z_bits}")
    print()

    # ==================== 步驟6: Z碼編碼 ====================
    print_section("步驟6: Z 碼編碼")

    print("▸ 方式 A: 文字格式")
    z_text = z_to_text(z_bits)
    print(f"  Z 碼文字: \"{z_text}\"")
    print()

    print("▸ 方式 B: 圖片格式")
    print("  每 8 位元轉成 1 個像素值:")
    pixels = []
    for i in range(0, len(z_bits), 8):
        byte = z_bits[i:i+8]
        if len(byte) < 8:
            byte = byte + [0] * (8 - len(byte))
        pixel_value = binary_to_int(byte)
        pixels.append(pixel_value)
        byte_str = ''.join(map(str, byte))
        print(f"  位元 [{i:2d}-{min(i+7, len(z_bits)-1):2d}]: {byte_str:8s} → 像素值 {pixel_value:3d}")

    z_image = z_to_image(z_bits)
    print(f"  Z 碼圖片尺寸: {z_image.size[0]}×{z_image.size[1]}")
    print(f"  像素數量: {z_image.size[0] * z_image.size[1]}")
    print()

    # ==================== 步驟7: 傳送 ====================
    print_section("步驟7: 傳送")

    print("Alice 傳送給 Bob:")
    print("1. Z 碼 (文字或圖片格式)")
    print("※雙方必須都有相同的掩護圖片")
    print()

    # ==================== 接收方Bob ====================
    print()
    print("=" * 40)
    print()
    print()
    print("【接收方 Bob】")

    # ==================== 步驟1: 重建密鑰Q ====================
    print_section("步驟1: 重建密鑰 Q")

    print("▸ Bob 也有相同的 cover image")
    print("▸ 從圖片第一行前 7 個像素重建 Q:")
    print(" " + " ".join(f"{val:3d}" for val in first_row[:7]))
    print()

    print("▸ 按像素值從小到大排序:")
    print("  索引 | 像素值")
    print("  -----+-------")
    for pos, val in sorted_pairs:
        print(f"   {pos}   |  {val:3d}")
    print()

    Q_reconstructed = generate_Q_from_block(image, Q_LENGTH)
    print(f"  排序後的索引順序: {', '.join(positions)}")
    print(f"  重建密鑰 Q: {Q_reconstructed}")
    print()
    print(f"▸ 重建的密鑰 Q: {Q_reconstructed}")
    print()

    # ==================== 步驟2: 解碼Z碼 ====================
    print_section("步驟2: 解碼 Z 碼")

    print("▸ 方式 A: 從文字解碼")
    z_decoded_text = text_to_z(z_text)
    print(f"  文字: \"{z_text}\"")
    print(f"  解碼: {z_decoded_text}")
    print()

    print("▸ 方式 B: 從圖片解碼")
    print("  從圖片讀取像素值並轉回位元:")
    z_decoded_image = image_to_z(z_image, len(z_bits))
    for i, pixel in enumerate(pixels):
        start = i * 8
        end = min(start + 8, len(z_decoded_image))
        bits = z_decoded_image[start:end]
        bits_str = ''.join(map(str, bits))
        print(f"  像素值 {pixel:3d} → {bits_str}")
    print(f"  解碼: {z_decoded_image}")
    print()

    # ==================== 步驟3: 重建多層次平均值 ====================
    print_section("步驟3: 重建多層次平均值")

    print("Bob 使用相同的 cover image 重新計算 21 個平均值")
    print("(過程和 Alice 相同，結果也會相同)")
    print()

    # 重新計算
    averages_21_reconstructed = calculate_hierarchical_averages(image)

    print(f"【第一層】16 個 2×2 區塊: {averages_21_reconstructed[:16]}")
    print(f"【第二層】4 個分組: {averages_21_reconstructed[16:20]}")
    print(f"【第三層】1 個總平均: {averages_21_reconstructed[20]}")
    print()
    print(f"重建的 21 個平均值: {averages_21_reconstructed}")
    print()

    # ==================== 步驟4: 重建MSB序列 ====================
    print_section("步驟4: 重建 MSB 序列")

    print("用 Q 重新排列 21 個平均值，然後提取 MSB")
    print()

    # 重新排列
    reordered_all_reconstructed = apply_Q_three_rounds(averages_21_reconstructed, Q_reconstructed)

    print(f"第 1 輪排列後: {reordered_all_reconstructed[0:7]}")
    print(f"第 2 輪排列後: {reordered_all_reconstructed[7:14]}")
    print(f"第 3 輪排列後: {reordered_all_reconstructed[14:21]}")
    print()
    print(f"排列後的 21 個平均值: {reordered_all_reconstructed}")
    print()

    print("▸ 重建 MSB 序列:")
    print("-" * 40)
    print("  序號 | 平均值 |  二進位  | MSB")
    print("-" * 40)

    msbs_reconstructed = get_msbs(reordered_all_reconstructed)
    for i, avg in enumerate(reordered_all_reconstructed):
        binary = int_to_binary(avg, 8)
        binary_str = ''.join(map(str, binary))
        msb = msbs_reconstructed[i]
        print(f"   {i+1:2d}  |  {avg:3d}  | {binary_str} |  {msb}")

    print()
    print(f"重建的 MSB 序列: {msbs_reconstructed}")
    print()

    # ==================== 步驟5: 提取秘密訊息 ====================
    print_section("步驟5: 提取秘密訊息")

    print("▸ 使用重建的 MSB 和收到的 Z 碼提取秘密訊息:")
    print("  (根據 Z 碼和 MSB 用反向映射還原 M)")
    print()

    # 執行提取
    recovered_message, extract_info = extract_secret(image, z_bits, secret_type='text')

    # 手動計算還原的 bits（用於顯示）
    recovered_bits_full = []
    for i in range(len(z_bits)):
        z_bit = z_bits[i]
        msb = msbs_reconstructed[i]
        m_bit = map_from_z(z_bit, msb)
        recovered_bits_full.append(m_bit)

    print("▸ 反向映射過程: (Z,MSB)→M")
    print("-" * 50)
    print("  i | Z[i] | MSB | (Z,MSB) | M[i] | 說明")
    print("-" * 50)

    for i in range(len(z_bits)):
        z_bit = z_bits[i]
        msb = msbs_reconstructed[i]
        m_bit = recovered_bits_full[i]
        pair = f"({z_bit},{msb})"
        if i == 0:
            note = f"類型標記 → {'文字' if m_bit == 0 else '圖片'}"
        else:
            note = f"內容 bit {i-1}"
        print(f" {i:2d} |  {z_bit}   |  {msb}  |  {pair}   |  {m_bit}   | {note}")

    print("-" * 50)
    print()

    # 分離類型標記和內容
    type_marker_recovered = recovered_bits_full[0]
    content_bits_recovered = recovered_bits_full[1:]

    print(f"▸ 解析還原的位元:")
    print(f"  類型標記: {type_marker_recovered} → {'文字' if type_marker_recovered == 0 else '圖片'}")
    print(f"  內容位元: {content_bits_recovered}")
    print()

    # 將內容位元轉回文字
    recovered_text = binary_to_text(content_bits_recovered)
    print(f"▸ UTF-8 解碼: {content_bits_recovered} → \"{recovered_text}\"")
    print()
    print(f"還原的秘密訊息: \"{recovered_message}\"")
    print()

    # ==================== 驗證結果 ====================
    print_section("驗證結果")

    print(f"原始秘密訊息: \"{secret_message}\"")
    print(f"還原秘密訊息: \"{recovered_message}\"")
    print()

    if recovered_message == secret_message:
        print("✅ 驗證成功! 秘密訊息完整還原!")
    else:
        print("❌ 驗證失敗!")
        print()
        print("除錯資訊:")
        print(f"  原始 content_bits: {content_bits}")
        print(f"  還原 content_bits: {content_bits_recovered}")
        
        # 找出不同的位置
        for i in range(min(len(content_bits), len(content_bits_recovered))):
            if content_bits[i] != content_bits_recovered[i]:
                print(f"  位置 {i}: 原始={content_bits[i]}, 還原={content_bits_recovered[i]}")
    print()

if __name__ == "__main__":
    demo_complete_process()
