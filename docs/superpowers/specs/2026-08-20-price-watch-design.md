# Chemist Warehouse 价格监控 — 设计文档

日期: 2026-08-20

## 目标

每天悉尼时间 9:00am 自动抓取 Chemist Warehouse 上 7 个固定商品的当前价格，与历史价格比对，把结果通过邮件发到 gdzjjack@gmail.com，同时在一个 GitHub Pages 静态页面上展示价格历史走势图。全部通过 GitHub Actions 定时任务运行，零服务器成本。

## 已验证的关键事实

商品页是 Next.js 服务端渲染页面，价格数据以 JSON 形式内嵌在页面的
`<script id="__NEXT_DATA__" type="application/json" nonce="...">...</script>` 标签里
（注意：`id` 和 `type` 之间还有一个随机 `nonce` 属性，正则匹配不能假设标签只有这两个属性）。

解析路径（用两个真实商品页验证过，`requests.get` 即可，不需要浏览器渲染）：

```python
data = json.loads(next_data_script_text)
product = data["props"]["pageProps"]["product"]
name = product["product"]["name"]
price_entry = product["prices"][0]           # 列表里通常只有一个 sku 条目
current_price = price_entry["price"]["value"]["amount"]   # 当前售价（含特价）
rrp = price_entry["price"]["rrp"]["amount"]                # 原价 RRP
sku = price_entry["sku"]
```

验证样本：

| 商品 | URL | 当前价 | RRP |
|---|---|---|---|
| Swisse Ultiboost 鱼油 1500mg 400粒 | `chemistwarehouse.com.au/buy/67489/...` | 47.99 | 79.99（有折扣）|
| CeraVe Daily Moisturising Lotion 1L | `chemistwarehouse.com.au/buy/91315/...` | 38.99 | 38.99（当前无折扣）|

CeraVe 当前价=RRP 说明小票上那次 $27.39 的特价促销周期已结束，属于正常促销轮换，不代表抓取逻辑有问题——这印证了必须同时记录 price 和 rrp，而不能只认"有没有折扣"判断抓取是否正常。

## 要追踪的 7 个商品

来自 2026-07-04 的购物小票，去重后 7 个商品：

1. CeraVe Daily Moisturising Lotion 1L
2. Swisse Ultiboost Odourless High Strength Wild Fish Oil 1500mg 400 Capsules
3. Ostelin Vitamin D3 1000IU 300 Capsules (Exclusive Bulk Size)
4. Blackmores EPO 1000mg 190 Capsules
5. Swisse Men's Ultivite 50+ 90 Tablets
6. Swisse Women's Ultivite 50+ 90 Tablets
7. Blackmores Lutein Defence 120 Tablets

已确认 URL：#1（91315）、#2（67489）。其余 5 个 URL 需要在实现阶段逐一核对确认（同名商品在 CW 网站上常有多个规格/包装，必须点开确认与小票上的规格完全一致，不能只靠搜索结果标题猜）。

## 仓库结构

```
chemist-warehouse-price-tracker/
├── .github/workflows/price-check.yml   # cron 定时任务
├── products.json                        # 7个商品的 id/name/url
├── scripts/
│   └── fetch_prices.py                  # 抓取 + 解析 + 更新历史 + 发邮件
├── docs/
│   ├── index.html                       # 价格走势静态页（Chart.js CDN）
│   └── data/history.json                # {date: {productId: {price, rrp} | null}}
└── requirements.txt                     # requests
```

GitHub Pages 配置为从 `main` 分支的 `/docs` 目录发布，不需要单独的 `gh-pages` 分支或构建步骤。

## 数据流

1. GitHub Actions 定时触发（见"调度"一节）
2. `fetch_prices.py` 读取 `products.json`，逐个请求商品页
3. 对每个商品：解析 `__NEXT_DATA__` → 提取 name/price/rrp；失败则该商品当天记为 `null` 并记录错误，不中断其余商品
4. 把今天的结果追加进 `docs/data/history.json`（按日期为 key）
5. 用 Python 生成/更新 `docs/index.html` 里嵌的最新数据摘要（页面本身通过 `fetch('data/history.json')` 动态读取，index.html 基本不用每次重写，只有首次创建）
6. `git commit` + `git push` 回 main（提交信息如 `chore: price data YYYY-MM-DD`）
7. 用 `dawidd6/action-send-mail`（SMTP，走 Gmail）发送当日报告邮件

## 调度（悉尼时间 9am，处理夏令时）

悉尼时间在 AEST（UTC+10，4月-10月）和 AEDT（UTC+11，10月-4月）之间切换。workflow 配两条 cron：

```yaml
on:
  schedule:
    - cron: '0 22 * * *'   # 覆盖 AEDT 期间的 9am
    - cron: '0 23 * * *'   # 覆盖 AEST 期间的 9am
  workflow_dispatch: {}     # 方便手动触发测试
```

脚本启动时用 `zoneinfo.ZoneInfo("Australia/Sydney")` 换算出当前悉尼本地时间，如果不在 8:55–9:05 这个窗口内就直接退出、不抓取也不发信——避免同一天因为两条 cron 都命中而重复发送，也保证换季时间点依然准确。`workflow_dispatch` 触发时跳过这个时间窗口检查，方便随时手动测试。

## 邮件内容

每天固定发送一封（不管有没有降价），表格包含：商品名（带链接）、今日价、昨日价、涨跌金额（降价绿色/涨价红色/持平灰色）、RRP。抓取失败的商品单独列一行注明"抓取失败，请检查"。

## 需要人工完成的前置步骤

- 在 Google 账号里生成一个 Gmail 应用专用密码，作为 GitHub repo secret `GMAIL_APP_PASSWORD` 存入（Claude 无法代为操作，需要用户在浏览器里手动完成两步验证流程）
- 安装并登录 `gh` CLI（已确认由 Claude 协助完成）后，由 Claude 创建远程仓库 `chemist-warehouse-price-tracker` 并推送

## 错误处理

- 单个商品抓取失败：记录错误、该商品当天数据记为 `null`，不影响其余商品，邮件里列出失败商品
- 全部商品都失败（例如网站整体改版导致 `__NEXT_DATA__` 结构变化）：邮件仍然发送，标题注明"抓取全部失败"，方便第一时间发现需要更新解析逻辑
- git push 冲突（理论上不会发生，只有这一个 workflow 会写 main）：无需处理，单一写入源

## 测试

- 本地先用 `python scripts/fetch_prices.py --dry-run`（不发邮件、不 push，只打印结果）验证抓取和解析逻辑
- 用 `workflow_dispatch` 手动触发一次完整流程（含发邮件），确认 GitHub Pages 页面和邮件都正常
