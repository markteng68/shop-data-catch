import requests

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

rate = get_free_exchange_rate()
if rate:
    print(f"✅ 当前 EUR → USD 汇率: {rate}")
