"""
Coinglass 清算热力图 Apify Actor
使用 Playwright 截图方式获取图片
"""

from datetime import datetime
from apify import Actor
from playwright.async_api import async_playwright

# 时间范围映射 (英文)
TIME_RANGE_MAP = {
    "12h": "12 hour",
    "24h": "24 hour",
    "48h": "48 hour",
    "3d": "3 day",
    "1w": "1 week",
    "2w": "2 week",
    "1m": "1 month",
    "3m": "3 month",
    "6m": "6 month",
    "1y": "1 Year",
}


async def screenshot_heatmap(
    coin: str = "BTC",
    exchange: str = "Binance",
    quote_currency: str = "USDT",
    time_range: str = "24h",
    headless: bool = True,
) -> bytes | None:
    """
    截取 Coinglass 清算热力图

    Args:
        coin: 币种，如 BTC, ETH
        exchange: 交易所，如 Binance, OKX
        quote_currency: 计价货币，如 USDT, USD, USDC
        time_range: 时间范围，如 12h, 24h, 48h, 3d, 1w, 2w, 1m, 3m, 6m, 1y
        headless: 是否无头模式

    Returns:
        截图二进制数据，失败返回 None
    """
    url = f"https://www.coinglass.com/pro/futures/LiquidationHeatMap?coin={coin}"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(
            viewport={"width": 2560, "height": 1440},
            device_scale_factor=2,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )
        page = await context.new_page()

        Actor.log.info(f"正在打开页面: {url}")

        # 同时发起导航和等待 API 响应
        async with page.expect_response(
            lambda r: "liqHeatMap" in r.url and r.status == 200,
            timeout=30000,
        ) as response_info:
            response = await page.goto(url, wait_until="domcontentloaded")

        # 检查页面是否正常加载
        if response and response.status >= 400:
            Actor.log.error(f"页面加载失败: HTTP {response.status}")
            await browser.close()
            return None

        # 等待 API 响应完成
        api_response = await response_info.value
        Actor.log.info(f"热力图 API 加载完成")

        # 给 canvas 渲染时间
        await page.wait_for_timeout(500)
        Actor.log.info("Canvas 已就绪")

        # 选择交易所/交易对（如果不是默认的 Binance USDT）
        if exchange != "Binance" or quote_currency != "USDT":
            # 构建交易对名称，如 "OKX BTC/USDT Perpetual"
            pair_name = f"{exchange} {coin}/{quote_currency} Perpetual"
            Actor.log.info(f"选择交易对: {pair_name}")
            try:
                # 点击交易对选择器
                pair_selector = page.get_by_role("combobox", name="Search")
                await pair_selector.click()

                # 等待下拉列表出现
                listbox = page.locator("[role='listbox']").filter(has_text="Perpetual")
                await listbox.wait_for(state="visible", timeout=3000)

                # 选择对应的交易对，同时等待新的 API 请求
                async with page.expect_response(
                    lambda r: "liqHeatMap" in r.url and r.status == 200,
                    timeout=30000,
                ) as response_info:
                    option = listbox.get_by_role("option", name=pair_name)
                    await option.click()

                await response_info.value
                Actor.log.info(f"已选择: {pair_name}，数据加载完成")
                await page.wait_for_timeout(500)
            except Exception as e:
                Actor.log.warning(f"选择交易对失败: {e}，使用默认 Binance BTC/USDT")

        # 选择时间范围（如果不是默认的 24h）
        time_label = TIME_RANGE_MAP.get(time_range)
        if time_label is None:
            Actor.log.warning(f"无效的时间范围 '{time_range}'，使用默认值 24h")
            time_label = "24 hour"
            time_range = "24h"

        if time_range != "24h":
            Actor.log.info(f"选择时间范围: {time_label}")
            try:
                # 点击时间选择器 combobox（包含 hour 文本的那个）
                time_selector = page.locator("[role='combobox']").filter(has_text="hour")
                await time_selector.click()

                # 等待时间选项下拉列表出现（包含 "12 hour" 的那个 listbox）
                listbox = page.locator("[role='listbox']").filter(has_text="12 hour")
                await listbox.wait_for(state="visible", timeout=3000)

                # 选择对应的时间选项，同时等待新的 API 请求
                async with page.expect_response(
                    lambda r: "liqHeatMap" in r.url and r.status == 200,
                    timeout=30000,
                ) as response_info:
                    time_option = listbox.get_by_role("option", name=time_label)
                    await time_option.click()

                # 等待新数据加载完成
                await response_info.value
                Actor.log.info(f"已选择: {time_label}，数据加载完成")

                # 给 canvas 渲染时间
                await page.wait_for_timeout(500)
            except Exception as e:
                Actor.log.warning(f"选择时间范围失败: {e}")

        screenshot_data = None

        # 截取 canvas 元素
        try:
            canvas = page.locator("canvas").first
            if await canvas.is_visible():
                box = await canvas.bounding_box()
                if box and box["width"] > 500 and box["height"] > 300:
                    screenshot_data = await canvas.screenshot()
                    Actor.log.info(f"截图成功: {box['width']:.0f}x{box['height']:.0f}")
        except Exception as e:
            Actor.log.error(f"截取 canvas 失败: {e}")

        # 备用: 截取整个图表区域
        if not screenshot_data:
            Actor.log.info("尝试截取整个图表区域...")
            try:
                container = page.locator(f'div:has-text("{exchange}") >> xpath=ancestor::div[contains(@class, "chart") or contains(@class, "heatmap")]').first
                if await container.is_visible(timeout=2000):
                    screenshot_data = await container.screenshot()
                    Actor.log.info("截图成功 (容器)")
            except Exception as e:
                Actor.log.error(f"截取容器失败: {e}")

        await browser.close()
        return screenshot_data


async def main() -> None:
    async with Actor:
        # 获取输入参数
        actor_input = await Actor.get_input() or {}
        coin = actor_input.get("coin", "BTC")
        exchange = actor_input.get("exchange", "Binance")
        quote_currency = actor_input.get("quoteCurrency", "USDT")
        time_range = actor_input.get("timeRange", "24h")
        headless = actor_input.get("headless", True)

        Actor.log.info(f"开始截取 {exchange} {coin}/{quote_currency} 清算热力图 (时间范围: {time_range})")

        # 执行截图
        screenshot_data = await screenshot_heatmap(
            coin=coin,
            exchange=exchange,
            quote_currency=quote_currency,
            time_range=time_range,
            headless=headless,
        )

        if screenshot_data:
            # 保存到 Key-Value Store
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{exchange}_{coin}{quote_currency}_{time_range}_{timestamp}.png"

            await Actor.set_value(
                key=filename,
                value=screenshot_data,
                content_type="image/png",
            )

            # 获取公开 URL
            kvs = await Actor.open_key_value_store()
            public_url = await kvs.get_public_url(filename)

            # 输出结果
            output = {
                "success": True,
                "coin": coin,
                "exchange": exchange,
                "quoteCurrency": quote_currency,
                "timeRange": time_range,
                "filename": filename,
                "url": public_url,
                "timestamp": timestamp,
            }
            await Actor.set_value("OUTPUT", output)
            await Actor.push_data(output)
            Actor.log.info(f"完成: {public_url}")
        else:
            output = {
                "success": False,
                "coin": coin,
                "exchange": exchange,
                "quoteCurrency": quote_currency,
                "timeRange": time_range,
                "error": "截图失败",
            }
            await Actor.set_value("OUTPUT", output)
            await Actor.push_data(output)
            Actor.log.error("截图失败")
