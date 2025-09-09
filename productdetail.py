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
            const productIdElement = document.querySelector('input[name="id"]');
        return productIdElement ? productIdElement.value.trim() : "";
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
            let productTitleElement = document.querySelector('.product__title__wrapper');
    return productTitleElement ? productTitleElement.innerText.trim() : "";
        }''')
        
        # **抓取 Product Categories**
        categories = await page.evaluate('''() => {
           // 抓取 breadcrumb 中的所有連結文字
        let breadcrumbElements = document.querySelectorAll('div.breadcrumb a');
        let categories = Array.from(breadcrumbElements)
            .map(el => el.textContent.trim())
            .filter(text => text.length > 0);

        // 移除首頁 (第一項) 和商品名稱 (最後一項)
        if (categories.length > 2) {
            categories = categories.slice(1, -1); // 保留中間的分類
        } else if (categories.length === 2) {
            categories = [categories[1]]; // 若只有首頁和分類，取分類
        } else {
            categories = categories; // 沒有多餘的層級時直接返回
        }

        return categories.join(' > '); // 使用 ' > ' 分隔多層分類
        }''')

        if categories:
            categories = categories.lstrip("> ").strip()


        # SKU**解析 JSON 数据并提取 SKU**
        sku = await page.evaluate('''() => {
                const scriptTag = Array.from(document.querySelectorAll('script')).find(el =>
            el.textContent.includes('"sku"')
        );
        if (scriptTag) {
            let cleanedText = scriptTag.textContent.replace(/^.*?=\\s*/, '').trim();
            cleanedText = cleanedText.replace(/;$/, '');  // 移除結尾的分號
            try {
                // ⚡ 使用 eval 解析非標準 JSON（僅適用於受信任來源）
                const jsonData = eval('(' + cleanedText + ')');
                return jsonData.variants ? jsonData.variants[0].sku : "";
            } catch (error) {
                console.error("JSON 解析錯誤:", error);
                return "";
            }
        }
        return "";
            }''')
            
        # **抓取产品价格（欧元）**

        price_data = await page.evaluate('''() => {
            // 🔍 抓取指定價格元素
        let currentPriceElement = document.querySelector("span.product_price--sale");
        let originalPriceElement = document.querySelector("span.compare-at");

        // ✅ 預設價格 (如果元素不存在)
        let member_price = currentPriceElement ? currentPriceElement.innerText.trim() : "N/A";
        let original_price = originalPriceElement ? originalPriceElement.innerText.trim() : "N/A";

        // 🔄 僅保留數字與小數點 (將逗號轉為小數點)
        member_price = member_price.replace(/[^\\d,\\.]/g, "").replace(",", ".");
        original_price = original_price.replace(/[^\\d,\\.]/g, "").replace(",", ".");

        // 💡 補救機制：當 original_price 為空或 N/A
        if (!original_price || original_price === "N/A") {
            if (member_price !== "N/A") {
                original_price = member_price;
                member_price = "N/A";
            }
        } 
        // 💡 當價格相同時，清除會員價格
        else if (original_price === member_price) {
            member_price = "N/A";
        } 
        // 💡 若原始價格低於會員價格則互換
        else if (parseFloat(original_price) < parseFloat(member_price)) {
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
        await asyncio.sleep(5)  # ⏳ 等待頁面渲染
        # **优化抓取描述**
        description = await page.evaluate("""() => {
            const wrapper = document.querySelector('div.tabs-wrapper');
                if (wrapper) {
                    const descriptions = Array.from(wrapper.querySelectorAll('div.accordion__body, div.accordion-content__entry'))
                        .map(el => `<div>${el.innerText.trim()}</div>`)
                        .filter(text => text.length > 0)
                        .join('');
                    return `<div class='blondesister-desc'>${descriptions}</div>`;
                }
                return "<div class='blondesister-desc'>描述不存在</div>";
        }""")
        # 1. 移除 HTML 註解
        description = re.sub(r'<!--.*?-->', '', description, flags=re.DOTALL)

        # 2. 移除多餘的空白字元
        description = re.sub(r'\s+', ' ', description).strip()



        # **抓取產品圖片 (增強版過濾條件)**
        images = await page.evaluate('''() => {
    let images = [];
    let productGrid = document.querySelector('div.product__grid.product__grid--mosaic.flickity-lock-height');

    if (productGrid) {
        // ✅ 1️⃣ 抓取 <img> 的 `src` 和 `srcset`
        let imgElements = Array.from(productGrid.querySelectorAll('img'));
        imgElements.forEach(img => {
            if (img.src) images.push(img.src);
            if (img.srcset) {
                let srcsetUrls = img.srcset.split(',').map(s => s.trim().split(' ')[0]);
                images.push(...srcsetUrls);
            }
        });

        // ✅ 2️⃣ 抓取 `data-media-src-placeholder`
        let placeholderElements = Array.from(productGrid.querySelectorAll('div[data-media-src-placeholder]'));
        placeholderElements.forEach(div => {
            let url = div.getAttribute('data-media-src-placeholder');
            if (url) images.push(url);
        });

        // ✅ 3️⃣ 抓取 `data-src`（某些 lazyload 圖片）
        let lazyloadElements = Array.from(productGrid.querySelectorAll('[data-src]'));
        lazyloadElements.forEach(el => {
            let url = el.getAttribute('data-src');
            if (url) images.push(url);
        });
    }

    // 🔍 過濾不相關圖片
    images = images
        .filter(url => url !== null)
        .map(url => url.startsWith('http') ? url : `https:${url}`)  // 確保補全 https
        .filter(url => 
            !url.includes("data:image") &&  // 去除 Base64 圖片
            !url.includes("_1x1.png") &&  // 去除 1x1 佔位符圖片
            !url.includes("_crop_center") &&  // 去除縮略圖
            !url.includes("placeholder") &&  // 避免抓到 `data-placeholder`
            !url.match(/width=(9[0-9]|1[0-4][0-9]|180|280|352|400|420|768)/)  // 去除小尺寸圖片
        );

    // 🏆 保留每張圖片的最高解析度
    let uniqueImages = {};
    images.forEach(url => {
        let baseUrl = url.split('?')[0];  // 移除 URL 參數部分
        let widthMatch = url.match(/width=(\d+)/);
        let width = widthMatch ? parseInt(widthMatch[1], 10) : 0;

        if (!uniqueImages[baseUrl] || uniqueImages[baseUrl] < width) {
            uniqueImages[baseUrl] = width;
        }
    });

    // 只保留最大尺寸的圖片
    return Object.keys(uniqueImages).map(baseUrl => `${baseUrl}?width=${uniqueImages[baseUrl]}`).join("; ");
}''')

        
        review_data = await page.evaluate('''() => {
          let review = null;
    let reviewCount = null;

    // 🔍 抓取評分（Review Rating）
    let reviewElement = document.querySelector('span[data-testid="rating-summary-avg"]');
    if (reviewElement) {
        review = reviewElement.getAttribute('aria-label').trim();
    }

    // 🔍 抓取評論數（Review Count）
    let reviewCountElement = document.querySelector('div[data-testid="rating-summary-count"]');
    if (reviewCountElement) {
        reviewCount = reviewCountElement.innerText.replace(/\D/g, "").trim();  // 移除非數字字符
    }

    return {  review,  reviewCount };
    
        }''')

        rating = review_data["review"]
        review_count = review_data["reviewCount"]

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
    file_path = r'C:\Users\mark0\Desktop\program\hello\blondesister\product_links.txt'
    save_path = r'C:\Users\mark0\Desktop\program\hello\blondesister\product'
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
