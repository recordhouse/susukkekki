#!/usr/bin/env python3
import datetime as dt
import html
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path


API_BASE_URL = "https://susukkekki.kr/wp-json/wp/v2"
SITE_URL = "https://susukkekki.kr/"
SITE_NAME = "수수께끼"
SITE_TITLE = "흥미로운 이야기 | 수수께끼"
SITE_DESCRIPTION = "수수께끼는 미스터리, 유머, 여행, 과학 등 알아두면 재미있는 흥미로운 이야기를 쉽고 빠르게 알려주는 한국어 콘텐츠 사이트입니다."
DEFAULT_POSTS_PER_CATEGORY = 9
DISPLAY_POSTS_BY_CATEGORY = {
    "미스터리": 9,
}
INDEX_PATH = Path("index.html")


def fetch_json(url):
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return json.loads(response.read().decode(charset))


def plain_text(value=""):
    text = re.sub(r"<[^>]*>", " ", str(value or ""))
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def escape(value=""):
    return html.escape(str(value or ""), quote=True)


def json_for_html(data):
    return (
        json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


def format_date(value):
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value

    return f"{parsed.year}년 {parsed.month}월 {parsed.day}일 {parsed.hour:02d}:{parsed.minute:02d}"


def get_image_url(post):
    media = (post.get("_embedded", {}).get("wp:featuredmedia") or [{}])[0]
    sizes = media.get("media_details", {}).get("sizes", {})
    for size in ("large", "medium_large", "medium"):
        if sizes.get(size, {}).get("source_url"):
            return sizes[size]["source_url"]
    return media.get("source_url") or ""


def normalize_post(post):
    title = plain_text(post.get("title", {}).get("rendered", ""))
    excerpt = plain_text(
        post.get("excerpt", {}).get("rendered")
        or post.get("content", {}).get("rendered", "")
    )

    return {
        "id": post.get("id"),
        "title": title,
        "excerpt": excerpt,
        "date": post.get("date", ""),
        "modified": post.get("modified", ""),
        "dateLabel": format_date(post.get("date", "")),
        "link": post.get("link", ""),
        "image": get_image_url(post),
        "initial": title[:1] or "S",
    }


def normalize_category(category, posts):
    return {
        "id": category.get("id"),
        "name": plain_text(category.get("name", "")),
        "count": category.get("count", 0),
        "link": category.get("link", ""),
        "posts": [normalize_post(post) for post in posts],
    }


def display_limit_for_category(category):
    name = plain_text(category.get("name", ""))
    return DISPLAY_POSTS_BY_CATEGORY.get(name, DEFAULT_POSTS_PER_CATEGORY)


def fetch_limit_for_category(category):
    name = plain_text(category.get("name", ""))
    extra_for_featured = 1 if name in DISPLAY_POSTS_BY_CATEGORY else 0
    return display_limit_for_category(category) + extra_for_featured


def load_categories():
    category_query = urllib.parse.urlencode(
        {
            "per_page": 100,
            "hide_empty": "true",
            "orderby": "count",
            "order": "desc",
            "_fields": "id,name,count,link",
        }
    )
    categories = fetch_json(f"{API_BASE_URL}/categories?{category_query}")
    rendered = []

    for category in categories:
        # Fetch one extra post for categories with a custom display limit because the
        # newest post may be pulled into the separate featured slot.
        per_page = fetch_limit_for_category(category)
        post_query = urllib.parse.urlencode(
            {
                "categories": category["id"],
                "per_page": per_page,
                "_embed": 1,
            }
        )
        posts = fetch_json(f"{API_BASE_URL}/posts?{post_query}")
        normalized = normalize_category(category, posts)
        if normalized["posts"]:
            rendered.append(normalized)

    return rendered


def render_post(post):
    if post["image"]:
        image = (
            f'<img class="thumb" src="{escape(post["image"])}" '
            f'alt="{escape(post["title"] + " 대표 이미지")}" loading="lazy" itemprop="image" />'
        )
    else:
        image = '<img class="thumb" alt="" loading="lazy" itemprop="image" hidden />'

    return f'''          <article class="post-card" itemscope itemtype="https://schema.org/Article">
            <a class="thumb-link" href="{escape(post["link"])}" target="_blank" rel="noreferrer">
              {image}
              <span class="thumb-fallback" data-initial="{escape(post["initial"])}" aria-hidden="true"></span>
            </a>
            <div class="post-body">
              <time datetime="{escape(post["date"])}" itemprop="datePublished">{escape(post["dateLabel"])}</time>
              <meta itemprop="dateModified" content="{escape(post["modified"] or post["date"])}" />
              <h3><a href="{escape(post["link"])}" target="_blank" rel="noreferrer" itemprop="url headline">{escape(post["title"])}</a></h3>
              <p itemprop="description">{escape(post["excerpt"])}</p>
            </div>
          </article>'''


def get_featured_post(categories):
    posts = [post for category in categories for post in category["posts"]]
    return max(posts, key=lambda post: post["date"], default=None)


def render_featured(categories):
    latest = get_featured_post(categories)
    if not latest:
        return ""
    return render_post(latest).replace("          <article", "        <article", 1)


def render_category(category, excluded_post_id=None):
    category_posts = [
        post for post in category["posts"] if post["id"] != excluded_post_id
    ][: display_limit_for_category(category)]
    if not category_posts:
        return ""
    posts = "\n".join(render_post(post) for post in category_posts)
    return f'''        <section class="category-section" aria-label="{escape(category["name"])} 게시글">
          <div class="category-header">
            <h2><a href="{escape(category["link"])}" target="_blank" rel="noreferrer">{escape(category["name"])}</a></h2>
            <span>{len(category_posts)}개</span>
          </div>
          <div class="category-posts">
{posts}
          </div>
        </section>'''


def render_posts(categories):
    if not categories:
        return '        <p class="empty-state">흥미로운 최신 이야기를 준비 중입니다.</p>'
    featured = get_featured_post(categories)
    excluded_post_id = featured["id"] if featured else None
    return "\n".join(
        section
        for section in (
            render_category(category, excluded_post_id) for category in categories
        )
        if section
    )


def structured_data(categories):
    posts = [
        {**post, "category": category["name"]}
        for category in categories
        for post in category["posts"]
    ]
    latest_modified = max(
        (post["modified"] or post["date"] for post in posts),
        default=None,
    )

    return {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": SITE_TITLE,
        "url": SITE_URL,
        "inLanguage": "ko-KR",
        "description": SITE_DESCRIPTION,
        "dateModified": latest_modified,
        "isPartOf": {
            "@type": "WebSite",
            "name": SITE_NAME,
            "url": SITE_URL,
        },
        "publisher": {
            "@type": "Organization",
            "name": SITE_NAME,
            "url": SITE_URL,
            "logo": {
                "@type": "ImageObject",
                "url": f"{SITE_URL}favicon.svg",
            },
        },
        "about": ["미스터리", "유머", "여행", "과학", "흥미로운 이야기"],
        "mainEntity": {
            "@type": "ItemList",
            "numberOfItems": len(posts),
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": index + 1,
                    "item": {
                        "@type": "Article",
                        "headline": post["title"],
                        "description": post["excerpt"],
                        "url": post["link"],
                        "mainEntityOfPage": post["link"],
                        "image": post["image"] or None,
                        "datePublished": post["date"],
                        "dateModified": post["modified"] or post["date"],
                        "articleSection": post["category"],
                        "inLanguage": "ko-KR",
                        "author": {
                            "@type": "Organization",
                            "name": SITE_NAME,
                        },
                        "publisher": {
                            "@type": "Organization",
                            "name": SITE_NAME,
                        },
                    },
                }
                for index, post in enumerate(posts)
            ],
        },
    }


