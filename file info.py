import asyncio
import os
import requests
from pyppeteer import launch
from datetime import datetime
import json

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
    existence = True
    try:
        await page.waitForSelector('h1', {'timeout': 5000})  # 确保标题存在
    except:
        existence = False

    if not existence:
        print(f"❌ 产品已下架或页面无效: {product_url}")
        product_data = {
            "date": datetime.utcnow().isoformat() + "Z",
            "url": product_url,
            "existence": False,
            "product_id": "N/A",
            "title": "产品已下架",
            "detail_name": "N/A",
            "brand": "N/A",
            "sku": "N/A",
            "categories": "N/A",
            "description": "N/A",
            "price_eur": "N/A",
            "price_usd": "N/A",
            "weight": "N/A",
            "width": "N/A",
            "height": "N/A",
            "length": "N/A",
            "images": "N/A"
        }
    else:
        # **抓取 productId**
        product_id = await page.evaluate('''() => {
            let input = document.querySelector('input[name="productId"]');
            return input ? input.value : null;
        }''')

        # **抓取品牌名**
        brand = await page.evaluate('''() => {
            let brandElem = document.querySelector('a.sc-3sotvb-2');
            return brandElem ? brandElem.innerText : null;
        }''')

        # **抓取详细名称**
        detail_name = await page.evaluate('''() => {
            let detailElem = document.querySelector('span.sc-3sotvb-5');
            return detailElem ? detailElem.innerText : null;
        }''')

        # **合并 `title` 和 `detail_name`**
         # **抓取产品名称**
        title = await page.evaluate('''() => {
            let titleElem = document.querySelector('span.sc-3sotvb-4');
            return titleElem ? titleElem.innerText : null;
        }''')

        # **抓取详细名称**
        detail_name = await page.evaluate('''() => {
            let detailElem = document.querySelector('span.sc-3sotvb-5');
            return detailElem ? detailElem.innerText : null;
        }''')

        full_title = f"{title} {detail_name}".strip() if detail_name else title

        # **抓取 Product Categories**
        categories = await page.evaluate('''() => {
            let breadcrumbContainer = document.querySelector('div[data-testid="breadcrumb-wrapper"]');
            if (!breadcrumbContainer) return null;

            let categoryElems = Array.from(breadcrumbContainer.querySelectorAll('a'));
            return categoryElems.map(el => el.innerText.trim()).join(" > ");
        }''')
        if categories:
            categories = categories.lstrip("> ").strip()


        # **解析 JSON 数据并提取 SKU**
        sku = await page.evaluate('''() => {
            let scriptElems = Array.from(document.querySelectorAll("script"));
            for (let scriptElem of scriptElems) {
                if (scriptElem.innerText.includes('"sku"')) {
                    try {
                        let jsonText = scriptElem.innerText.trim();
                        jsonText = jsonText.substring(jsonText.indexOf('{'), jsonText.lastIndexOf('}') + 1);
                        let jsonData = JSON.parse(jsonText);
                        return jsonData.sku || null;
                    } catch (error) {
                        return null;
                    }
                }
            }
            return null;
        }''')
        # **抓取产品价格（欧元）**
        price_eur = await page.evaluate('''() => {
            let priceElem = document.querySelector('[data-testid="pd-price"]');
            return priceElem ? priceElem.innerText.replace("€", "").trim() : null;
        }''')

        # **转换价格到 USD**
        if price_eur and exchange_rate:
            try:
                price_eur = price_eur.replace(",", ".")  # **修复 16,00 -> 16.00**
                price_usd = f"{round(float(price_eur) * exchange_rate, 2)}"
            except ValueError:
                price_usd = "N/A"
        else:
            price_usd = "N/A"

        # **优化抓取描述**
        description = await page.evaluate('''() => {
          let sections = [];

         // **抓取主要描述**
         let descElem = document.querySelector('#pd-description-text');
         if (descElem) {
                let currentTitle = "";
                descElem.childNodes.forEach(node => {
                    if (node.tagName === "H3" || node.tagName === "H2") {
                        currentTitle = node.innerText.trim();
                        sections.push(`<div>${currentTitle}:</div>`);
                    } else if (node.tagName === "P") {
                        sections.push(`<div>${node.innerText}</div>`);
                    } else if (node.tagName === "UL") {
                        let list_items = Array.from(node.querySelectorAll("li")).map(li => `<div>> ${li.innerText}</div>`);
                        sections.push(...list_items);
                    }
                });
            }

            // **抓取成分信息（完整）**
            let compositionWrapper = document.querySelector('#pd-composition-wrapper');
            if (compositionWrapper) {
                let compositionText = Array.from(compositionWrapper.querySelectorAll("p, div, span"))
                    .map(el => el.innerText.trim())
                    .filter(text => text.length > 0)
                           .join("<div></div>");  // ✅ `<div></div>` 保持分段结构
                if (compositionText.length > 0) {
                    sections.push(`<div>Composizione:</div><div>${compositionText}</div>`);
                }
            }

            // **抓取品牌介绍**
            let brandElem = document.querySelector('#pdAboutBrand p');
            if (brandElem && brandElem.innerText.trim().length > 0) {
                sections.push(`<div>Informazioni sul marchio:</div><div>${brandElem.innerText.trim()}</div>`);
            }

            // **抓取 Notino 标准描述（HTML 结构）**
            let notinoDesc = document.querySelector('div.notino-desc');
            if (notinoDesc) {
                sections.push(notinoDesc.innerHTML.trim());
            }

            // **组合最终描述，并包裹 `<div class="notino-desc">`**
            return sections.length > 0 ? '<div class="notino-desc">' + sections.join("") + '</div>' : "N/A";
        }''')
        

        # **Python 处理部分：移除 `\`**
        if description and description != "N/A":
            description = description.replace('\\"', '"')  # **去除转义符**


        # **抓取产品图片**
        images = await page.evaluate('''() => {
            let gallery = document.querySelector('#pdImageGallery');
            let slider_images = document.querySelectorAll('img[data-testid="slider-image"]');

            let imgUrls = [];

            if (gallery) {
                let imgElems = Array.from(gallery.querySelectorAll('img'));
                imgUrls = imgElems.map(img => img.src).filter(url => url && url.startsWith("http"));
            }

            if (slider_images.length > 0) {
                let sliderImgs = Array.from(slider_images).map(img => img.src).filter(url => url && url.startsWith("http"));
                imgUrls = imgUrls.concat(sliderImgs);
            }

            return [...new Set(imgUrls)];  // **去重**
        }''')

       # **格式化图片列表**
        if images:
          images_str = ";".join(images)  # **多张图片用 `:` 连接**
        else:
            images_str = "N/A"

        product_data = {
            "date": datetime.utcnow().replace(microsecond=0).isoformat(),
            "url": product_url,
            "product_id": product_id,
            "existence": existence,
            "full_title": full_title,
            "brand": brand,
            "sku": sku,
            "categories": categories,
            "description": description,  # ✅ 使用 `<div>` 作为换行
            "price_eur": price_eur,
            "price_usd": price_usd,
            "weight": None,
            "width": None,
            "height": None,
            "length": None,
            "images": images_str
}

   
    # **保存为 JSON 兼容的 TXT 文件**
    product_name = product_url.split("/")[-2] if "/" in product_url else "unknown"
    txt_file_path = os.path.join(save_path, f"{product_name}.txt")

    with open(txt_file_path, 'w', encoding='utf-8') as file:
        json.dump(product_data, file, indent=2, ensure_ascii=False)  # ✅ 取消 `ensure_ascii=True`

    print(f"✅ 产品数据已保存到 {txt_file_path}")

    await browser.close()

    
async def main():
    file_path = r'C:\Users\mark0\Desktop\program\hello\product_links.txt'
    save_path = r'C:\Users\mark0\Desktop\program\hello\product_details'
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
