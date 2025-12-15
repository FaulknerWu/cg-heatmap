"""
Coinglass 清算热力图 Apify Actor
使用 Playwright 截图方式获取图片
"""

from datetime import datetime
from apify import Actor
from playwright.async_api import async_playwright


async def screenshot_heatmap(
    coin: str = "BTC",
    exchange: str = "Binance",
    headless: bool = True,
    wait_timeout: int = 10000,
) -> bytes | None:
    """
    截取 Coinglass 清算热力图

    Args:
        coin: 币种，如 BTC, ETH
        exchange: 交易所，如 Binance, OKX
        headless: 是否无头模式
        wait_timeout: 等待超时时间(ms)

    Returns:
        截图二进制数据，失败返回 None
    """
    url = f"https://www.coinglass.com/pro/futures/LiquidationHeatMap?coin={coin}"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(
            viewport={"width": 2560, "height": 1440},
            device_scale_factor=2,
        )
        page = await context.new_page()

        Actor.log.info(f"正在打开页面: {url}")
        await page.goto(url, wait_until="domcontentloaded")

        # 智能等待: 等待 canvas 元素出现并渲染完成
        Actor.log.info("等待热力图 canvas 加载...")
        try:
            canvas = page.locator("canvas").first
            await canvas.wait_for(state="visible", timeout=wait_timeout)
            # 短暂等待确保 canvas 完成渲染
            await page.wait_for_timeout(500)
        except Exception as e:
            Actor.log.warning(f"等待 canvas 超时: {e}")

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
        headless = actor_input.get("headless", True)
        wait_timeout = actor_input.get("waitTimeout", 10000)

        Actor.log.info(f"开始截取 {coin} 清算热力图")

        # 执行截图
        screenshot_data = await screenshot_heatmap(
            coin=coin,
            exchange=exchange,
            headless=headless,
            wait_timeout=wait_timeout,
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
                "exchange": exchange,
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
                "error": "截图失败",
            }
            await Actor.set_value("OUTPUT", output)
            await Actor.push_data(output)
            Actor.log.error("截图失败")
