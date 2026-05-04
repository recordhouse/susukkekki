const API_BASE_URL = "https://susukkekki.kr/wp-json/wp/v2";
const DEFAULT_POSTS_PER_CATEGORY = 9;
const POSTS_PER_CATEGORY = new Map();
const SITE_URL = "https://susukkekki.kr/";
const SITE_NAME = "수수께끼";
const SITE_TITLE = "흥미로운 이야기 | 수수께끼";
const SITE_DESCRIPTION =
  "수수께끼는 미스터리, 유머, 여행, 과학 등 알아두면 재미있는 흥미로운 이야기를 쉽고 빠르게 알려주는 한국어 콘텐츠 사이트입니다.";

const state = {
  categories: [],
  query: "",
  loading: false,
};

const featuredPost = document.querySelector("#featuredPost");
const postGrid = document.querySelector("#postGrid");
const statusText = document.querySelector("#statusText");
const refreshButton = document.querySelector("#refreshButton");
const searchInput = document.querySelector("#searchInput");
const template = document.querySelector("#postCardTemplate");
const structuredDataId = "latest-posts-structured-data";
const staticPostData = document.querySelector("#static-post-data");

const plainText = (html = "") => {
  const doc = new DOMParser().parseFromString(html, "text/html");
  return doc.body.textContent.replace(/\s+/g, " ").trim();
};

