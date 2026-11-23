# 維護手冊

這份文件是給**未來接手的人**看的——可能是幾個月後的你自己，也可能是完全沒看過這專案的人。
目標是讓人不必重新摸索就能改動它。所有「實測結論」都是真的踩過才寫下來的，請不要重新踩一次。

最後更新：2026-11-23

---

## 一、這是什麼

一個自動更新的個人資訊站，每天把幾個來源的內容抓進來，集中在一頁瀏覽。

- 線上網址：<https://lindor8787-sun.github.io/social_sunny/>
- 原始碼：<https://github.com/lindor8787-sun/social_sunny>

分成兩類內容：

| 類型 | 區塊 | 怎麼來的 |
|---|---|---|
| 自動更新 | 時事、產業・媒體、行銷・方法論、菜價行情 | GitHub Actions 每天抓 |
| 靜態 | 法律知識、金融知識中心、金融計算工具、生活情報 | 寫死在 `index.html` |

---

## 二、三條不可違反的原則

動手改之前先讀這段。這三條是專案存在的前提，不是偏好。

### 1. 完全免費、不綁信用卡、不需要任何 API 金鑰

repo 裡沒有、也不應該有 GitHub Secrets。所有資料來自公開 RSS 與政府開放 API。

**不要引入 Gemini 或任何需要開帳單的服務。** 這件事評估過並且否決了，理由記錄在下面第八節，別重做一次評估。

### 2. 不收集任何個人資料

收藏、深淺色、閱讀紀錄只存在瀏覽器的 `localStorage`（key 為 `social_erp_v1`），不上傳、不進 repo、換電腦不跟著走。
`data/db.json` 裡只有公開新聞與公開行情。

因為沒有個資，repo 設公開才是安全的（GitHub Pages 免費方案也需要公開 repo）。

### 3. 不要把記帳功能加回來

這個站是從一個叫 FinLearn ERP 的原型改造的，那個原型有完整的記帳、預算、資產負債功能。
**那些是刻意拔掉的**，理由是「個人財務資料放在網頁上有風險」。保留下來的金融知識中心與計算工具都不存個資。

---

## 三、架構

```
使用者瀏覽器
      │  讀取
      ▼
index.html ──fetch──▶ data/db.json
                           ▲
                           │ commit
                  .github/workflows/update.yml
                  （台北時間每天 09:00 / 20:00）
                           │ 執行
                           ▼
                  fetch_and_update.py
                           │ 抓取
         ┌─────────────────┼──────────────────┐
         ▼                 ▼                  ▼
   公視 Atom        TechNews / TechOrange   農業部開放 API
                    經理人 RSS
```

沒有伺服器、沒有資料庫、沒有建置步驟。GitHub Pages 直接把 repo 根目錄當靜態網站發佈。

### 檔案清單

| 檔案 | 職責 |
|---|---|
| `index.html` | 整個前端。HTML + CSS + JS 全部內嵌在這一個檔案裡 |
| `fetch_and_update.py` | 抓取腳本。只用 Python 標準函式庫，**沒有任何 pip 相依** |
| `data/db.json` | 唯一的資料存放處，由 Actions 自動 commit 回來 |
| `.github/workflows/update.yml` | 排程設定 |
| `README.md` | 給第一次架設的人看的 |
| `MAINTENANCE.md` | 這份 |

---

## 四、`index.html` 內部結構

單檔約 930 行。由上而下分成幾段：

### CSS（`<style>` 內）

用 CSS 變數做主題。`:root` 定義淺色，`[data-theme="dark"]` 覆寫成深色。
改配色只要動這兩塊的變數，不用翻整份樣式。

重要的 class：

- `.tblwrap` + `.tbl` — 長資料表格。`.tbl th` 設了 `position:sticky; top:0`，**捲動時表頭會凍結**，這是刻意的，不要拿掉
- `.up` / `.down` / `.flat` — 漲跌顏色。依台灣習慣，**漲是紅色、跌是綠色**
- `.warnbox` — 黃色警告框，法律頁在用
- `.stale` — 紅色提示框，資料過期或讀不到 json 時出現

