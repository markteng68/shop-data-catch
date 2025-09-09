from product import StandardProduct
import json
import traceback
import asyncio
from pyppeteer import launch
import requests
import os

# 設定檔案路徑
file_path = r"C:\Users\mark0\Desktop\program\hello\alkemillacosmetici.it\\merged_products.txt"

def save_corrected_product(file_path, line_number, corrected_product):
    """根據出錯行數將修正後的資料寫回原始檔案"""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()

        lines[line_number - 1] = json.dumps(corrected_product, ensure_ascii=False) + "\n"

        with open(file_path, 'w', encoding='utf-8') as file:
            file.writelines(lines)
        print(f"💾 第 {line_number} 行資料已成功寫回檔案。")

    except Exception as e:
        print(f"💥 寫入修正資料時發生錯誤：{str(e)}")
        traceback.print_exc()

# ✅ 使用 pyppeteer 從 URL 抓取產品價格並轉換為 USD，並加入延遲以確保網頁加載
async def scrape_product_info(product_url, exchange_rate):
    try:
        browser = await launch(
            headless=False,
            args=['--no-sandbox', '--disable-setuid-sandbox'],
            executablePath='C:/Program Files/Google/Chrome/Application/chrome.exe'
        )
        page = await browser.newPage()
        await page.goto(product_url, timeout=60000)

        # 等待網頁完全載入 (延遲 5 秒)
        await asyncio.sleep(5)

        price_data = await page.evaluate("""() => {
            let priceElemso = document.querySelector("span.line-through");
    let priceElemsd = Array.from(document.querySelectorAll("span.text-danger"));
    
    let original_price = priceElemso ? priceElemso.textContent.replace(/[^0-9]/g, "").trim() : "N/A";

    // **检查所有 `div`，如果包含 `¥`，提取价格**
    let priceDivs = Array.from(document.querySelectorAll("div"))
        .filter(div => div.textContent.includes("¥")) // 先筛选包含 `¥` 的 div
        .map(div => div.textContent.replace(/[^0-9]/g, "").trim())
        .filter(text => text.length > 2 && text.length < 7); // 限制 3-6 位数字

    let member_price = "N/A";
    
    if (priceDivs.length > 0) {
        member_price = priceDivs[0];  // 取第一个有效价格
    }

    // **逻辑修正**
    if (!original_price || original_price === "N/A") {
        if (member_price !== "N/A") {
            original_price = member_price;
            member_price = "N/A";
        }
    } else if (original_price === member_price) {
        member_price = "N/A";
    } else if (parseInt(original_price) < parseInt(member_price)) {
        // 互换 original_price 和 member_price
        let temp = original_price;
        original_price = member_price;
        member_price = temp;
    }

    return { original_price, member_price };
        }""")

        await browser.close()

        eur_price = float(price_data["original_price"]) if price_data["original_price"] != "N/A" else None
        if eur_price:
            usd_price = eur_price * exchange_rate
            return round(usd_price, 2)
        return None

    except Exception as e:
        print(f"🌐 從 {product_url} 抓取價格時發生錯誤：{str(e)}")
        traceback.print_exc()
        return None

# ✅ 取得 EUR -> USD 匯率
def get_exchange_rate():
    try:
        response = requests.get("https://api.exchangerate-api.com/v4/latest/EUR")
        if response.status_code == 200:
            rates = response.json()["rates"]
            return rates.get("USD", 1)
        return 1
    except Exception as e:
        print(f"💱 取得匯率時發生錯誤：{str(e)}")
        traceback.print_exc()
        return 1
# ✅ 修正 categories 欄位重複值
def fix_duplicate_categories(categories):
    try:
        if categories:
            category_list = categories.split('>')
            unique_categories = []
            for cat in category_list:
                cat = cat.strip()
                if cat not in unique_categories:
                    unique_categories.append(cat)
            return ' > '.join(unique_categories)
        return categories
    except Exception as e:
        print(f"⚠️ 修正 categories 欄位時發生錯誤：{str(e)}")
        traceback.print_exc()
        return categories

# ✅ 根據錯誤類型進行相應修復
async def handle_error(product, idx, error_msg, exchange_rate):
    if "category must be unique" in error_msg:
        print(f"🛠️ 嘗試修正第 {idx} 行的 categories 欄位...")
        product['categories'] = fix_duplicate_categories(product.get('categories'))
        save_corrected_product(file_path, idx, product)
        return product

    elif "price" in error_msg and "url" in product:
        print(f"🌐 嘗試從 {product['url']} 重新抓取價格...")
        updated_price = await scrape_product_info(product['url'], exchange_rate)
        if updated_price:
            product['price'] = updated_price
            print(f"💲 已重新取得價格（USD）：{updated_price}，重新處理並寫回檔案...")
            save_corrected_product(file_path, idx, product)
            return product
        else:
            print(f"⚠️ 無法取得價格，停止處理。")
            return None

    else:
        print(f"⚡ 無法自動修復的錯誤：{error_msg}")
        return None

# ✅ 使用 StandardProduct 逐行解析檔案，根據錯誤自動修正並寫回原始檔案
async def process_products(file_path):
    try:
        exchange_rate = get_exchange_rate()
        with open(file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()

        for idx, line in enumerate(lines, start=1):
            try:
                print(f"🔄 正在解析第 {idx} 行資料...")
             
                product = json.loads(line.strip())
             
            
                print(f"✅ 第 {idx} 行 JSON 解析成功，開始使用 StandardProduct 處理...")

                standard_product = StandardProduct(**product)
                uploadable_product = standard_product.model_dump()
                print(f"✅ 第 {idx} 行產品資料處理成功：")
                print(uploadable_product)

            except Exception as e:
                error_msg = str(e)
                print(f"❌ 第 {idx} 行產品資料處理時發生錯誤：{error_msg}")
                print("出錯的產品資料：")
                print(json.dumps(product, ensure_ascii=False, indent=2))
                traceback.print_exc()

                # 根據錯誤進行修復
                corrected_product = await handle_error(product, idx, error_msg, exchange_rate)
                if corrected_product:
                    try:
                        standard_product = StandardProduct(**corrected_product)
                        uploadable_product = standard_product.model_dump()
                        print(f"✅ 第 {idx} 行資料修正後處理成功：")
                        print(uploadable_product)
                    except Exception as inner_e:
                        print(f"❌ 修正後仍發生錯誤：{str(inner_e)}")
                        traceback.print_exc()
                        return  # 出現錯誤時立即停止
                else:
                    print("⚠️ 無法修正錯誤，停止處理。")
                    return  # 出現錯誤時立即停止

    except Exception as e:
        print("💥 檔案處理時發生錯誤：")
        print(f"錯誤訊息：{str(e)}")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(process_products(file_path))