"""
Coinglass 清算热力图 Apify Actor
使用 Playwright 截图方式获取图片
"""

import re
import time
from collections.abc import Awaitable, Callable
from datetime import datetime

from apify import Actor
from playwright.async_api import Page, Response, async_playwright

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

HEATMAP_API_KEYWORD = "liqHeatMap"
API_TIMEOUT_MS = 30000
LISTBOX_TIMEOUT_MS = 3000


def is_heatmap_response(response: Response) -> bool:
    return HEATMAP_API_KEYWORD in response.url and response.status == 200


async def wait_for_canvas_ready(page: Page, timeout: int = 10000, check_interval: int = 200) -> bool:
    """
    Wait for canvas rendering to complete by checking pixel fill ratio stability.

    Args:
        page: Playwright page object
        timeout: Maximum wait time in milliseconds
        check_interval: Time between checks in milliseconds

    Returns:
        True if canvas is ready, False if timeout
    """
    start_time = time.time()
    last_fill_ratio = -1
    stable_count = 0

    while (time.time() - start_time) * 1000 < timeout:
        try:
            result = await page.evaluate(
                """() => {
                const canvas = document.querySelector('canvas');
                if (!canvas || !canvas.offsetParent) return { ready: false, ratio: 0 };
                const ctx = canvas.getContext('2d');
                if (!ctx) return { ready: false, ratio: 0 };
                const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
                let nonTransparent = 0;
                for (let i = 3; i < imageData.data.length; i += 4) {
                    if (imageData.data[i] > 0) nonTransparent++;
                }
                const ratio = nonTransparent / (canvas.width * canvas.height);
                return { ready: true, ratio: Math.round(ratio * 1000) / 1000 };
            }"""
            )

            if result["ready"] and result["ratio"] > 0.1:
                if abs(result["ratio"] - last_fill_ratio) < 0.01:
                    stable_count += 1
                    if stable_count >= 2:
                        return True
                else:
                    stable_count = 0
                last_fill_ratio = result["ratio"]
        except Exception:
            pass

        await page.wait_for_timeout(check_interval)

    return False


async def wait_for_heatmap_update(page: Page, action: Callable[[], Awaitable[None]]) -> None:
    async with page.expect_response(is_heatmap_response, timeout=API_TIMEOUT_MS) as response_info:
        await action()
    await response_info.value


async def wait_canvas_or_warn(page: Page, timeout_message: str, success_message: str | None = None) -> None:
    if await wait_for_canvas_ready(page):
        if success_message:
            Actor.log.info(success_message)
    else:
        Actor.log.warning(timeout_message)


def get_time_label(time_range: str) -> tuple[str, str]:
    time_label = TIME_RANGE_MAP.get(time_range)
    if time_label:
        return time_range, time_label

    Actor.log.warning(f"无效的时间范围 '{time_range}'，使用默认值 24h")
    return "24h", "24 hour"


async def open_heatmap_page(page: Page, url: str) -> bool:
    async with page.expect_response(is_heatmap_response, timeout=API_TIMEOUT_MS) as response_info:
        response = await page.goto(url, wait_until="domcontentloaded")

    if response and response.status >= 400:
        Actor.log.error(f"页面加载失败: HTTP {response.status}")
        return False

    await response_info.value
    Actor.log.info("热力图 API 加载完成")
    await wait_canvas_or_warn(page, "等待 Canvas 渲染超时，继续尝试截图", success_message="Canvas 已就绪")
    return True


async def select_pair(page: Page, coin: str, exchange: str, quote_currency: str) -> None:
    if exchange == "Binance" and quote_currency == "USDT":
        return

    pair_name = f"{exchange} {coin}/{quote_currency} Perpetual"
    Actor.log.info(f"选择交易对: {pair_name}")

    try:
        pair_selector = page.get_by_role("combobox", name="Search")
        await pair_selector.click()

        listbox = page.locator("[role='listbox']").filter(has_text="Perpetual")
        await listbox.wait_for(state="visible", timeout=LISTBOX_TIMEOUT_MS)

        option = listbox.get_by_role("option", name=pair_name)
        await wait_for_heatmap_update(page, option.click)

        Actor.log.info(f"已选择: {pair_name}，数据加载完成")
        await wait_canvas_or_warn(page, "等待 Canvas 更新超时，继续尝试截图")
    except Exception as e:
        Actor.log.warning(f"选择交易对失败: {e}，使用默认 Binance BTC/USDT")


