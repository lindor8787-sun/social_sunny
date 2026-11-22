#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Social ERP - 資料更新腳本
零金鑰：所有來源都是公開 RSS / 開放 API，不需要任何 API key 或帳號。
只用 Python 標準函式庫，不需要 pip install。
"""
import json, os, re, sys, time, hashlib, urllib.request, urllib.error, urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

TPE = timezone(timedelta(hours=8))
ROOT = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(ROOT, "data", "db.json")

PER_FEED_CAP = 60          # 每個來源最多保留幾則
VEG_DAYS = 10              # 菜價往回抓幾天
# 這支 API 每次最多回 1000 筆且分頁參數無效（Page 2 以上一律空），
# 但 MarketName 篩選有效。單一市場單日約 300 多筆，遠低於上限，
# 所以改成「逐日 × 逐市場」查詢，徹底避開截斷。
VEG_MARKETS = ["台北一", "台北二"]
VEG_LIST_CAP = 60
HTTP_TIMEOUT = 30
RETRIES = 3

UA = "Mozilla/5.0 (compatible; social-erp/1.0; +https://github.com/)"

FEEDS = [
    {"key": "news",         "name": "時事",           "source": "公視新聞",        "url": "https://news.pts.org.tw/xml/newsfeed.xml"},
    {"key": "technews",     "name": "科技與海外市場", "source": "TechNews 科技新報", "url": "https://cdn.technews.tw/feed/"},
    {"key": "techorange",   "name": "數位轉型",       "source": "TechOrange 科技報橘", "url": "https://techorange.com/feed/"},
    {"key": "managertoday", "name": "企劃與方法論",   "source": "經理人 Managertoday", "url": "https://rss.bnextmedia.com.tw/feed/managertoday/"},
]

MOA_API = "https://data.moa.gov.tw/api/v1/AgriProductsTransType/"


# ---------- 共用 ----------

def log(*a):
    print("[%s]" % datetime.now(TPE).strftime("%H:%M:%S"), *a, flush=True)


def http_get(url, tries=RETRIES):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA,
                "Accept": "application/rss+xml, application/xml, application/json, text/xml, */*",
            })
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
                return r.read()
        except Exception as e:
            last = e
            log("  取得失敗 (第 %d 次): %s" % (i + 1, e))
            if i < tries - 1:
                time.sleep(2 * (i + 1))
    raise last


def sid(*parts):
    """由內容產生穩定 id，用來去重。"""
    raw = "||".join([p or "" for p in parts])
    return hashlib.sha1(raw.encode("utf-8", "ignore")).hexdigest()[:12]


def strip_html(s):
    if not s:
        return ""
    s = re.sub(r"(?is)<(script|style).*?</\1>", " ", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    s = (s.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<")
          .replace("&gt;", ">").replace("&quot;", '"').replace("&#39;", "'"))
    return re.sub(r"\s+", " ", s).strip()


def clip(s, n):
    s = s or ""
    return s if len(s) <= n else s[:n].rstrip() + "…"


# ---------- RSS / Atom ----------

def _tag(el):
    return el.tag.split("}")[-1] if "}" in el.tag else el.tag


def _find_text(parent, names):
    for ch in list(parent):
        if _tag(ch) in names:
            if ch.text and ch.text.strip():
                return ch.text.strip()
    return ""


def _find_link(parent):
    # RSS: <link>text</link>  /  Atom: <link href="..."/>
    for ch in list(parent):
        if _tag(ch) != "link":
            continue
        if ch.text and ch.text.strip().startswith("http"):
            return ch.text.strip()
        href = ch.attrib.get("href")
        rel = ch.attrib.get("rel", "alternate")
        if href and rel == "alternate":
            return href
    for ch in list(parent):
        if _tag(ch) == "guid" and ch.text and ch.text.strip().startswith("http"):
            return ch.text.strip()
    return ""


MONTHS = {m: i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}


def parse_date(s):
    """把 RSS(RFC822) 或 Atom(ISO8601) 的日期轉成台北時間 ISO 字串。失敗回空字串。"""
    if not s:
        return ""
    s = s.strip()
    # ISO 8601
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})(?:\.\d+)?(Z|[+-]\d{2}:?\d{2})?", s)
    if m:
        y, mo, d, h, mi, se, tz = m.groups()
        dt = datetime(int(y), int(mo), int(d), int(h), int(mi), int(se), tzinfo=timezone.utc)
        if tz and tz != "Z":
            tz = tz.replace(":", "")
            off = int(tz[1:3]) * 60 + int(tz[3:5])
            if tz[0] == "-":
                off = -off
            dt = dt.replace(tzinfo=timezone(timedelta(minutes=off)))
        return dt.astimezone(TPE).isoformat()
    # RFC 822
    m = re.search(r"(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})\s+(\d{2}):(\d{2})(?::(\d{2}))?\s*([+-]\d{4}|GMT|UTC)?", s)
    if m:
        d, mon, y, h, mi, se, tz = m.groups()
        mo = MONTHS.get(mon, 1)
        off = 0
        if tz and tz not in ("GMT", "UTC"):
            off = int(tz[1:3]) * 60 + int(tz[3:5])
            if tz[0] == "-":
                off = -off
        dt = datetime(int(y), mo, int(d), int(h), int(mi), int(se or 0),
                      tzinfo=timezone(timedelta(minutes=off)))
        return dt.astimezone(TPE).isoformat()
    return ""


def parse_feed(raw, feed):
    """同時支援 RSS 2.0 與 Atom。"""
    text = raw.decode("utf-8", "ignore") if isinstance(raw, bytes) else raw
    text = text.lstrip("﻿ \t\r\n")
    root = ET.fromstring(text)
    nodes = []
    for el in root.iter():
        if _tag(el) in ("item", "entry"):
            nodes.append(el)
    out = []
    for el in nodes:
        title = strip_html(_find_text(el, ("title",)))
        if not title:
            continue
        link = _find_link(el)
        date = parse_date(_find_text(el, ("pubDate", "published", "updated", "date")))
        summary = clip(strip_html(_find_text(el, ("description", "summary", "content"))), 180)
        out.append({
            "id": sid(feed["key"], link or title),
            "title": clip(title, 150),
            "link": link,
            "date": date,
            "summary": summary,
            "source": feed["source"],
        })
    return out


def merge_items(old, new):
    """以 id 去重；保留第一次出現的 added_date；更新標題/摘要等易變欄位。"""
    by_id = {}
    order = []
    for it in old:
        by_id[it["id"]] = dict(it)
        order.append(it["id"])
    for it in new:
        i = it["id"]
        if i in by_id:
            keep = by_id[i].get("added_date")
            by_id[i].update(it)
            by_id[i]["added_date"] = keep or datetime.now(TPE).isoformat()
        else:
            it = dict(it)
            it["added_date"] = datetime.now(TPE).isoformat()
            by_id[i] = it
            order.append(i)
    items = [by_id[i] for i in order]
    # 新的在前；沒有日期的排後面
    items.sort(key=lambda x: x.get("date") or x.get("added_date") or "", reverse=True)
    return items[:PER_FEED_CAP]


# ---------- 菜價（農業部開放 API，無須金鑰） ----------

def to_roc(d):
    return "%d.%02d.%02d" % (d.year - 1911, d.month, d.day)


def from_roc(s):
    try:
        y, m, d = s.split(".")
        return datetime(int(y) + 1911, int(m), int(d)).date()
    except Exception:
        return None


def fetch_veg_rows():
    """逐日 × 逐市場抓取，避開 1000 筆截斷。回傳所有交易列。"""
    today = datetime.now(TPE).date()
    rows = []
    truncated = 0
    for back in range(VEG_DAYS + 1):
        day = to_roc(today - timedelta(days=back))
        for market in VEG_MARKETS:
            url = "%s?Start_time=%s&End_time=%s&MarketName=%s" % (
                MOA_API, day, day, urllib.parse.quote(market))
            try:
                data = json.loads(http_get(url, tries=2).decode("utf-8", "ignore"))
            except Exception as e:
                log("    %s %s 取得失敗：%s" % (day, market, e))
                continue
            got = data.get("Data") or []
            rows.extend(got)
            if data.get("Next"):
                truncated += 1
    if truncated:
        log("  警告：%d 次查詢回報仍有後續資料，可能被截斷" % truncated)
    return rows


def fetch_veg():
    rows = fetch_veg_rows()
    log("  取得 %d 筆原始交易資料" % len(rows))

    series = {}   # (crop, market) -> {date: avg}
    meta = {}
    for r in rows:
        market = (r.get("MarketName") or "").strip()
        if market not in VEG_MARKETS:
            continue
        crop = (r.get("CropName") or "").strip()
        if crop == "休市":
            continue
        d = (r.get("TransDate") or "").strip()
        try:
            avg = float(r.get("Avg_Price"))
        except (TypeError, ValueError):
            continue
        if not crop or not d:
            continue
        k = (crop, market)
        series.setdefault(k, {})[d] = avg
        meta[k] = {
            "qty": r.get("Trans_Quantity"),
            "upper": r.get("Upper_Price"),
            "lower": r.get("Lower_Price"),
        }

    items = []
    for (crop, market), by_date in series.items():
        dates = sorted(by_date.keys(), key=lambda s: (from_roc(s) or datetime(1900, 1, 1).date()))
        if len(dates) < 1:
            continue
        last = dates[-1]
        prev = dates[-2] if len(dates) >= 2 else None
        avg = by_date[last]
        pavg = by_date[prev] if prev else None
        chg = None
        if pavg not in (None, 0):
            chg = round((avg - pavg) / pavg * 100, 1)
        items.append({
            "crop": crop,
            "market": market,
            "date": last,
            "avg": round(avg, 1),
            "prev_date": prev,
            "prev_avg": round(pavg, 1) if pavg is not None else None,
            "change_pct": chg,
            "qty": meta[(crop, market)]["qty"],
            "upper": meta[(crop, market)]["upper"],
            "lower": meta[(crop, market)]["lower"],
            "history": [{"d": d, "v": round(by_date[d], 1)} for d in dates],
        })

    # 變動幅度大的排前面（這是「菜價變動」的重點）
    items.sort(key=lambda x: abs(x["change_pct"]) if x["change_pct"] is not None else -1, reverse=True)
    items = items[:VEG_LIST_CAP]
    latest = max([i["date"] for i in items], key=lambda s: (from_roc(s) or datetime(1900, 1, 1).date())) if items else ""
    return {
        "updated_at": datetime.now(TPE).isoformat(),
        "latest_date": latest,
        "market_label": "、".join(VEG_MARKETS),
        "source": "農業部 農產品批發市場交易行情",
        "source_url": "https://data.moa.gov.tw/",
        "items": items,
    }


# ---------- 主流程 ----------

def load_db():
    try:
        with open(DB_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"feeds": {}, "veg": {}}


def main():
    db = load_db()
    db.setdefault("feeds", {})
    db.setdefault("veg", {})
    ok, fail = [], []

    for feed in FEEDS:
        log("抓取:", feed["source"])
        try:
            items = parse_feed(http_get(feed["url"]), feed)
            if not items:
                raise ValueError("解析後 0 則")
            cur = db["feeds"].get(feed["key"], {})
            merged = merge_items(cur.get("items", []), items)
            db["feeds"][feed["key"]] = {
                "name": feed["name"],
                "source": feed["source"],
                "url": feed["url"],
                "updated_at": datetime.now(TPE).isoformat(),
                "ok": True,
                "items": merged,
            }
            log("  ✓ %d 則新資料，合併後共 %d 則" % (len(items), len(merged)))
            ok.append(feed["source"])
        except Exception as e:
            log("  ✗ 失敗:", e)
            if feed["key"] in db["feeds"]:
                db["feeds"][feed["key"]]["ok"] = False
                db["feeds"][feed["key"]]["error"] = str(e)[:200]
            else:
                db["feeds"][feed["key"]] = {
                    "name": feed["name"], "source": feed["source"], "url": feed["url"],
                    "ok": False, "error": str(e)[:200], "items": [],
                }
            fail.append(feed["source"])

    log("抓取: 農業部菜價行情")
    try:
        db["veg"] = fetch_veg()
        log("  ✓ %d 個品項" % len(db["veg"].get("items", [])))
        ok.append("農業部菜價")
    except Exception as e:
        log("  ✗ 失敗:", e)
        db.setdefault("veg", {})["ok"] = False
        db["veg"]["error"] = str(e)[:200]
        fail.append("農業部菜價")

    # 清掉已從 FEEDS 移除的舊來源，避免設定頁永遠顯示一個抓取失敗的幽靈來源
    live = {f["key"] for f in FEEDS}
    for stale in [k for k in db["feeds"] if k not in live]:
        log("移除已不再使用的來源:", stale)
        db["feeds"].pop(stale, None)

    db["updated_at"] = datetime.now(TPE).isoformat()
    db["status"] = {"ok": ok, "failed": fail}

    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=1)
    log("寫入完成:", DB_PATH)
    log("成功 %d 個來源，失敗 %d 個" % (len(ok), len(fail)))
    # 即使部分來源失敗也不讓 workflow 整個紅掉（其他來源仍有更新）
    return 0


if __name__ == "__main__":
    sys.exit(main())
