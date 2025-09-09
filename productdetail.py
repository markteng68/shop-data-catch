import asyncio
import os
import requests
from pyppeteer import launch
from datetime import datetime
import json
import re

### **获取实时汇率**
def get_free_exchange_rate():
    """使用免費的 exchangerate-api 獲取 EUR -> USD 匯率"""
    url = "https://api.exchangerate-api.com/v4/latest/EUR"
    response = requests.get(url)
    data = response.json()

    if "rates" in data and "USD" in data["rates"]:
        return data["rates"]["USD"]
    else:
        print("❌ 无法获取汇率！")
        return None

async def scrape_product_info(product_url, save_path, exchange_rate):
    browser = await launch(
        headless=False, 
        args=['--no-sandbox', '--disable-setuid-sandbox'], 
        executablePath='C:/Program Files/Google/Chrome/Application/chrome.exe'
    )
    page = await browser.newPage()

    print(f"📄 正在访问产品页面: {product_url}")
    await page.goto(product_url, {'timeout': 60000, 'waitUntil': 'domcontentloaded'})

    # **检测产品是否存在**
    
    if page.url != product_url:
        print(f"❌ 产品已跳转，判定为不存在: {page.url}")
        existence = False
    else:
        existence = True  # **保持默认值**


    # **改进: 额外检测 "Sorry, this product cannot be found"**
    not_found_text = await page.evaluate('''() => {
        let errorElem = document.querySelector("body");
        return errorElem ? errorElem.innerText.includes("Sorry, this product cannot be found") : false;
    }''')

    if not_found_text:
        existence = False  # **产品不存在**

    if not existence:
       
        print(f"❌ 产品已下架或页面无效: {product_url}")
        # **存储已下架产品的计数**
        not_found_count = {}  # 以产品 URL 为 Key，计数为 Value

        if not existence: 
            print(f"❌ 产品已下架或页面无效: {product_url}")
    
            # **检查是否已有计数**
            if product_url in not_found_count:
                not_found_count[product_url] += 1
            else:
                not_found_count[product_url] = 1  # **首次出现，初始化为 1**
    
            # **生成唯一文件名**
            full_title = f"产品已下架({not_found_count[product_url]})"
            
        product_data = {
            
            "date": datetime.utcnow().isoformat() + "Z",
            "url": product_url,
            "existence": False,
            "product_id": "N/A",
            "title": full_title,
            "detail_name": "N/A",
            "brand": "N/A",
            "sku": "N/A",
            "categories": "N/A",
            "description": "N/A",
            "price_eur": "N/A",
            "price_old": "N/A",
            "price_usd_dis": "N/A",
            "price_usd_old": "N/A",
            "weight": "N/A",
            "width": "N/A",
            "height": "N/A",
            "length": "N/A",
            "images": "N/A",
            "rating": "N/A",
            "review_count": "N/A"
        }
    else:
        # **抓取 productID**
        product_id = await page.evaluate('''() => {
             let scriptText = [...document.scripts].map(s => s.innerText).join(" ");
            let match = scriptText.match(/"ProductID"\s*:\s*(\d+)/);
            return match ? match[1] : "N/A";
        }''')

        if not product_id:
            print("❌ 未找到 productID")
        else:
            print(f"✅ 找到 productID: {product_id}")

        # **改进品牌抓取，支持不同 HTML 结构**
        brand = await page.evaluate('''() => {
            let scriptText = [...document.scripts].map(s => s.innerText).join(" ");
            let match = scriptText.match(/"item_brand"\s*:\s*"([^"]+)"/);
            return match ? match[1] : "Brand not found";
        }''')

        if brand:
            print(f"✅ 成功提取品牌名称: {brand}")
        else:
            print("❌ 仍然未找到品牌名称")

        # **合并 `title` 和 `detail_name`**
         # **抓取产品名称**
        full_title = await page.evaluate('''() => {
            let productTitleElement = document.querySelector("h1.product-name");
            return productTitleElement ? productTitleElement.innerText.trim() : "";
        }''')
        


        # **抓取 Product Categories**
        categories = await page.evaluate('''() => {
            let scriptText = [...document.scripts].map(s => s.innerText).join(" ");
            let match = scriptText.match(/"Categories"\s*:\s*\[([^\]]+)\]/);

            if (!match) return "Categories not found";

            // 提取并解析类别
            let categoryList = match[1].replace(/"/g, '').split(',');
    
            // 用 `>` 连接成字符串
            return categoryList.join(" > ");
        }''')

        if categories:
            categories = categories.lstrip("> ").strip()


        # SKU**解析 JSON 数据并提取 SKU**
        sku = await page.evaluate('''() => {
            let scriptText = [...document.scripts].map(s => s.innerText).join(" ");
            let match = scriptText.match(/"SKU"\s*:\s*"([^"]+)"/);
            return match ? match[1] : "N/A";
        }''')
            
        # **抓取产品价格（欧元）**

        price_data = await page.evaluate('''() => {
            let currentPriceElement = document.querySelector("span[itemprop='price']");
            let originalPriceElement = document.querySelector("span.regular-price");

            let member_price = currentPriceElement ? currentPriceElement.getAttribute("content").trim() : "N/A";
            let original_price = originalPriceElement ? (originalPriceElement.innerText.match(/([\d,.]+)/) || [])[1] || "N/A" : "N/A";

            // **逻辑修正**
            if (!original_price || original_price === "N/A") {
                if (member_price) {
                    original_price = member_price;
                    member_price = "N/A";
                }
            } else if (original_price === member_price) {
                original_price = member_price;
                member_price = "N/A";
            } else if (parseFloat(original_price) < parseFloat(member_price)) {
                // 互换 original_price 和 member_price
                let temp = original_price;
                original_price = member_price;
                member_price = temp;
            }

            return { 
                "original_price": original_price , 
                "member_price": member_price 
            };
        }''')
        print("📌 原始抓取的价格数据:", price_data)  # 调试原始抓取数据

        price_dis = price_data["member_price"]
        price_old = price_data["original_price"]
        
        # **转换价格到 USD**
        try:
            # **转换 price_old（原价）**
            if price_old and price_old != "N/A":
                price_old = price_old.replace(",", ".")  # 修复 16,00 -> 16.00
                price_usd_old = f"{round(float(price_old) * exchange_rate, 2)}"
            else:
                price_usd_old = "N/A"

            # **转换 price_dis（特价）**
            if price_dis and price_dis != "N/A":
                price_dis = price_dis.replace(",", ".")  # 修复 16,00 -> 16.00
                price_usd_dis = f"{round(float(price_dis) * exchange_rate, 2)}"
            else:
                price_usd_dis = "N/A"

        except ValueError:
            price_usd_dis = "N/A"
            price_usd_old = "N/A"

        print("📌 USD价格数据:", price_usd_old)  # 调试原始抓取数据

        # **优化抓取描述**
        description = await page.evaluate("""() => {
             let section = document.querySelector("#description-collapse");
            if (!section) return "Description not found";

            let paragraphs = section.querySelectorAll("p");
            let descriptionHTML = Array.from(paragraphs)
                .map(p => `<div>${p.innerText.trim()}</div>`)
                .join("");

            return `<div class='alkemill-desc'>${descriptionHTML}</div>`;
        }""")


        # **抓取产品图片**

        images = await page.evaluate("""() => {
            let imgElement = document.querySelector("img.img-fluid.js-qv-product-cover");
            return imgElement ? imgElement.src : "Image not found";
        }""")




        review_data = await page.evaluate('''() => {
             let ratingElem = document.querySelector("p[class^='ReviewsSection-module_reviewScore__']");
            let reviewCountElem = document.querySelector("div.comments_note span");

            let rating = ratingElem ? ratingElem.textContent.trim() : "N/A";
            let review_count = reviewCountElem ? reviewCountElem.textContent.match(/\d+/)?.[0] || "N/A" : "N/A";

            return { rating, review_count };
        }''')

        rating = review_data["rating"]
        review_count = review_data["review_count"]

        variants_data = []

        variant_data = await page.evaluate("""() => {
            let variants = document.querySelectorAll("button.btn.btn-link.option-select.js-variant-select");

            // 使用 Set 来去重
            let variantSet = new Set();

            let variantArray = Array.from(variants).map(button => {
                let variant_id = button.getAttribute("data-attr-value")?.trim() || "N/A";
                let sku = button.getAttribute("data-attr-variant-id")?.trim() || "N/A";
                let color = button.getAttribute("data-attr-name")?.trim() || "N/A";

                let variantString = `${variant_id}-${sku}-${color}`; // 组合唯一 Key
                if (!variantSet.has(variantString)) {
                    variantSet.add(variantString);
                    return { "variant_id": variant_id, "sku": sku, "color": color };
                }
                return null; // 跳过重复项
            }).filter(v => v !== null); // 移除 `null` 值

            return variantArray; // 直接返回数组
        }""")

        print(variant_data)


        variants_data.append(variant_data)
        


        product_data = {
            "date": datetime.utcnow().replace(microsecond=0).isoformat(),
            "url": product_url,
            "product_id": product_id,
            "existence": existence,
            "title": full_title,
            "description": description,  # ✅ 使用 `<div>` 作为换行
            "sku": sku,
            "brand": brand,  
            "categories": categories, 
            "images": images,
            "price": price_usd_old,
            "variants": variants_data, 
            "reviews": review_count,
            "rating": rating,
            "weight": None,
            "width": None,
            "height": None,
            "length": None   
        
}

   
    # **保存为 JSON 兼容的 TXT 文件**
    # **清理文件名**
    def clean_filename(filename):
        return re.sub(r'[<>:"/\\|?*]', '', filename)  # **移除 Windows 不允许的字符**

    # **确保 product_name 没有非法字符**
    product_name = clean_filename(full_title)
    txt_file_path = os.path.join(save_path, f"{product_name}.txt")

    with open(txt_file_path, 'w', encoding='utf-8') as file:
        json.dump(product_data, file, indent=2, ensure_ascii=False)  # ✅ 取消 `ensure_ascii=True`

    print(f"✅ 产品数据已保存到 {txt_file_path}")

    await browser.close()

    
async def main():
    file_path = r'C:\Users\mark0\Desktop\program\hello\alkemillacosmetici.it\product_links.txt'
    save_path = r'C:\Users\mark0\Desktop\program\hello\alkemillacosmetici.it\product'
    os.makedirs(save_path, exist_ok=True)

    # **获取最新汇率**
    exchange_rate = get_free_exchange_rate()
    print(f"💰 当前 EUR → USD 汇率: {exchange_rate}")

    # **读取所有产品链接**
    with open(file_path, 'r', encoding='utf-8') as file:
        product_links = [line.strip() for line in file.readlines() if line.strip()]  # **过滤空行**

    for product_url in product_links:
        await scrape_product_info(product_url, save_path, exchange_rate)

# **运行爬取任务**
asyncio.get_event_loop().run_until_complete(main())