async def select_time_range(page: Page, time_range: str) -> str:
    time_range, time_label = get_time_label(time_range)
    if time_range == "24h":
        return time_range

    Actor.log.info(f"选择时间范围: {time_label}")

    try:
        time_selector = page.locator("[role='combobox']").filter(
            has_text=re.compile(r"(hour|day|week|month|year)", re.IGNORECASE)
        )
        await time_selector.click()

        listbox = page.locator("[role='listbox']").filter(has_text="12 hour")
        await listbox.wait_for(state="visible", timeout=LISTBOX_TIMEOUT_MS)

        time_option = listbox.get_by_role("option", name=time_label)
        await wait_for_heatmap_update(page, time_option.click)

        Actor.log.info(f"已选择: {time_label}，数据加载完成")
        await wait_canvas_or_warn(page, "等待 Canvas 更新超时，继续尝试截图")
    except Exception as e:
        Actor.log.warning(f"选择时间范围失败: {e}")

    return time_range


async def capture_canvas_screenshot(page: Page) -> bytes | None:
    try:
        canvas = page.locator("canvas").first
        if not await canvas.is_visible():
            return None

        box = await canvas.bounding_box()
        if not box or box["width"] <= 500 or box["height"] <= 300:
            return None

        screenshot_data = await canvas.screenshot()
        Actor.log.info(f"截图成功: {box['width']:.0f}x{box['height']:.0f}")
        return screenshot_data
    except Exception as e:
        Actor.log.error(f"截取 canvas 失败: {e}")
        return None


async def capture_container_screenshot(page: Page, exchange: str) -> bytes | None:
    try:
        container = page.locator(
            f'div:has-text("{exchange}") >> xpath=ancestor::div[contains(@class, "chart") or contains(@class, "heatmap")]'
        ).first
        if await container.is_visible(timeout=2000):
            screenshot_data = await container.screenshot()
            Actor.log.info("截图成功 (容器)")
            return screenshot_data
    except Exception as e:
        Actor.log.error(f"截取容器失败: {e}")

    return None


async def capture_heatmap(page: Page, exchange: str) -> bytes | None:
    screenshot_data = await capture_canvas_screenshot(page)
    if screenshot_data:
        return screenshot_data

    Actor.log.info("尝试截取整个图表区域...")
    return await capture_container_screenshot(page, exchange)


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
        try:
            context = await browser.new_context(
                viewport={"width": 2560, "height": 1440},
                device_scale_factor=2,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            )
            page = await context.new_page()

            Actor.log.info(f"正在打开页面: {url}")
            if not await open_heatmap_page(page, url):
                return None

            await select_pair(page, coin=coin, exchange=exchange, quote_currency=quote_currency)
            await select_time_range(page, time_range)

            return await capture_heatmap(page, exchange)
        finally:
            await browser.close()


def build_base_output(coin: str, exchange: str, quote_currency: str, time_range: str) -> dict[str, str]:
    return {
        "coin": coin,
        "exchange": exchange,
        "quoteCurrency": quote_currency,
        "timeRange": time_range,
    }


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

        base_output = build_base_output(coin, exchange, quote_currency, time_range)

        if not screenshot_data:
            output = {
                "success": False,
                **base_output,
                "error": "截图失败",
            }
            await Actor.set_value("OUTPUT", output)
            await Actor.push_data(output)
            Actor.log.error("截图失败")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{exchange}_{coin}{quote_currency}_{time_range}_{timestamp}.png"

        await Actor.set_value(key=filename, value=screenshot_data, content_type="image/png")
        await Actor.set_value(key="screenshot.png", value=screenshot_data, content_type="image/png")

        kvs = await Actor.open_key_value_store()
        public_url = await kvs.get_public_url(filename)

        output = {
            "success": True,
            **base_output,
            "filename": filename,
            "url": public_url,
            "timestamp": timestamp,
        }
        await Actor.set_value("OUTPUT", output)
        await Actor.push_data(output)
        Actor.log.info(f"完成: {public_url}")
