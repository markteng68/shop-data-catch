import os
import re

# **定义文件夹路径**
input_folder = r'C:\Users\mark0\Desktop\program\hello\product_details'
output_file = r'C:\Users\mark0\Desktop\program\hello\all_products.txt'

# **获取所有 TXT 文件**
txt_files = [f for f in os.listdir(input_folder) if f.endswith('.txt')]

# **合并所有文件**
with open(output_file, 'w', encoding='utf-8') as outfile:
    for txt_file in txt_files:
        file_path = os.path.join(input_folder, txt_file)
        
        with open(file_path, 'r', encoding='utf-8') as infile:
            product_data = infile.read().strip()

            # **移除换行，使其成为单行**
            single_line_product = " ".join(product_data.splitlines())

            # **清理 `{` 后和 `,` 后的多余空格**
            single_line_product = re.sub(r'\{\s+', '{', single_line_product)  # `{` 后的空格
            single_line_product = re.sub(r',\s+"', ',"', single_line_product)  # `,` 后 `" ` 之间的空格

            # **写入数据，每个产品独立成一行**
            outfile.write(single_line_product + "\n")

print(f"✅ 所有产品数据已合并并清理空格，保存到 {output_file}")