def replace_between(source, start, end, content):
    pattern = re.compile(rf"(\s*{re.escape(start)}\s*)[\s\S]*?(\s*{re.escape(end)})")
    if not pattern.search(source):
        raise RuntimeError(f"Missing marker: {start}")
    return pattern.sub(lambda match: f"{match.group(1)}\n{content}\n        {match.group(2)}", source, count=1)


def replace_structured_data(source, data):
    script = (
        '    <script id="latest-posts-structured-data" type="application/ld+json">'
        f"{json_for_html(data)}</script>"
    )
    without_old = re.sub(
        r'\n\s*<script id="latest-posts-structured-data" type="application/ld\+json">[\s\S]*?</script>',
        "",
        source,
        count=1,
    )
    return without_old.replace("\n  </head>", f"\n{script}\n  </head>", 1)


def replace_meta_content(source, selector, content):
    escaped = escape(content)
    pattern = re.compile(
        rf'(<meta\s+{selector}\s+content=")[^"]*(")',
        flags=re.IGNORECASE,
    )
    if pattern.search(source):
        return pattern.sub(rf"\1{escaped}\2", source, count=1)

    return source


def replace_head_links(source, categories):
    posts = [post for category in categories for post in category["posts"]]
    latest_post = max(posts, key=lambda post: post["date"], default=None)
    latest_image = latest_post["image"] if latest_post else f"{SITE_URL}favicon.svg"
    latest_title = latest_post["title"] if latest_post else SITE_NAME

    replacements = [
        ('name="description"', SITE_DESCRIPTION),
        ('property="og:title"', SITE_TITLE),
        ('property="og:description"', "미스터리, 유머, 여행, 과학 등 알아두면 재미있는 흥미로운 이야기를 만나보세요."),
        ('property="og:image"', latest_image),
        ('property="og:image:alt"', f"{latest_title} - {SITE_NAME}"),
        ('name="twitter:title"', SITE_TITLE),
        ('name="twitter:description"', "수수께끼는 미스터리, 유머, 여행, 과학 등 알아두면 재미있는 흥미로운 이야기를 알려줍니다."),
        ('name="twitter:image"', latest_image),
    ]

    for selector, content in replacements:
        source = replace_meta_content(source, selector, content)

    return re.sub(
        r"<title>[\s\S]*?</title>",
        f"<title>{escape(SITE_TITLE)}</title>",
        source,
        count=1,
    )


def main():
    categories = load_categories()
    post_count = sum(len(category["posts"]) for category in categories)
    source = INDEX_PATH.read_text(encoding="utf-8")

    source = re.sub(
        r'<p id="statusText">[\s\S]*?</p>',
        f'<p id="statusText">흥미로운 이야기 {post_count}개를 표시 중입니다.</p>',
        source,
        count=1,
    )
    source = replace_head_links(source, categories)
    source = replace_between(
        source,
        "<!-- STATIC_FEATURED_START -->",
        "<!-- STATIC_FEATURED_END -->",
        render_featured(categories),
    )
    source = replace_between(
        source,
        "<!-- STATIC_POSTS_START -->",
        "<!-- STATIC_POSTS_END -->",
        render_posts(categories),
    )
    source = replace_between(
        source,
        "<!-- STATIC_DATA_START -->",
        "<!-- STATIC_DATA_END -->",
        f'    <script id="static-post-data" type="application/json">{json_for_html({"categories": categories})}</script>',
    )
    source = replace_structured_data(source, structured_data(categories))

    INDEX_PATH.write_text(source, encoding="utf-8")
    print(f"Generated {post_count} posts from {len(categories)} categories.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(error, file=sys.stderr)
        sys.exit(1)
