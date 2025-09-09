import asyncio
from pyppeteer import launch
import os

# **基本设置**
BASE_URL = "https://www.alkemillacosmetici.it/en/"
CATEGORY_URLS = [
    "15-hair",
    "11-body",
    "5-face",
    "17-makeup",
    "104-men",
    "9-baby",
    "13-sun-care"
]

SAVE_PATH = r'C:\Users\mark0\Desktop\program\hello\alkemillacosmetici.it'
os.makedirs(SAVE_PATH, exist_ok=True)

PRODUCT_FILE = os.path.join(SAVE_PATH, 'product_links.txt')

async def fetch_product_links():
    browser = await launch(
        headless=False,
        args=['--no-sandbox', '--disable-setuid-sandbox'],
        executablePath='C:/Program Files/Google/Chrome/Application/chrome.exe'
    )
    page = await browser.newPage()
    await page.setViewport({"width": 1280, "height": 800})  # 模拟正常窗口

    all_product_links = set()

    for category in CATEGORY_URLS:
        page_number = 1  # 每个分类的分页
        while True:
            category_url = f"{BASE_URL}{category}?page={page_number}"
            print(f"📌 抓取分类页面: {category_url}")
            await page.goto(category_url, {"waitUntil": "domcontentloaded"})  # 页面加载

            # **检查是否有产品**
            try:
                await page.waitForSelector("a.product-title", {"timeout": 5000})
            except:
                print(f"⚠️ 第 {page_number} 页没有产品，停止爬取 {category} 分类。")
                break

            # **抓取产品链接**
            product_links = await page.evaluate("""() => {
                return Array.from(document.querySelectorAll("a.product-title"))
                    .map(el => el.getAttribute("href"));
            }""")

            # **补全网址**
            full_links = {link for link in product_links if link}

            # **检测是否有新链接**
            if not full_links - all_product_links:
                print(f"✅ 第 {page_number} 页没有新的链接，结束 {category} 分类的爬取。")
                break

            all_product_links.update(full_links)
            page_number += 1  # 进入下一页

    # **写入 product_links.txt**
    with open(PRODUCT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(all_product_links)))

    print(f"✅ 抓取完成，共获取 {len(all_product_links)} 个产品链接，已保存到 {PRODUCT_FILE}")
    await browser.close()

# **执行爬虫**
asyncio.run(fetch_product_links())
