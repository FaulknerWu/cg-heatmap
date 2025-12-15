"""
Coinglass 清算热力图下载器
使用 Playwright 截图方式获取图片
"""

import asyncio
from pathlib import Path
from datetime import datetime
from playwright.async_api import async_playwright


async def screenshot_heatmap(
    coin: str = "BTC",
    output_dir: str = "downloads",
    headless: bool = False,
) -> str | None:
    """
    截取 Coinglass 清算热力图

    Args:
        coin: 币种，如 BTC, ETH
        output_dir: 保存目录
        headless: 是否无头模式

    Returns:
        截图文件路径，失败返回 None
    """
    url = f"https://www.coinglass.com/pro/futures/LiquidationHeatMap?coin={coin}"
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(
            viewport={"width": 2560, "height": 1440},
            device_scale_factor=2,  # 2x 高清
        )
        page = await context.new_page()

        print(f"正在打开页面: {url}")
        await page.goto(url, wait_until="networkidle")

        print("等待热力图加载...")
        await page.wait_for_timeout(5000)

        screenshot_path = None
        chart_selectors = [
            'canvas',
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
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = f"{coin}_heatmap_screenshot_{timestamp}.png"
                        save_path = output_path / filename
                        await element.screenshot(path=save_path)
                        screenshot_path = str(save_path)
                        print(f"截图成功: {screenshot_path} (选择器: {selector})")
                        break
            except Exception as e:
                print(f"选择器 {selector} 失败: {e}")
                continue

        if not screenshot_path:
            print("尝试截取整个图表区域...")
            try:
                # 找到包含热力图的容器
                chart_container = page.locator('div:has-text("Binance BTC/USDT") >> xpath=..').first
                if await chart_container.is_visible():
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"{coin}_heatmap_screenshot_{timestamp}.png"
                    save_path = output_path / filename
                    await chart_container.screenshot(path=save_path)
                    screenshot_path = str(save_path)
                    print(f"截图成功: {screenshot_path}")
            except Exception as e:
                print(f"截取容器失败: {e}")

        await browser.close()
        return screenshot_path


async def main():
    result = await screenshot_heatmap(
        coin="BTC",
        output_dir="downloads",
        headless=False,
    )

    if result:
        print(f"\n完成: {result}")
    else:
        print("\n截图失败")


if __name__ == "__main__":
    asyncio.run(main())
