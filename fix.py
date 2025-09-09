import os
import json
import re
import asyncio
from pyppeteer import launch

# **指定來源與目的檔案路徑**
input_folder = r'C:\Users\mark0\Desktop\program\hello\alkemillacosmetici.it\product'
output_file = r'C:\Users\mark0\Desktop\program\hello\alkemillacosmetici.it\merged_products.txt'

def process_description(description):
    """確保 description 中的第一個 <div> 是 <div class='naturallabo-desc'>"""
    if not description.startswith("<div class='alkemill-desc'>"):
        description = f"<div class='alkemill-desc'>{description}</div>"
    return description

async def fetch_main_image_url(product_url):
    """使用瀏覽器爬取 mainImageURL"""
    try:
        browser = await launch(
            headless=False,
            args=['--no-sandbox', '--disable-setuid-sandbox'],
            executablePath='C:/Program Files/Google/Chrome/Application/chrome.exe'
        )
        page = await browser.newPage()
        await page.setUserAgent(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )

        await page.goto(product_url, {'waitUntil': 'domcontentloaded'})

        # **執行 JavaScript 取得 mainImageURL**
        main_image_url = await page.evaluate('''() => {
            let imgElem = document.querySelector("input[name='mainImageURL']");
            return imgElem ? imgElem.getAttribute("src") || imgElem.value : null;
        }''')

        await browser.close()
        return main_image_url

    except Exception as e:
        print(f"⚠ 無法抓取 {product_url} 的圖片: {e}")
        return None


async def process_json(data):
    """依據需求調整 JSON 結構與內容"""

    # **如果 images 為 null，則從產品頁面抓取 `mainImageURL`**
    if not data.get("images") or data["images"] in [None, ""]:
        if "url" in data and isinstance(data["url"], str):
            data["images"] = await fetch_main_image_url(data["url"])  # **逐个等待爬取 `mainImageURL`**

    # **清理 images 欄位中的空格**
    if "images" in data and isinstance(data["images"], str):
        data["images"] = data["images"].replace("; ", ";")

    # **確保 description 標籤**
    if "description" in data and isinstance(data["description"], str):
        data["description"] = process_description(data["description"].replace("\n", "").strip())

    # **reviews 欄位只保留數字**
    if "reviews" in data and isinstance(data["reviews"], str):
        reviews_match = re.search(r'\d+', data["reviews"])
        data["reviews"] = int(reviews_match.group()) if reviews_match else None

    

    # **處理 product_id 與 sku 欄位互補**
    if not data.get("product_id") and data.get("sku"):
        data["product_id"] = data["sku"]
    elif not data.get("sku") and data.get("product_id"):
        data["sku"] = data["product_id"]

    # **處理 categories 欄位，保留第一個分類**
    if "categories" in data and isinstance(data["categories"], list) and len(data["categories"]) > 0:
        data["categories"] = data["categories"][0]  # 只保留第一個分類，變成單一字符串

    # **確保 `rating` 只包含數字，否則設為 "N/A"**
    if "rating" in data and isinstance(data["rating"], str):
        clean_rating = data["rating"].replace(".", "").strip()
        data["rating"] = data["rating"] if clean_rating.isdigit() else None

    # **確保 `review_count` 只包含整數，否則設為 "N/A"**
    if "review_count" in data and isinstance(data["review_count"], str):
        data["review_count"] = data["review_count"] if data["review_count"].isdigit() else None
    
    if not data.get("brand") or data["brand"] in ["Brand not found", ""]:
        data["brand"] = None

    if not data.get("variants") or (isinstance(data["variants"], list) and not any(data["variants"])):
        del data["variants"]


    # **所有 "N/A" 轉為 None**
    for key, value in data.items():
        if isinstance(value, str) and value.strip() == "N/A":
            data[key] = None
    
    # **插入指定欄位**
    updated_data = {}
    for key in data:
        updated_data[key] = data[key]
        if key == "url":
            updated_data["source"] = "alkemillacosmetici.net"
        if key == "title":
            updated_data["title_en"] = None
        if key == "description":
            updated_data["description_en"] = None
            updated_data["summary"] = None
        if key == "sku":
            updated_data["upc"] = None
        if key == "brand":
            updated_data["specifications"] = None
        if key == "images":
            updated_data["videos"] = None
        if key == "price":
            updated_data["options"] = None
            updated_data["variants"] = None
            updated_data["returnable"] = None
        if key == "rating":
            updated_data["sold_count"] = None
            updated_data["shipping_fee"] = 0
            updated_data["shipping_days_min"] = None
            updated_data["shipping_days_max"] = None

    # **最終欄位**
    updated_data["has_only_default_variant"] = True

    return updated_data


async def merge_txt_files_to_single_txt(folder_path, output_path):
    """整合所有 txt 檔案並進行結構調整"""
    merged_data = []

    for filename in os.listdir(folder_path):
        if filename.endswith('.txt'):
            file_path = os.path.join(folder_path, filename)
            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    data = json.load(file)
                    cleaned_data = await process_json(data)  # **逐个等待 `process_json()` 完成**
                    merged_data.append(cleaned_data)
            except Exception as e:
                print(f"⚠ 無法處理 {filename}: {e}")

    # **以緊湊格式寫入單一 TXT 檔案**
    with open(output_path, 'w', encoding='utf-8') as out_file:
        for item in merged_data:
            json_line = json.dumps(item, ensure_ascii=False, separators=(',', ':'))
            out_file.write(json_line + '\n')

    print(f"✅ 已成功整合 {len(merged_data)} 筆資料至 {output_path}")

# **執行整合任務**
asyncio.run(merge_txt_files_to_single_txt(input_folder, output_file))