### JavaScript

依序是：

**工具函式**　`$` `$$` `esc` `fmt` `uid` `toast` `modal` `confirmDialog`

**圖表**　`barChart` `lineChart` `donut`，純 canvas 手寫，無外部繪圖函式庫

**靜態內容種子**　`ART_SEED`（金融文章）、`GLOSSARY_SEED`（術語）、`FAQ_SEED`、`COURSE_SEED`（課程）、`LAW_SEED`（法律）、`SHOPPING_SEED`（換季檔期）

**資料層**
- `STORE` — 只管 localStorage，存使用者偏好與收藏
- `EMBEDDED_DB` — 內嵌的種子資料，供 `file://` 開啟時使用
- `DATA` / `DATA_SOURCE` — 實際渲染用的資料；`DATA_SOURCE` 是 `'file'`（讀到 db.json）或 `'embedded'`（後備）
- `loadData()` — 啟動時呼叫。**偵測到 `location.protocol === 'file:'` 會直接跳過 fetch**，因為瀏覽器一定會擋跨來源讀取，試了只會在 console 留紅字嚇人
- `allFeedItems(keys)` — 把指定來源的項目合併後依時間排序

**導覽**　`PAGES` 陣列定義側欄；`nav(id)` 切頁；每頁對應一個 `RENDER.<id>` 函式

**各頁**　`RENDER.dashboard` `news` `industry` `marketing` `veg` `life` `law` `knowledge` `calculators` `settings`

**計算工具**　`TOOLS` 物件，目前五個：複利計算器、儲蓄目標試算、貸款月付金試算、通膨與購買力試算、緊急預備金計算。每個工具自己定義 `fields`（輸入欄）與 `compute()`（回傳結果列、計算假設、繪圖函式）

**啟動**　`STORE.load()` → `applyTheme()` → `buildNav()` → `loadData().then(() => nav('dashboard'))`

---

## 五、`fetch_and_update.py` 內部結構

### 可調參數（檔案最上方）

| 參數 | 預設 | 說明 |
|---|---|---|
| `PER_FEED_CAP` | 60 | 每個來源保留幾則，超過從最舊的淘汰 |
| `VEG_DAYS` | 10 | 菜價往回抓幾天 |
| `VEG_MARKETS` | 台北一、台北二 | 要看的批發市場 |
| `VEG_LIST_CAP` | 60 | 菜價最多列幾個品項 |
| `RETRIES` | 3 | 每個來源失敗重試次數 |
| `FEEDS` | — | RSS 來源清單 |

### 主要函式

- `http_get(url, tries)` — 帶重試的 HTTP 取得
- `parse_feed(raw, feed)` — **同時支援 RSS 2.0 與 Atom**。靠 tag 名稱判斷（`item` 或 `entry`），不需要為新來源改程式
- `parse_date(s)` — 同時處理 RFC 822（`Wed, 18 Nov 2026 11:54:06 +0800`）與 ISO 8601，統一轉成台北時間
- `merge_items(old, new)` — 以內容 hash 當 id 去重；**保留第一次出現的 `added_date`**；更新標題摘要等易變欄位；依時間排序後裁切到上限
- `fetch_veg_rows()` — 逐日 × 逐市場查詢農業部 API（原因見下一節）
- `fetch_veg()` — 計算漲跌、整理歷史序列、依變動幅度排序
- `main()` — 逐一處理來源，**每個來源用 try/except 隔離**，一個掛掉不影響其他；最後清掉已從 `FEEDS` 移除的舊來源

### 容錯設計（請不要「優化」掉）

