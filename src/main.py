"""
Coinglass 清算热力图 Apify Actor
使用 Playwright 截图方式获取图片
"""

from datetime import datetime
from apify import Actor
from playwright.async_api import async_playwright


async def screenshot_heatmap(
    coin: str = "BTC",
    headless: bool = True,
) -> bytes | None:
    """
    截取 Coinglass 清算热力图

    Args:
        coin: 币种，如 BTC, ETH
        headless: 是否无头模式

    Returns:
        截图二进制数据，失败返回 None
    """
    url = f"https://www.coinglass.com/pro/futures/LiquidationHeatMap?coin={coin}"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(
            viewport={"width": 2560, "height": 1440},
            device_scale_factor=2,  # 2x 高清
        )
        page = await context.new_page()

        Actor.log.info(f"正在打开页面: {url}")
        await page.goto(url, wait_until="networkidle")

        Actor.log.info("等待热力图加载...")
        await page.wait_for_timeout(5000)

        # 尝试定位热力图 canvas 元素
        screenshot_data = None

        # 可能的图表容器选择器
        chart_selectors = [
            'canvas',  # 热力图通常是 canvas
            '[class*="chart"]',
            '[class*="heatmap"]',
            'div:has(canvas)',
        ]

        for selector in chart_selectors:
            try:
                element = page.locator(selector).first
                if await element.is_visible(timeout=2000):
                    box = await element.bounding_box()
                    if box and box['width'] > 500 and box['height'] > 300:
                        screenshot_data = await element.screenshot()
                        Actor.log.info(f"截图成功 (选择器: {selector})")
                        break
            except Exception as e:
                Actor.log.debug(f"选择器 {selector} 失败: {e}")
                continue

        # 如果没找到合适的元素，截取整个图表区域
        if not screenshot_data:
            Actor.log.info("尝试截取整个图表区域...")
            try:
                chart_container = page.locator('div:has-text("Binance BTC/USDT") >> xpath=..').first
                if await chart_container.is_visible():
                    screenshot_data = await chart_container.screenshot()
                    Actor.log.info("截图成功")
            except Exception as e:
                Actor.log.error(f"截取容器失败: {e}")

        await browser.close()
        return screenshot_data


async def main() -> None:
    async with Actor:
        # 获取输入参数
        actor_input = await Actor.get_input() or {}
        coin = actor_input.get("coin", "BTC")
        headless = actor_input.get("headless", True)

        Actor.log.info(f"开始截取 {coin} 清算热力图")

        # 执行截图
        screenshot_data = await screenshot_heatmap(
            coin=coin,
            headless=headless,
        )

        if screenshot_data:
            # 保存到 Key-Value Store
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{coin}_heatmap_{timestamp}.png"

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
                "filename": filename,
                "url": public_url,
                "timestamp": timestamp,
            }
            await Actor.set_value("OUTPUT", output)
            Actor.log.info(f"完成: {public_url}")
        else:
            output = {
                "success": False,
                "coin": coin,
                "error": "截图失败",
            }
            await Actor.set_value("OUTPUT", output)
            Actor.log.error("截图失败")
