# -*- coding: utf-8 -*-
"""
ikanbot.com (我爱看播) 爬虫
- 首页: 从 /hot/index-movie-热门.html 和 /hot/index-tv-热门.html 获取推荐
- 分类: 按 movie/tv/anime/variety/documentary + 子筛选(热门/最新/华语/动作等)
- 搜索: /search?q={keyword}
- 播放: /api/getResN API获取m3u8直链 (无需解析线路)
"""
import sys
import re
import json
import requests as rq
from urllib.parse import quote

sys.path.append('..')
try:
    from base.spider import Spider
except ImportError:
    class Spider:
        def fetch(self, url, headers=None, **kw):
            kw.pop('timeout', None)
            r = rq.get(url, headers=headers, timeout=15, **kw)
            r.encoding = 'utf-8'
            return r

def _(x): return x

HOST = "https://www.ikanbot.com"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# 分类配置
# type_id -> {name, url_type, tag}
# url_type: 'hot' 用 /hot/index-{type}-{tag}.html
#           'category' 用 /category/{id}?p={page}
CLASS_MAP = {
    # === 电影 ===
    "movie_hot":     {"name": "电影·热门",     "url_type": "hot", "cat": "movie", "tag": "热门"},
    "movie_new":     {"name": "电影·最新",     "url_type": "hot", "cat": "movie", "tag": "最新"},
    "movie_classic": {"name": "电影·经典",     "url_type": "hot", "cat": "movie", "tag": "经典"},
    "movie_douban":  {"name": "电影·豆瓣高分", "url_type": "hot", "cat": "movie", "tag": "豆瓣高分"},
    "movie_hidden":  {"name": "电影·冷门佳片", "url_type": "hot", "cat": "movie", "tag": "冷门佳片"},
    "movie_cn":      {"name": "电影·华语",     "url_type": "hot", "cat": "movie", "tag": "华语"},
    "movie_us":      {"name": "电影·欧美",     "url_type": "hot", "cat": "movie", "tag": "欧美"},
    "movie_kr":      {"name": "电影·韩国",     "url_type": "hot", "cat": "movie", "tag": "韩国"},
    "movie_jp":      {"name": "电影·日本",     "url_type": "hot", "cat": "movie", "tag": "日本"},
    "movie_action":  {"name": "电影·动作",     "url_type": "hot", "cat": "movie", "tag": "动作"},
    "movie_comedy":  {"name": "电影·喜剧",     "url_type": "hot", "cat": "movie", "tag": "喜剧"},
    "movie_love":    {"name": "电影·爱情",     "url_type": "hot", "cat": "movie", "tag": "爱情"},
    "movie_scifi":   {"name": "电影·科幻",     "url_type": "hot", "cat": "movie", "tag": "科幻"},
    "movie_susp":    {"name": "电影·悬疑",     "url_type": "hot", "cat": "movie", "tag": "悬疑"},
    "movie_horror":  {"name": "电影·恐怖",     "url_type": "hot", "cat": "movie", "tag": "恐怖"},
    "movie_grow":    {"name": "电影·成长",     "url_type": "hot", "cat": "movie", "tag": "成长"},
    "movie_top250":  {"name": "豆瓣top250",    "url_type": "hot", "cat": "movie", "tag": "豆瓣top250"},
    # === 剧集 ===
    "tv_hot":        {"name": "剧集·热门",     "url_type": "hot", "cat": "tv", "tag": "热门"},
    "tv_new":        {"name": "剧集·最新",     "url_type": "hot", "cat": "tv", "tag": "最新"},
    "tv_us":         {"name": "美剧",           "url_type": "hot", "cat": "tv", "tag": "美剧"},
    "tv_uk":         {"name": "英剧",           "url_type": "hot", "cat": "tv", "tag": "英剧"},
    "tv_kr":         {"name": "韩剧",           "url_type": "hot", "cat": "tv", "tag": "韩剧"},
    "tv_jp":         {"name": "日剧",           "url_type": "hot", "cat": "tv", "tag": "日剧"},
    "tv_cn":         {"name": "国产剧",         "url_type": "hot", "cat": "tv", "tag": "国产剧"},
    "tv_hk":         {"name": "港剧",           "url_type": "hot", "cat": "tv", "tag": "港剧"},
    "tv_classic":    {"name": "剧集·经典",     "url_type": "hot", "cat": "tv", "tag": "经典"},
    "tv_douban":     {"name": "剧集·豆瓣高分", "url_type": "hot", "cat": "tv", "tag": "豆瓣高分"},
    # === 动漫/综艺/纪录片 (用category保证内容准确) ===
    "anime":         {"name": "动漫",           "url_type": "category", "cat_id": 18},
    "variety":       {"name": "综艺",           "url_type": "category", "cat_id": 19},
    "documentary":   {"name": "纪录片",         "url_type": "category", "cat_id": 20},
}