1. **單一來源失敗不會中斷其他來源。** 失敗時標記 `ok: false` 並保留上次成功的資料，不清空。
2. **全部失敗時腳本仍回傳結束碼 0。** 這是刻意的——讓 workflow 不要因為外部網站暫時掛掉就整個紅掉。
   **副作用：workflow 綠燈不代表有抓到資料。** 驗證時一定要看 `db.json` 的 `status` 欄位，不要只看綠燈。
3. 只在 `db.json` 真的有變動時才 commit，避免產生無意義的 commit 紀錄。

---

## 六、農業部菜價 API 實測筆記

Endpoint：`https://data.moa.gov.tw/api/v1/AgriProductsTransType/`（免金鑰、免註冊）

這支 API 有好幾個不直觀的行為，全部實測確認過：

| 行為 | 細節 |
|---|---|
| **日期必須用民國年** | `115.11.22` 可以，`2026.11.22` 會回**空陣列而不是報錯**，很容易誤判成沒資料 |
| **單次最多 1000 筆** | 超過時回傳 `"Next": true` |
| **分頁是壞的** | `Page=0` 與 `Page=1` 回同一頁，`Page=2` 以上一律回 0 筆。`$skip` / `Skip` / `Offset` / `TopN` / `$top` 全部被忽略 |
| **市場代碼參數無效** | `Market_No`、`MarketNo`、`Market` 都無效，回傳仍混有其他市場 |
| **只有 `MarketName` 有效** | 用中文市場名篩選才真的會過濾 |
| 資料量 | 單日全市場 > 1000 筆（會被截斷）；單一市場單日約 300–350 筆（安全） |

### 結論：必須逐日 × 逐市場查詢

```
?Start_time=115.11.22&End_time=115.11.22&MarketName=台北一
```

每次請求都把起訖日設成同一天，再加市場名。一次執行約發出 22 次請求（11 天 × 2 市場），每次都遠低於上限。

**不要為了「減少請求數」改回單次大範圍查詢。** 之前就是這樣寫的，結果每個品項只拿得到最新一天的資料，漲跌全部算不出來，頁面上「上漲 0 項、下跌 0 項」。

### 資料清理注意事項

- `CropName` 可能是 `休市`（市場休市的標記列），要濾掉
- `Avg_Price` 可能是 `null`
- 漲跌是「最新交易日 vs 前一個**有交易紀錄**的日子」，中間遇到休市會自動跳過，不是固定比昨天

---

## 七、RSS 來源現況

### 目前可用

| 來源 | 網址 | 備註 |
|---|---|---|
| 公視新聞 | `https://news.pts.org.tw/xml/newsfeed.xml` | Atom 格式，更新頻繁 |
| TechNews 科技新報 | `https://cdn.technews.tw/feed/` | 原網址 `technews.tw/feed/` 會 302 轉到這裡，直接用轉址後的 |
| TechOrange 科技報橘 | `https://techorange.com/feed/` | |

### 已死或不穩（別再試）

| 來源 | 狀況 |
|---|---|
| Motive 商業洞察 | **網站已改為封存版本**，頁面自己寫「只保留部分文章」，feed 回 HTML。已移除 |
| 經理人 Managertoday | `rss.bnextmedia.com.tw/feed/managertoday/` 會**間歇性產出空 feed**——只有頻道標頭、零篇文章，但 `lastBuildDate` 照常更新。目前仍保留，腳本會標記失敗並保留上次資料 |
| 數位時代 | 同平台 `/feed/bnext/`，長期是空的 |
| 中央社 | feedburner 網址 404 |
| Inside | `/feed` 與 `/rss` 都不是有效 feed |
| 動腦 | `/rss/news` 回 500 |

### 已知缺口

**「行銷・方法論」這一區來源不足。** 台灣行銷類媒體的 RSS 生態不好，目前只剩一個不穩的經理人。

要補的話，**務必先實際抓一次確認 feed 裡真的有 `<item>`**，不要只看網址回 200 就寫進去——上面那幾個死掉的來源都是網址還在、內容是空的或 HTML。

---

## 八、為什麼不用 AI 抓取（歷史決策）

