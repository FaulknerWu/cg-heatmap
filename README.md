# Coinglass Liquidation Heatmap

Capture high-resolution screenshots of cryptocurrency liquidation heatmaps from [Coinglass](https://www.coinglass.com/pro/futures/LiquidationHeatMap).

## What does this Actor do?

This Actor uses Playwright to navigate to Coinglass and capture liquidation heatmap screenshots for any supported cryptocurrency trading pair. The heatmap visualizes liquidation clusters at different price levels, helping traders identify key support/resistance zones.

**Key features:**
- High-resolution screenshots (2560x1440 @ 2x scale)
- Smart canvas rendering detection for optimal image quality
- Supports 20+ exchanges and multiple quote currencies
- Flexible time range selection (12h to 1 year)
- Returns publicly accessible image URL

## Input

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `coin` | string | Cryptocurrency symbol (e.g., BTC, ETH, SOL) | `BTC` |
| `exchange` | string | Exchange name | `Binance` |
| `quoteCurrency` | string | Quote currency (USDT, USD, USDC) | `USDT` |
| `timeRange` | string | Time range for the heatmap | `24h` |
| `headless` | boolean | Run browser in headless mode | `true` |

### Supported Exchanges

Binance, OKX, Bybit, Bitget, MEXC, Gate, HTX, Hyperliquid, BingX, Deribit, Bitfinex, KuCoin, Bitmex, Kraken, Coinbase, CoinEx, dYdX, WhiteBIT, LBank, Bitunix, Crypto.com

### Time Range Options

| Value | Description |
|-------|-------------|
| `12h` | 12 Hours |
| `24h` | 24 Hours |
| `48h` | 48 Hours |
| `3d` | 3 Days |
| `1w` | 1 Week |
| `2w` | 2 Weeks |
| `1m` | 1 Month |
| `3m` | 3 Months |
| `6m` | 6 Months |
| `1y` | 1 Year |

## Output

The Actor outputs a JSON object with the following fields:

```json
{
  "success": true,
  "coin": "BTC",
  "exchange": "Binance",
  "quoteCurrency": "USDT",
  "timeRange": "24h",
  "filename": "Binance_BTCUSDT_24h_20241215_120000.png",
  "url": "https://api.apify.com/v2/key-value-stores/.../records/...",
  "timestamp": "20241215_120000"
}
```

The screenshot is stored in the default Key-Value Store and the `url` field contains a publicly accessible link to the image.

## Example Usage

### Default (BTC/USDT on Binance, 24h)

```json
{
  "coin": "BTC"
}
```

### ETH on OKX, 1 week

```json
{
  "coin": "ETH",
  "exchange": "OKX",
  "quoteCurrency": "USDT",
  "timeRange": "1w"
}
```

### SOL on Bybit, 3 days

```json
{
  "coin": "SOL",
  "exchange": "Bybit",
  "quoteCurrency": "USDT",
  "timeRange": "3d"
}
```

## Use Cases

- **Trading Analysis**: Monitor liquidation levels for potential price reversals
- **Market Research**: Track liquidation distribution across different timeframes
- **Automated Reports**: Schedule periodic heatmap captures for trading dashboards
- **Social Media**: Share liquidation insights with your audience

## Limitations

- Requires Coinglass website to be accessible
- The trading pair must exist on the selected exchange
- Screenshot quality depends on successful canvas rendering