const formatDate = (date) =>
  new Intl.DateTimeFormat("ko-KR", {
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(date));

const getImageUrl = (post) => {
  const media = post._embedded?.["wp:featuredmedia"]?.[0];
  return (
    media?.media_details?.sizes?.large?.source_url ||
    media?.media_details?.sizes?.medium_large?.source_url ||
    media?.media_details?.sizes?.medium?.source_url ||
    media?.source_url ||
    ""
  );
};

const normalizePost = (post) => {
  const title = plainText(post.title?.rendered);
  const excerpt = plainText(post.excerpt?.rendered || post.content?.rendered);

  return {
    id: post.id,
    title,
    excerpt,
    date: post.date,
    modified: post.modified,
    dateLabel: formatDate(post.date),
    link: post.link,
    image: getImageUrl(post),
    initial: title.slice(0, 1) || "S",
  };
};

const normalizeCategory = (category, posts) => ({
  id: category.id,
  name: plainText(category.name),
  count: category.count,
  link: category.link,
  posts: posts.map(normalizePost),
});

const postsPerCategory = (category) =>
  POSTS_PER_CATEGORY.get(plainText(category.name)) || DEFAULT_POSTS_PER_CATEGORY;

const readStaticData = () => {
  if (!staticPostData?.textContent) {
    return [];
  }

  try {
    const data = JSON.parse(staticPostData.textContent);
    return Array.isArray(data.categories) ? data.categories : [];
  } catch (error) {
    console.error("Failed to parse static post data", error);
    return [];
  }
};

const createCard = (post) => {
  const node = template.content.firstElementChild.cloneNode(true);
  const thumbLink = node.querySelector(".thumb-link");
  const image = node.querySelector(".thumb");
  const fallback = node.querySelector(".thumb-fallback");
  const time = node.querySelector("time");
  const titleLink = node.querySelector("h3 a");
  const excerpt = node.querySelector("p");

  thumbLink.href = post.link;
  titleLink.href = post.link;
  titleLink.textContent = post.title;
  excerpt.textContent = post.excerpt;
  time.dateTime = post.date;
  time.textContent = post.dateLabel;
  fallback.dataset.initial = post.initial;
  node.setAttribute("itemscope", "");
  node.setAttribute("itemtype", "https://schema.org/Article");
  titleLink.setAttribute("itemprop", "url headline");
  image.setAttribute("itemprop", "image");
  excerpt.setAttribute("itemprop", "description");
  time.setAttribute("itemprop", "datePublished");

  if (post.image) {
    image.src = post.image;
    image.alt = `${post.title} 대표 이미지`;
    image.addEventListener("error", () => {
      image.hidden = true;
    });
  } else {
    image.hidden = true;
  }

  return node;
};

const filteredCategories = () => {
  const query = state.query.trim().toLowerCase();
  if (!query) return state.categories;

  return state.categories
    .map((category) => ({
      ...category,
      posts: category.posts.filter((post) =>
        `${category.name} ${post.title} ${post.excerpt}`.toLowerCase().includes(query),
      ),
    }))
    .filter((category) => category.posts.length);
};

const createCategorySection = (category) => {
  const section = document.createElement("section");
  section.className = "category-section";
  section.setAttribute("aria-label", `${category.name} 게시글`);

  const header = document.createElement("div");
  header.className = "category-header";

  const title = document.createElement("h2");
  const titleLink = document.createElement("a");
  titleLink.href = category.link;
  titleLink.target = "_blank";
  titleLink.rel = "noreferrer";
  titleLink.textContent = category.name;
  title.append(titleLink);

  const count = document.createElement("span");
  count.textContent = `${category.posts.length}개`;

  const grid = document.createElement("div");
  grid.className = "category-posts";

  category.posts.forEach((post) => grid.append(createCard(post)));
  header.append(title, count);
  section.append(header, grid);

  return section;
};

const updateStructuredData = () => {
  document.querySelector(`#${structuredDataId}`)?.remove();

  if (!state.categories.length) {
    return;
  }

  const posts = state.categories.flatMap((category) =>
    category.posts.map((post) => ({ ...post, category: category.name })),
  );
  const modifiedDates = posts
    .map((post) => post.modified || post.date)
    .filter(Boolean)
    .sort();
  const latestModified = modifiedDates[modifiedDates.length - 1];
  const data = {
    "@context": "https://schema.org",
    "@type": "CollectionPage",
    name: SITE_TITLE,
    url: SITE_URL,
    inLanguage: "ko-KR",
    description: SITE_DESCRIPTION,
    dateModified: latestModified,
    isPartOf: {
      "@type": "WebSite",
      name: SITE_NAME,
      url: SITE_URL,
    },
    publisher: {
      "@type": "Organization",
      name: SITE_NAME,
      url: SITE_URL,
      logo: {
        "@type": "ImageObject",
        url: `${SITE_URL}favicon.svg`,
      },
    },
    about: ["미스터리", "유머", "여행", "과학", "흥미로운 이야기"],
    mainEntity: {
      "@type": "ItemList",
      numberOfItems: posts.length,
      itemListElement: posts.map((post, index) => ({
        "@type": "ListItem",
        position: index + 1,
        item: {
          "@type": "Article",
          headline: post.title,
          description: post.excerpt,
          url: post.link,
          mainEntityOfPage: post.link,
          image: post.image || undefined,
          datePublished: post.date,
          dateModified: post.modified || post.date,
          articleSection: post.category,
          inLanguage: "ko-KR",
          author: {
            "@type": "Organization",
            name: SITE_NAME,
          },
          publisher: {
            "@type": "Organization",
            name: SITE_NAME,
          },
        },
      })),
    },
  };
  const script = document.createElement("script");
  script.id = structuredDataId;
  script.type = "application/ld+json";
  script.textContent = JSON.stringify(data);
  document.head.append(script);
};

const render = () => {
  const categories = filteredCategories();
  featuredPost.replaceChildren();
  postGrid.replaceChildren();

  if (!state.categories.length && state.loading) {
    return;
  }

  if (!categories.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "검색어와 일치하는 게시글이 없습니다.";
    postGrid.append(empty);
    return;
  }

  categories.forEach((category) => postGrid.append(createCategorySection(category)));
};

const updateStatus = () => {
  const postCount = state.categories.reduce(
    (total, category) => total + category.posts.length,
    0,
  );
  statusText.textContent = `흥미로운 이야기 ${postCount}개를 표시 중입니다.`;
};

const setLoading = (loading) => {
  state.loading = loading;
  refreshButton.disabled = loading;
  refreshButton.setAttribute("aria-busy", String(loading));
};

const loadPosts = async () => {
  setLoading(true);
  statusText.textContent = "흥미로운 최신 이야기를 불러오는 중입니다.";

  try {
    const categoriesResponse = await fetch(
      `${API_BASE_URL}/categories?per_page=100&hide_empty=true&orderby=count&order=desc&_fields=id,name,count,link&_=${Date.now()}`,
      {
        headers: { Accept: "application/json" },
      },
    );

    if (!categoriesResponse.ok) {
      throw new Error(`HTTP ${categoriesResponse.status}`);
    }

    const categories = await categoriesResponse.json();
    const categoriesWithPosts = await Promise.all(
      categories.map(async (category) => {
        try {
          const postsResponse = await fetch(
            `${API_BASE_URL}/posts?categories=${category.id}&per_page=${postsPerCategory(category)}&_embed=1&_=${Date.now()}`,
            {
              headers: { Accept: "application/json" },
            },
          );

          if (!postsResponse.ok) {
            throw new Error(`HTTP ${postsResponse.status}`);
          }

          return normalizeCategory(category, await postsResponse.json());
        } catch (error) {
          console.error(`Failed to load category ${category.id}`, error);
          return normalizeCategory(category, []);
        }
      }),
    );

    state.categories = categoriesWithPosts.filter((category) => category.posts.length);
    updateStatus();
    updateStructuredData();
    render();
  } catch (error) {
    featuredPost.replaceChildren();
    postGrid.replaceChildren();
    const message = document.createElement("p");
    message.className = "error-state";
    message.textContent =
      "게시글을 불러오지 못했습니다. 잠시 후 새로고침을 눌러 다시 시도해 주세요.";
    postGrid.append(message);
    statusText.textContent = "연결 오류가 발생했습니다.";
    console.error(error);
  } finally {
    setLoading(false);
  }
};

refreshButton.addEventListener("click", loadPosts);
searchInput.addEventListener("input", (event) => {
  state.query = event.target.value;
  render();
});

state.categories = readStaticData();

if (state.categories.length) {
  updateStatus();
  updateStructuredData();
} else {
  loadPosts();
}