一開始的規劃是走「GitHub Actions + Gemini 免費版 + Google Search grounding」，跟其他幾個看板專案一樣。查完官方文件後否決了：

- Gemini API 的**模型呼叫**確實有免費層，但 **Google Search grounding 是獨立計價的工具**，不包含在裡面
- 只有 **Gemini 2.5 系列**在免費層有 grounding（每天 500 次）
- 但官方已限制 2.5 系列「只開放給過去實際使用過的使用者」，新專案建議改用 3.5 / 3.8
- 而 **Gemini 3 系列的 grounding 在免費層標示 Not available**，必須開帳單綁卡
- 沒有 grounding 的模型只會憑訓練資料編造新聞，比不做還糟

所以改走純 RSS / 公開 API。副作用是可靠度反而更高（政府 API 的數字不會被語言模型轉述錯），代價是「服裝特惠」這類沒有結構化來源的內容做不了。

---

## 九、常見維護任務

### 新增或更換 RSS 來源

改 `fetch_and_update.py` 最上方的 `FEEDS`：

```python
FEEDS = [
    {"key": "自訂代號", "name": "顯示名稱", "source": "來源名稱", "url": "feed 網址"},
]
```

RSS 2.0 與 Atom 都支援，不用改解析程式。

移除來源時**不必手動清 `db.json`**，腳本會自動刪掉不在 `FEEDS` 裡的舊來源（否則設定頁會永遠顯示一個抓取失敗的幽靈來源）。

如果新來源要獨立成一個分頁，還要改 `index.html`：在 `PAGES` 加一項，再寫對應的 `RENDER.<id>` 函式（可以照抄 `RENDER.industry`，它用的是通用的 `feedPage()`）。

### 改更新時間

改 `.github/workflows/update.yml` 的 cron。**格式是 UTC，台北時間要減 8 小時。**

目前 `0 1,12 * * *` = 台北 09:00 與 20:00。
改成每天只跑一次早上八點 → `0 0 * * *`。

### 改菜價看的市場

改 `VEG_MARKETS`。市場名稱要用 API 回傳的中文名（例如 `台中`、`板橋區`、`三重區`）。
市場數量直接影響請求次數（天數 × 市場數），加太多會讓執行變慢。

### 改配色或版面

全部在 `index.html` 的 `<style>` 裡。深淺色各一組 CSS 變數。

### 新增靜態內容（法律、金融知識等）

改對應的 `*_SEED` 常數。法律區改完**一定要更新 `LAW_VERIFIED_AT` 的日期**。

---

## 十、驗證流程

改完之後請照順序跑完，不要只看 workflow 綠燈。

```bash
# 1. 語法
python -m py_compile fetch_and_update.py

# 2. JSON 與 YAML 可解析
python -c "import json;json.load(open('data/db.json',encoding='utf-8'))"
python -c "import yaml;yaml.safe_load(open('.github/workflows/update.yml',encoding='utf-8'))"

# 3. 本機預覽（會讀到真的 db.json）
python -m http.server 8000     # 然後開 http://127.0.0.1:8000
```

4. 推上去後到 Actions 頁籤按 **Run workflow** 手動跑一次
5. **最關鍵的一步**：打開
   `https://raw.githubusercontent.com/lindor8787-sun/social_sunny/main/data/db.json`
   檢查
   - `status.ok` 與 `status.failed` 分別有誰
   - 每個來源的 `items` 長度合不合理
   - 菜價的 `change_pct` 有沒有值（**全是 `null` 就是逐日查詢壞了**）
6. 最後開線上網站，確認頁面真的有東西

### 建議補的離線測試

這個專案的解析與計算邏輯值得用單元測試固定住。測過的項目：

RSS 2.0 與 Atom 解析、CDATA 標題、HTML entity 還原、無連結的項目不會壞、RFC 822 與 ISO 8601 日期轉台北時間、UTC +8 換算、去重與 `added_date` 保留、超量淘汰、民國年雙向轉換、菜價漲跌計算、跨日配對前期、休市列與 null 價格過濾、依變動幅度排序、把 HTML 當 feed 餵進去不會丟出未捕捉例外。

