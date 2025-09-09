import asyncio
from pyppeteer import launch
import os
import random

async def scrape_page(page_number, seen_links):
    """
    每次抓取一页后，关闭浏览器，避免 Cloudflare 触发反爬虫。
    """
    browser = await launch(headless=False, args=['--no-sandbox', '--disable-setuid-sandbox'], executablePath='C:/Program Files/Google/Chrome/Application/chrome.exe')
    page = await browser.newPage()

    # 设置 User-Agent，防止 Cloudflare 检测
    await page.setUserAgent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")

    # 伪装为真实用户
    await page.evaluateOnNewDocument('''() => {
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        window.navigator.chrome = { runtime: {} };
        Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
    }''')

    # **构造正确的 URL**
    if page_number == 1:
        url = 'https://www.notino.it/brand-cosmetici-italiani/'
    else:
        url = f'https://www.notino.it/brand-cosmetici-italiani/?f={page_number}-1-2-62760'

    print(f"📄 正在抓取第 {page_number} 页：{url}")

    await page.goto(url, {'timeout': 60000, 'waitUntil': 'domcontentloaded'})

    # **模拟滚动加载更多产品**
    for _ in range(5):
        await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
        await asyncio.sleep(random.uniform(3, 5))  # **每次滚动等待 3-5 秒**

    # **提取产品链接**
    links = await page.evaluate('''() => {
        return Array.from(document.querySelectorAll('div[data-testid="product-container"] a'))
            .map(link => link.href);
    }''')

    # **仅保留唯一的链接**
    unique_links = [link for link in links if link not in seen_links]
    seen_links.update(unique_links)  # **更新已抓取的链接集合**

    print(f"🔗 第 {page_number} 页找到 {len(links)} 个产品链接，其中 {len(unique_links)} 个是新的")

    await browser.close()  # **每次抓取完后关闭浏览器**
    return unique_links

async def main():
    total_pages = 44
    seen_links = set()  # **存储已抓取的链接**
    save_path = r'C:\Users\mark0\Desktop\program\hello'
    os.makedirs(save_path, exist_ok=True)
    file_path = os.path.join(save_path, 'product_links.txt')

    # **确保文件为空**
    open(file_path, 'w', encoding='utf-8').close()

    for page_number in range(1, total_pages + 1):
        try:
            unique_links = await scrape_page(page_number, seen_links)

            # **随机延迟，防止 Cloudflare 进一步识别**
            wait_time = random.uniform(10, 15)
            print(f"⏳ 随机等待 {wait_time:.2f} 秒，模拟人类行为...")
            await asyncio.sleep(wait_time)

            # **追加写入（不会写入重复的链接）**
            with open(file_path, 'a', encoding='utf-8') as file:
                for link in unique_links:
                    file.write(link + '\n')

        except Exception as e:
            print(f"❌ 抓取第 {page_number} 页失败: {e}")

    print(f"✅ 抓取完成，所有唯一链接已保存到 {file_path}")

# 运行脚本
asyncio.get_event_loop().run_until_complete(main())
