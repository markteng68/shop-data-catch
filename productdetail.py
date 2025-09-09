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
    url = "https://api.exchangerate-api.com/v4/latest/USD"
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
            let productIdElement = document.querySelector('input[name="product-id"]');
    return productIdElement ? productIdElement.value : "";
        }''')

        if not product_id:
            print("❌ 未找到 productID")
        else:
            print(f"✅ 找到 productID: {product_id}")

        # **改进品牌抓取，支持不同 HTML 结构**
        brand = await page.evaluate('''() => {
            let scriptText = [...document.scripts].map(s => s.innerText).join(" ");
            let match = scriptText.match(/"item_brand"\s*:\s*"([^"]+)"/);
            return match ? match[1] : "N/A";
        }''')

        if brand:
            print(f"✅ 成功提取品牌名称: {brand}")
        else:
            print("❌ 仍然未找到品牌名称")

        # **合并 `title` 和 `detail_name`**
         # **抓取产品名称**
        full_title = await page.evaluate('''() => {
            let productTitleElement = document.querySelector('h1.product-meta__title.heading.h3');
            return productTitleElement ? productTitleElement.innerText.trim() : "";
        }''')
        
        # **抓取 Product Categories**
        categories = await page.evaluate('''() => {
            let breadcrumbElement = document.querySelector("nav.woocommerce-breadcrumb");
    if (breadcrumbElement) {
        // 提取所有 <a> 標籤的文字作為路徑節點
        let paths = Array.from(breadcrumbElement.querySelectorAll("a"))
            .map(a => a.innerText.trim())
            .filter(text => text && text.toLowerCase() !== "home");  // 過濾掉 'Home'

        // 提取商品名稱後面的純文字 (最後的商品名稱會是 innerText 中最後的字串)
        let fullText = breadcrumbElement.innerText.trim();
        let productName = paths.length > 0 ? fullText.split(paths[paths.length - 1])[1]?.trim() : "";
        
        // 過濾掉商品名稱
        if (productName) {
            fullText = fullText.replace(productName, "").trim();
        }

        // 最終組合為 "分類1 > 分類2"
        return paths.join(" > ");
    }
    return "";
        }''')

        if categories:
            categories = categories.lstrip("> ").strip()


        # SKU**解析 JSON 数据并提取 SKU**
        sku = await page.evaluate('''() => {
            let meta = document.querySelector("span.sku");  // 使用正確的 class 選擇器
            return meta ? meta.innerText.trim() : "";       // 取得 SKU 文字內容
        }''')
            
        # **抓取产品价格（欧元）**

        price_data = await page.evaluate('''() => {
            let currentPriceElement = document.querySelector("span.price--highlight");
    let originalPriceElement = document.querySelector("span.price--compare");

    let member_price = currentPriceElement ? currentPriceElement.innerText.trim() : "N/A";
    let original_price = originalPriceElement ? originalPriceElement.innerText.trim() : "N/A";

    // ✅ 处理价格格式，去除非數字字符（如 $、€）
    member_price = member_price.replace(/[^\d,\\.]/g, "").replace(",", ".");
    original_price = original_price.replace(/[^\d,\\.]/g, "").replace(",", ".");

    // ✅ 價格邏輯修正
    if (!original_price || original_price === "N/A") {
        if (member_price) {
            original_price = member_price;
            member_price = "N/A";
        }
    } else if (original_price === member_price) {
        original_price = member_price;
        member_price = "N/A";
    } else if (parseFloat(original_price) < parseFloat(member_price)) {
        // 🔄 若原始價格小於會員價格則互換
        let temp = original_price;
        original_price = member_price;
        member_price = temp;
    }

    return { 
        "original_price": original_price, 
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
        description = await page.evaluate("""
            () => {
                let descriptionElement = document.querySelector('div.product-form__description.rte');
    if (!descriptionElement) return "<div class='beemea-desc'></div>";

    // 將每個子元素（如 <p>、<li>）包裝到 <div> 中
    let paragraphs = Array.from(descriptionElement.children).map(child => {
        return `<div>${child.innerText.trim()}</div>`;
    }).join("");

    // 使用外層 div 包裹所有內容
    return `<div class='beemea-desc'>${paragraphs}</div>`;
            }
        """)


        # **抓取產品圖片 (增強版過濾條件)**
        images = await page.evaluate("""() => {
            const baseUrl = "https:/";
            const images = document.querySelectorAll('div.product_media-item img, div.flickity-slider img');
    const imageMap = new Map(); // 使用 Map 儲存圖片並依檔名篩選最大解析度

    const processUrl = (url) => {
        // ✅ 先補全主域名並修正路徑
        url = url.startsWith("http") ? url : `${baseUrl}${url.replace(/^\\/+/, '')}`;

        // 🚫 補全後再檢查並刪除格式錯誤的網址 (https:/beemea.com，但缺少 //)
        if (url.startsWith("https:/beemea.com") && !url.startsWith("https://beemea.com")) {
            return;
        }

        // 從 URL 中擷取不含解析度的基本檔名以作為 Key
        const baseName = url.replace(/_\\d+x\\..+$/, ''); 
        const sizeMatch = url.match(/_(\\d+)x/);
        const size = sizeMatch ? parseInt(sizeMatch[1], 10) : 0;

        // 若該圖片已存在，則比較解析度並保留解析度較大者
        if (!imageMap.has(baseName) || imageMap.get(baseName).size < size) {
            imageMap.set(baseName, { url, size });
        }
    };

    Array.from(images).forEach(img => {
        // 處理 srcset (多解析度圖片)
        if (img.srcset) {
            img.srcset.split(',').forEach(item => {
                const [url] = item.trim().split(' ');
                processUrl(url);
            });
        }

        // 如果沒有 srcset，則使用 src
        if (img.src) {
            processUrl(img.src);
        }
    });
                                     
                                     

    // 從 Map 中提取唯一且解析度最高的圖片網址
    return Array.from(imageMap.values()).map(item => item.url).join(";");
}""")

        await asyncio.sleep(5)  # ⏳ 等待頁面渲染
        review_data = await page.evaluate('''() => {
          // ✅ 正確匹配評分元素（包括 aria-label 容錯處理）
            let ratingElement = document.querySelector("div.jdgm-rev-widg__summary-inner");
            let ratingText = ratingElement ? ratingElement.getAttribute("aria-label") : null;

            // ✅ 若 aria-label 為空則嘗試從文字節點中提取
            if (!ratingText && ratingElement) {
                ratingText = ratingElement.innerText.trim();
            }

            // ✅ 評論數提取
            let countElement = document.querySelector("div.jdgm-rev-widg__summary-text");
            let ratingCount = countElement ? countElement.innerText.trim() : "0";

            // ✅ 提取評分中的數值（支援 "5.00 su 5" 或 "Average rating is 5.00 stars"）
            const ratingMatch = ratingText ? ratingText.match(/(\\d+\\.\\d+|\\d+)/) : null;
            const rating = ratingMatch ? ratingMatch[0] : "0";

            // ✅ 從評論文字中提取評論數量（如 "Basato su 10 recensioni" 提取 "10"）
            const ratingCountMatch = ratingCount.match(/\\d+/);
            ratingCount = ratingCountMatch ? ratingCountMatch[0] : "0";

            return { 
                rating, 
                ratingCount 
            };
    
        }''')

        rating = review_data["rating"]
        review_count = review_data["ratingCount"]

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
    file_path = r'C:\Users\mark0\Desktop\program\hello\beemea\product_links.txt'
    save_path = r'C:\Users\mark0\Desktop\program\hello\beemea\product'
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