測菜價時要 **mock `http_get` 並依 URL 裡的日期與市場回傳不同資料**，否則測不出逐日查詢是否正確。

---

## 十一、故障排除

| 症狀 | 可能原因 |
|---|---|
| workflow 綠燈但網站沒新資料 | 正常現象之一：腳本在全部來源失敗時仍回傳 0。看 `db.json` 的 `status.failed` |
| 沒有產生 commit | 資料跟上次完全相同，腳本刻意不 commit |
| 菜價「變動」全是 `—`、上漲下跌都 0 項 | 逐日查詢壞了，或日期用成西元年。看第六節 |
| 某個來源一直紅點 | 先手動開那個 feed 網址確認裡面有沒有 `<item>`。多半是對方的問題 |
| 雙擊 `index.html` 只看到舊資料 | 正常。`file://` 讀不到 `data/db.json`，會自動改用內嵌種子資料。要看最新的請開線上網址 |
| 網站整頁空白 | 開 DevTools 看 console。多半是 `index.html` 的 JS 語法錯誤 |
| Pages 沒更新 | Settings → Pages 確認 Source 是 `Deploy from a branch`、分支 `main`、目錄 `/ (root)` |

---

## 十二、刻意不做的事

這些不是還沒做，是評估後決定不做。要改變決定前請先讀原因。

**「今天哪裡有折扣」**
沒有任何公開統一資料源能可靠提供這個。硬寫只會給出過期或錯誤的折扣資訊，比沒有更糟。
生活情報頁改放換季檔期的節奏整理，加上品牌官網查詢入口，讓使用者自己點進去看最新公告。

**法規動態自動更新**
全國法規資料庫擋自動抓取，司法院憲法法庭沒有 feed。
立法院確實有「法律提案」API，但它追蹤的是**提案進度**，不是已公布法規的異動——拿來當「法規動態」會誤導人。
所以法律區採「人工查證的靜態知識 + 官方查詢入口」。

---

## 十三、法律區的特別注意事項

法律區的每一條都是從全國法規資料庫與財政部公告**逐條抄錄**的，不是憑印象寫的。查證日期記在 `index.html` 的 `LAW_VERIFIED_AT`。

修改時請遵守：

1. **只寫查得到原文的內容。** 查不到就別寫，寧可留查詢入口。
2. **改完更新 `LAW_VERIFIED_AT`。**
3. **遺產稅免稅額與各項扣除額幾乎每年調整**，隔年務必重新確認財政部公告。
4. **民法 §1223（特留分）的警告不要拿掉。** 該條於 115 年 8 月 17 日修正公布、自公布後六個月施行。查證當日法規資料庫同時掛著「本法規部分或全部條文尚未生效」的提示，且顯示版本已不含「兄弟姊妹」。也就是說看到的可能是尚未上路的新版。這個差異在真實繼承案件裡會直接改變分配結果，頁面上的黃框警告是必要的。
5. 頁面最上方的「這不是法律意見」免責聲明也不要拿掉。

---

## 十四、本機開發環境

家中電腦（miosnew）上已有完整的 git repo：

```
C:\Users\User\Downloads\social_sunny
```

remote 已指向 GitHub，改完 `git push` 即可。

換一台電腦的話：

```bash
git clone https://github.com/lindor8787-sun/social_sunny.git
cd social_sunny
python fetch_and_update.py     # 手動抓一次（只更新本機 db.json）
python -m http.server 8000
```

排程只在 GitHub 上跑，本機執行腳本不會影響線上。

> 注意：某些公司網路或受管理的執行環境有對外白名單，會讓腳本所有來源都抓失敗並回報
> `403 host is not on the allow list`。那是網路限制，不是程式壞了——GitHub Actions 的執行環境沒有這層限制。