class Spider(Spider):

    def init(self, extend=""):
        self._session = rq.Session()
        self._session.headers.update({"User-Agent": UA})
        try:
            self._session.get(HOST, timeout=10)
        except:
            pass

    def getName(self):
        return "ikanbot"

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url or ".flv" in url

    def manualVideoCheck(self):
        return False

    def homeContent(self, filter=False):
        classes = []
        for tid, info in CLASS_MAP.items():
            classes.append({"type_id": tid, "type_name": info["name"]})
        return {"class": classes}

    def homeVideoContent(self):
        try:
            all_items = []
            # 电影热门
            items = self._fetch_hot_list("movie", "热门", 1, 24)
            all_items.extend(items)
            # 剧集热门
            items = self._fetch_hot_list("tv", "热门", 1, 24)
            all_items.extend(items)
            return {"list": all_items}
        except:
            return {"list": []}

    def categoryContent(self, tid, pg=1, filter=False, extend=None):
        try:
            pn = max(int(str(pg)), 1)
            info = CLASS_MAP.get(tid)
            if not info:
                return {"list": [], "page": pn, "pagecount": 1, "limit": 24, "total": 0}

            url_type = info.get("url_type", "category")
            if url_type == "hot":
                cat = info["cat"]
                tag = info["tag"]
                items = self._fetch_hot_list(cat, tag, pn, 24)
            else:
                cat_id = info.get("cat_id", 1)
                items = self._fetch_category_list(cat_id, pn, 48)

            return {"list": items, "page": pn, "pagecount": pn + 10, "limit": 24, "total": 0}
        except:
            return {"list": [], "page": pg, "pagecount": 1, "limit": 24, "total": 0}

    def detailContent(self, ids):
        try:
            vid = str(ids[0]) if ids else ""
            if not vid:
                return {"list": []}

            detail_url = f"{HOST}/play/{vid}"
            r = self._get(detail_url, timeout=15000)
            html = r.text if hasattr(r, 'text') else str(r)

            etoken = self._extract(html, r'id="e_token"\s+value="([^"]+)"')
            cid = self._extract(html, r'id="current_id"\s+value="([^"]+)"')
            mtype = self._extract(html, r'id="mtype"\s+value="([^"]+)"') or "1"
            title = self._extract(html, r'<h1[^>]*>([^<]+)</h1>') or ""
            # 封面: 从第一个data-src取
            cover = self._extract(html, r'data-src="([^"]+\.(?:jpg|png|webp))"') or ""

            if not cid or not etoken:
                return {"list": []}

            token = self._gen_token(cid, etoken)

            api_url = f"{HOST}/api/getResN?videoId={cid}&mtype={mtype}&token={token}"
            r2 = self._get(api_url, timeout=15000)
            text = r2.text if hasattr(r2, 'text') else str(r2)
            data = json.loads(text)

            if data.get("state") != 1:
                return {"list": []}

            source_list = data.get("data", {}).get("list", [])

            pf_list = []
            pu_list = []
            for src in source_list:
                site_id = src.get("siteId", "")
                res_data = src.get("resData", "[]")
                try:
                    episodes = json.loads(res_data)
                except:
                    episodes = []

                if not episodes:
                    continue

                ep_list = []
                for ep in episodes:
                    flag = ep.get("flag", f"线路{site_id}")
                    ep_url = ep.get("url", "")
                    if "$" in ep_url:
                        ep_name, ep_play_url = ep_url.split("$", 1)
                    else:
                        ep_name = ep_url[:30]
                        ep_play_url = ep_url

                    if ep_play_url:
                        ep_list.append(f"{ep_name}${ep_play_url}")

                if ep_list:
                    pf_list.append(flag)
                    pu_list.append("#".join(ep_list))

            vod = {
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": cover,
                "vod_play_from": "$$$".join(pf_list),
                "vod_play_url": "$$$".join(pu_list),
            }
            return {"list": [vod]}
        except:
            return {"list": []}

    def searchContent(self, key, quick=False, pg=1):
        try:
            url = f"{HOST}/search?q={quote(key)}"
            items = self._fetch_search(url)
            return {"list": items, "page": 1}
        except:
            return {"list": [], "page": 1}

    def playerContent(self, flag, id, vipFlags=None):
        url = str(id) if id else str(flag)
        if not url:
            return {"url": ""}
        if "$" in url:
            parts = url.split("$", 1)
            url = parts[1]

        if url.startswith("http"):
            return {"url": url}
        return {"url": url}

    def _get(self, url, timeout=15):
        r = self._session.get(url, timeout=timeout)
        r.encoding = 'utf-8'
        return r

    def _extract(self, text, pattern):
        m = re.search(pattern, text)
        return m.group(1) if m else ""

    def _gen_token(self, current_id, e_token):
        last4 = current_id[-4:]
        parts = []
        tk = e_token
        for ch in last4:
            mod = int(ch) % 3 + 1
            part = tk[mod:mod + 8]
            parts.append(part)
            tk = tk[mod + 8:]
        return "".join(parts)

    def _fetch_category_list(self, cat_id, page, limit):
        """从 /category/{cat_id}?p={page} 抓取影片列表"""
        url = f"{HOST}/category/{cat_id}?p={page}"

        r = self._get(url, timeout=15000)
        html = r.text if hasattr(r, 'text') else str(r)

        items = []
        pattern = re.compile(
            r'<a\s+class="item"\s+href="(/play/(\d+))">'
            r'[\s\S]*?'
            r'<img[^>]+id="\d+"[^>]+alt="([^"]+)"'
            r'(?:[^>]+data-src="([^"]+)")?'
        )
        matches = pattern.findall(html)
        for href, vid, title, cover in matches[:limit]:
            # 没封面的在分类列表中隐藏
            if not cover or cover.startswith("data:"):
                continue
            items.append({
                "vod_id": vid,
                "vod_name": title.strip(),
                "vod_pic": cover,
                "vod_remarks": "",
            })
        return items

    def _fetch_hot_list(self, cat, tag, page, limit):
        """从 /hot/index-{cat}-{tag}-p-{page}.html 抓取影片列表"""
        if page > 1:
            url = f"{HOST}/hot/index-{cat}-{tag}-p-{page}.html"
        else:
            url = f"{HOST}/hot/index-{cat}-{tag}.html"

        r = self._get(url, timeout=15000)
        html = r.text if hasattr(r, 'text') else str(r)

        items = []
        pattern = re.compile(
            r'<a\s+class="item"\s+href="(/play/(\d+))">'
            r'[\s\S]*?'
            r'<img[^>]+id="\d+"[^>]+alt="([^"]+)"'
            r'(?:[^>]+data-src="([^"]+)")?'
        )
        matches = pattern.findall(html)
        for href, vid, title, cover in matches[:limit]:
            # 没封面的在分类列表中隐藏
            if not cover or cover.startswith("data:"):
                continue
            items.append({
                "vod_id": vid,
                "vod_name": title.strip(),
                "vod_pic": cover,
                "vod_remarks": "",
            })
        return items

    def _fetch_search(self, url):
        r = self._get(url, timeout=15000)
        html = r.text if hasattr(r, 'text') else str(r)

        items = []
        seen = set()
        pattern = re.compile(
            r'<a[^>]+href="(/play/(\d+))"[^>]*>'
            r'[\s\S]*?'
            r'<img[^>]+id="\d+"[^>]+alt="([^"]+)"'
            r'(?:[^>]+data-src="([^"]+)")?'
        )
        matches = pattern.findall(html)
        for href, vid, title, cover in matches:
            if vid in seen:
                continue
            seen.add(vid)
            items.append({
                "vod_id": vid,
                "vod_name": title.strip(),
                "vod_pic": cover or "",
                "vod_remarks": "",
            })
        return items

    def localProxy(self, param):
        pass
