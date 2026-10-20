'use strict';

/* 研图 · Figure Atlas — static search page over data.json (catalog version 3). */

const ICONS = {
  search: '<circle cx="11" cy="11" r="6.5"/><path d="m16 16 4.5 4.5"/>',
  close: '<path d="M6 6l12 12M18 6 6 18"/>',
  bookmark: '<path d="M6.5 4.5A1.5 1.5 0 0 1 8 3h8a1.5 1.5 0 0 1 1.5 1.5V21L12 17.3 6.5 21Z"/>',
  download: '<path d="M12 4v11m-4.5-4.5L12 15l4.5-4.5M5 19h14"/>',
  external: '<path d="M14 4h6v6m0-6-9 9M19 14v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h4"/>',
  copy: '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/>',
  left: '<path d="m14.5 6-6 6 6 6"/>', right: '<path d="m9.5 6 6 6-6 6"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5m0-8h.01"/>',
  sliders: '<path d="M4 7h10m4 0h2M4 17h4m4 0h8"/><circle cx="16" cy="7" r="2"/><circle cx="10" cy="17" r="2"/>',
  contrast: '<circle cx="12" cy="12" r="8.5"/><path d="M12 3.5v17a8.5 8.5 0 0 0 0-17Z" fill="currentColor"/>',
  github: '<path d="M9 19c-4.3 1.4-4.3-2.5-6-3m12 5v-3.5c0-1 .1-1.4-.5-2 2.8-.3 5.5-1.4 5.5-6a4.6 4.6 0 0 0-1.3-3.2 4.2 4.2 0 0 0-.1-3.2s-1.1-.3-3.5 1.3a12.3 12.3 0 0 0-6.2 0C6.5 2.8 5.4 3.1 5.4 3.1a4.2 4.2 0 0 0-.1 3.2A4.6 4.6 0 0 0 4 9.5c0 4.6 2.7 5.7 5.5 6-.6.6-.6 1.2-.5 2V21"/>',
  link: '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
  file: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8Zm0 0v5h5"/>'
};
const svgIcon = name => `<svg class="ic" viewBox="0 0 24 24" aria-hidden="true">${ICONS[name] || ''}</svg>`;
const paintIcons = (root = document) => root.querySelectorAll('[data-icon]').forEach(el => { if (!el.firstChild) el.innerHTML = svgIcon(el.dataset.icon); });
paintIcons();

const $ = id => document.getElementById(id);
const fmt = n => Number(n || 0).toLocaleString('zh-CN');
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const norm = v => String(v ?? '').normalize('NFKC').toLowerCase().replace(/[‐-―_]+/g, '-');
// "U-Net", "Swin Transformer" also match "unet", "swintransformer".
const compact = (...values) => values.map(v => norm(v).replace(/[\s\-·.]+/g, '')).join(' ');
const store = {
  get(key, fallback) { try { const v = localStorage.getItem(key); return v === null ? fallback : JSON.parse(v); } catch { return fallback; } },
  set(key, value) { try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* private mode */ } }
};

const TAB_NAMES = { atomic: '图元', paper: '论文原图', icon: '科研图标', all: '全部素材', favorites: '我的收藏' };
const DEFAULT_TAB = 'atomic';
const KIND_LABEL = { paper: '论文原图', atomic: '图元', icon: '图标' };
const SWATCHES = ['#1f2937', '#3b5bdb', '#0f8a5f', '#d9480f', '#c2255c', '#7048e8', '#0b7285', '#ffffff'];
const FAVORITES_KEY = 'paper-elements-favorites-v1';
const PAGE = { paper: 48, icon: 180, mixed: 96 };

const state = {
  tab: DEFAULT_TAB, q: '', category: '', pack: '', from: '', arch: false, vector: false, mono: false, featured: false,
  sort: 'relevance', limit: 0, color: store.get('figure-atlas-color', '#1f2937')
};
let catalog = null, items = [], byId = new Map(), results = [], current = null, pngSize = 512, searchTimer = 0;
let favorites = new Set((store.get(FAVORITES_KEY, []) || []).map(String));

/* ------------------------------------------------------------------ theme */
(function initTheme() {
  const saved = store.get('figure-atlas-theme', '');
  if (saved) document.documentElement.dataset.theme = saved;
  $('themeToggle').addEventListener('click', () => {
    const dark = document.documentElement.dataset.theme
      ? document.documentElement.dataset.theme === 'dark'
      : matchMedia('(prefers-color-scheme: dark)').matches;
    const next = dark ? 'light' : 'dark';
    document.documentElement.dataset.theme = next;
    store.set('figure-atlas-theme', next);
  });
})();

/* ------------------------------------------------------------------ data */
function buildItems(data) {
  const out = [];
  const sources = data.sources;
  for (const p of data.papers) {
    const s = sources[p.source] || {};
    const it = {
      type: p.kind, id: p.id, name: p.name, category: p.category, tags: p.tags || [], description: p.description,
      figure: p.figure, caption: p.caption, source: s, sourceKey: p.source, year: p.year || s.year, page: p.page,
      files: p.files, thumb: p.files.thumb || p.files.png, width: p.width, height: p.height, svgKind: p.svg_kind,
      architecture: p.architecture, hasAlpha: p.has_alpha, vector: Boolean(p.files.svg || p.files.pdf), featured: true,
      original: Boolean(p.original), collection: p.collection || '', upstream: p.upstream || '',
      from: p.kind === 'atomic' ? (p.original ? p.source : p.collection || p.source) : ''
    };
    it.en = p.original || p.collection ? p.english : `${s.short || ''}${p.figure ? ' · ' + p.figure : ''}`;
    it.search = norm([it.id, it.name, it.en, it.category, it.description, it.tags.join(' '), s.title, s.short,
      s.venue, (s.authors || []).join(' '), it.caption, it.year].join(' ')) + ' ' + compact(it.name, it.en, s.short, it.tags.join(' '));
    out.push(it);
  }
  const f = Object.fromEntries(data.icons.fields.map((k, i) => [k, i]));
  const cats = data.categories.icon;
  for (const r of data.icons.rows) {
    const pack = data.packs[r[f.pack]];
    const it = {
      type: 'icon', id: r[f.id], pack: r[f.pack], packInfo: pack, file: r[f.file], src: pack.path + r[f.file],
      name: r[f.zh], en: r[f.en], category: cats[r[f.cat]], tagText: r[f.tags], featured: Boolean(r[f.flags] & 1),
      mono: Boolean(r[f.flags] & 2), author: r[f.author], license: r[f.license]
    };
    it.thumb = it.src;
    it.search = norm([it.id, it.name, it.en, it.category, it.tagText, pack.name, it.author].join(' ')) + ' ' + compact(it.en);
    out.push(it);
  }
  out.forEach((it, i) => {
    it.order = i; it.nName = norm(it.name); it.nEn = norm(it.en);
    it.cName = compact(it.name); it.cEn = compact(it.type === 'icon' ? it.en : it.source.short || it.en);
  });
  return out;
}

async function load() {
  $('loadError').hidden = true;
  $('grid').innerHTML = Array.from({ length: 8 }, () => '<div class="skeleton" aria-hidden="true"></div>').join('');
  try {
    const res = await fetch('data.json');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    catalog = await res.json();
    if (catalog.version !== 3) throw new Error('索引版本不兼容');
    items = buildItems(catalog);
    byId = new Map(items.map(it => [it.id, it]));
    fillCounts();
    heroArt();
    readUrl();
    syncControls();
    render();
    openFromHash();
  } catch (error) {
    console.error(error);
    $('grid').replaceChildren();
    $('grid').setAttribute('aria-busy', 'false');
    $('loadError').hidden = false;
    $('resultsSummary').textContent = '加载失败';
    $('loadErrorMessage').textContent = location.protocol === 'file:'
      ? '请用 python scripts/serve.py 启动本地服务后再打开页面。' : `请检查网络后重试（${error.message}）。`;
  }
}

function fillCounts() {
  const c = catalog.counts;
  const values = { papers: c.papers, atomic: c.atomic, icons: c.icons, sources: c.sources, packs: c.packs };
  document.querySelectorAll('[data-count]').forEach(el => { el.textContent = fmt(values[el.dataset.count]); });
  updateTabCounts();
}

// Tab counts follow the current search so matches in other collections stay visible.
let tabCounts = {};
function updateTabCounts() {
  const toks = state.q ? tokens() : [];
  const counts = { all: 0, paper: 0, atomic: 0, icon: 0, favorites: 0 };
  for (const it of items) {
    if (toks.length && !matches(it, toks)) continue;
    counts[it.type] += 1;
    counts.all += 1;
    if (favorites.has(it.id)) counts.favorites += 1;
  }
  tabCounts = counts;
  document.querySelectorAll('[data-tab]').forEach(btn => {
    const span = [...btn.querySelectorAll('span')].find(s => !s.dataset.icon);
    if (span) span.textContent = fmt(counts[btn.dataset.tab]);
  });
  $('favoriteCount').textContent = fmt(toks.length ? items.filter(it => favorites.has(it.id)).length : counts.favorites);
}

function heroArt() {
  // Elements lead; one original figure shows where they come from.
  const picks = ['el-seq-down-1', 'el-mask-causal-blue', 'el-tensor-cube-purple', 'el-image-day', 'el-tokens-cls-teal'];
  const tiles = picks.map(id => byId.get(id)).filter(Boolean);
  const art = $('heroArt');
  art.innerHTML = tiles.map((it, i) => `<div class="tile t${i + 1}"><img src="${esc(it.thumb)}" alt="" decoding="async"><span>${esc(it.name)}</span></div>`).join('')
    + chipFor('f3d-robot', 'c1', '机器人 · 数据库 · 卫星') + chipFor('el-radar-1', 'c2', '雷达回波 · 地球 · 点云');
  function chipFor(id, cls, label) {
    const it = byId.get(id);
    return it ? `<div class="chip ${cls}"><img src="${esc(it.thumb)}" alt="">${esc(label)}</div>` : '';
  }
}

/* ------------------------------------------------------------------ url state */
function readUrl() {
  const p = new URLSearchParams(location.search);
  if (TAB_NAMES[p.get('tab')]) state.tab = p.get('tab');
  state.q = p.get('q') || '';
  state.category = p.get('cat') || '';
  state.pack = p.get('pack') || '';
  state.from = p.get('from') || '';
}
function writeUrl() {
  const p = new URLSearchParams();
  if (state.tab !== DEFAULT_TAB) p.set('tab', state.tab);
  if (state.q) p.set('q', state.q);
  if (state.category) p.set('cat', state.category);
  if (state.pack) p.set('pack', state.pack);
  if (state.from) p.set('from', state.from);
  const qs = p.toString();
  history.replaceState(null, '', `${location.pathname}${qs ? '?' + qs : ''}${location.hash}`);
}

/* ------------------------------------------------------------------ filtering */
function inTab(it) {
  switch (state.tab) {
    case 'paper': return it.type === 'paper';
    case 'atomic': return it.type === 'atomic';
    case 'icon': return it.type === 'icon';
    case 'favorites': return favorites.has(it.id);
    default: return true;
  }
}
function passOptions(it, skip = '') {
  if (state.arch && it.type !== 'icon' && !it.architecture) return false;
  if (state.arch && it.type === 'icon') return false;
  if (state.vector && !(it.type !== 'icon' && it.vector)) return false;
  if (state.mono && !(it.type === 'icon' && it.mono)) return false;
  if (state.featured && it.type === 'icon' && !it.featured) return false;
  if (skip !== 'pack' && state.pack && it.pack !== state.pack) return false;
  if (skip !== 'from' && state.from && it.from !== state.from) return false;
  if (skip !== 'category' && state.category && it.category !== state.category) return false;
  return true;
}
function tokens() { return norm(state.q).split(/\s+/).filter(Boolean); }
function matches(it, toks) { return toks.every(t => it.search.includes(t)); }

function score(it, toks) {
  let s = it.type === 'atomic' ? 320 : it.type === 'paper' ? 260 : (it.featured ? 120 : 0);
  if (it.type === 'icon') s -= PACK_RANK[it.pack] || 0;
  if (!toks.length) return s;
  const name = it.nName, en = it.nEn, cName = it.cName, cEn = it.cEn;
  for (const t of toks) {
    const ct = t.replace(/[\s\-·.]+/g, '');
    if (name === t || en === t || cName === ct || cEn === ct) s += 400;
    else if (name.startsWith(t) || en.startsWith(t) || cName.startsWith(ct) || cEn.startsWith(ct)) s += 220;
    else if (name.includes(t) || en.includes(t) || cName.includes(ct) || cEn.includes(ct)) s += 120;
  }
  return s;
}
const PACK_RANK = { phosphor: 0, tabler: 2, iconpark: 4, 'fluent-emoji': 5, bioicons: 3, healthicons: 6, 'carbon-pictograms': 7, carbon: 9, mdi: 10, 'fluent-system': 11 };

function compute() {
  const toks = tokens();
  const base = items.filter(it => inTab(it) && matches(it, toks));
  results = base.filter(it => passOptions(it));
  if (state.sort === 'name') results.sort((a, b) => a.name.localeCompare(b.name, 'zh-CN'));
  else if (state.sort === 'year-desc') results.sort((a, b) => (b.year || 0) - (a.year || 0) || a.order - b.order);
  else if (state.sort === 'year-asc') results.sort((a, b) => (a.year || 9999) - (b.year || 9999) || a.order - b.order);
  else {
    const scored = results.map(it => [score(it, toks), it]);
    scored.sort((a, b) => b[0] - a[0] || a[1].order - b[1].order);
    results = scored.map(x => x[1]);
  }
  return base;
}

/* ------------------------------------------------------------------ facets */
function renderFacets(base) {
  const catCount = new Map(), packCount = new Map(), fromCount = new Map();
  for (const it of base) {
    if (passOptions(it, 'category')) catCount.set(it.category, (catCount.get(it.category) || 0) + 1);
    if (it.type === 'icon' && passOptions(it, 'pack')) packCount.set(it.pack, (packCount.get(it.pack) || 0) + 1);
    if (it.from && passOptions(it, 'from')) fromCount.set(it.from, (fromCount.get(it.from) || 0) + 1);
  }
  const cat = $('categoryFacet');
  const groups = [['paper', '论文原图'], ['atomic', '图元'], ['icon', '图标']];
  const html = [];
  for (const [type, label] of groups) {
    const list = catalog.categories[type].filter(c => catCount.get(c));
    if (!list.length) continue;
    if (state.tab === 'all' || state.tab === 'favorites') html.push(`<div class="group-label">${label}</div>`);
    for (const c of list) {
      html.push(`<button type="button" data-category="${esc(c)}" class="${state.category === c ? 'active' : ''}"><span>${esc(c)}</span><span class="count">${fmt(catCount.get(c))}</span></button>`);
    }
  }
  if (state.category && !catCount.get(state.category)) {
    html.unshift(`<button type="button" data-category="${esc(state.category)}" class="active"><span>${esc(state.category)}</span><span class="count">0</span></button>`);
  }
  cat.innerHTML = html.join('') || '<p class="sub">没有可选分类</p>';
  const showPacks = state.tab === 'icon' || state.tab === 'all' || state.tab === 'favorites';
  $('packBlock').hidden = !showPacks || !packCount.size;
  $('packFacet').innerHTML = Object.entries(catalog.packs)
    .filter(([key]) => packCount.get(key) || state.pack === key)
    .map(([key, p]) => `<button type="button" data-pack="${esc(key)}" class="${state.pack === key ? 'active' : ''}"><span>${esc(p.name)} <span class="sub">${esc(p.style)}</span></span><span class="count">${fmt(packCount.get(key) || 0)}</span></button>`)
    .join('');
  const fromKeys = [...fromCount.keys()];
  if (state.from && !fromKeys.includes(state.from)) fromKeys.push(state.from);
  fromKeys.sort((a, b) => Number(Boolean(catalog.sources[b]?.original)) - Number(Boolean(catalog.sources[a]?.original))
    || (fromCount.get(b) || 0) - (fromCount.get(a) || 0));
  $('fromBlock').hidden = state.tab === 'paper' || state.tab === 'icon' || !fromKeys.length;
  $('fromFacet').innerHTML = fromKeys.map(key => {
    const s = catalog.sources[key] || {};
    const licence = s.original ? 'CC0' : s.license_name || '';
    return `<button type="button" data-from="${esc(key)}" class="${state.from === key ? 'active' : ''}"><span>${esc(s.short || key)} <span class="sub">${esc(licence)}</span></span><span class="count">${fmt(fromCount.get(key) || 0)}</span></button>`;
  }).join('');
  document.querySelectorAll('#optionBlock [data-scope]').forEach(el => {
    const scope = el.dataset.scope;
    const any = state.tab === 'all' || state.tab === 'favorites';
    el.hidden = !(any || state.tab === scope || (scope === 'figure' && (state.tab === 'paper' || state.tab === 'atomic')));
  });
  $('optionBlock').hidden = [...document.querySelectorAll('#optionBlock [data-scope]')].every(el => el.hidden);
}

function renderActive() {
  const chips = [];
  if (state.q) chips.push(['q', `搜索：${state.q}`]);
  if (state.category) chips.push(['category', state.category]);
  if (state.pack) chips.push(['pack', catalog.packs[state.pack]?.name || state.pack]);
  if (state.from) chips.push(['from', `来源：${catalog.sources[state.from]?.short || state.from}`]);
  if (state.arch) chips.push(['arch', '完整架构图']);
  if (state.vector) chips.push(['vector', '附矢量']);
  if (state.mono) chips.push(['mono', '可改色']);
  if (state.featured) chips.push(['featured', '科研常用']);
  const box = $('activeFilters');
  box.hidden = !chips.length;
  box.innerHTML = chips.map(([k, label]) => `<button type="button" data-clear="${k}" aria-label="移除筛选 ${esc(label)}">${esc(label)}${svgIcon('close')}</button>`).join('');
}

/* ------------------------------------------------------------------ grid */
function pageSize() {
  if (state.tab === 'icon') return PAGE.icon;
  if (state.tab === 'paper' || state.tab === 'atomic') return PAGE.paper;
  return PAGE.mixed;
}

function card(it) {
  const saved = favorites.has(it.id);
  const save = `<button type="button" class="save${saved ? ' on' : ''}" data-save="${esc(it.id)}" aria-pressed="${saved}" aria-label="${saved ? '取消收藏' : '收藏'}">${svgIcon('bookmark')}</button>`;
  if (it.type === 'icon') {
    const art = it.mono
      ? `<span class="glyph" style="--src:url('${esc(it.src)}')" role="img" aria-label="${esc(it.name)}"></span>`
      : `<img src="${esc(it.src)}" alt="${esc(it.name)}" loading="lazy" decoding="async">`;
    return `<article class="card icon-card">${save}<button type="button" class="card-open" data-open="${esc(it.id)}"><div class="card-art">${art}</div><div class="card-body"><h3 class="card-title" title="${esc(it.name)} · ${esc(it.en)}">${esc(it.name)}</h3><div class="card-meta">${esc(it.packInfo.name)}</div></div></button></article>`;
  }
  const s = it.source || {};
  const venue = it.type === 'atomic' && (it.original || it.collection) ? it.category : (s.venue || '').replace(/\s*·.*$/, '');
  return `<article class="card">${save}<button type="button" class="card-open" data-open="${esc(it.id)}"><div class="card-art"><span class="kind ${it.type}">${it.type === 'atomic' ? (it.files.svg ? 'SVG' : 'PNG') : esc(shortFigure(it.figure))}</span><img src="${esc(it.thumb)}" alt="${esc(it.name)}" loading="lazy" decoding="async"></div><div class="card-body"><h3 class="card-title" title="${esc(it.name)}">${esc(it.type === 'atomic' ? it.name.replace(/\s·\s.*$/, '') : it.name)}</h3><div class="card-meta"><span class="model">${esc(s.short || '')}</span>${venue ? `<span class="dot"></span><span class="venue">${esc(venue)}</span>` : ''}</div></div></button></article>`;
}

// Card badge: "Fig. 3" / "Table 1" from labels such as "Figure 3 中间 adaLN-Zero".
function shortFigure(label) {
  const m = /(fig(?:ure)?\.?|table)\s*(\d+(?:\.\d+)?(?:\s*\([a-z](?:[-–][a-z])?\))?)/i.exec(label || '');
  return m ? `${/^t/i.test(m[1]) ? 'Table' : 'Fig.'} ${m[2].replace(/\s+/g, '')}` : '原图';
}

function render(keepScroll = false) {
  const base = compute();
  renderFacets(base);
  renderActive();
  const size = pageSize();
  if (!keepScroll) state.limit = size;
  const shown = results.slice(0, state.limit);
  const grid = $('grid');
  const onlyIcons = shown.length && shown.every(it => it.type === 'icon');
  grid.classList.toggle('icons', Boolean(onlyIcons));
  grid.innerHTML = shown.map(card).join('');
  grid.setAttribute('aria-busy', 'false');
  $('resultsTitle').textContent = TAB_NAMES[state.tab];
  const n = results.length;
  const parts = [`${fmt(n)} 项`];
  if (state.tab === 'all' && n) {
    const t = { paper: 0, atomic: 0, icon: 0 };
    results.forEach(it => { t[it.type] += 1; });
    parts.push(`图元 ${fmt(t.atomic)} · 论文原图 ${fmt(t.paper)} · 图标 ${fmt(t.icon)}`);
  }
  $('resultsSummary').textContent = n ? parts.join('，') : '没有匹配的素材';
  $('emptyState').hidden = Boolean(n);
  updateTabCounts();
  const elsewhere = Object.entries(tabCounts).filter(([tab, count]) => count && tab !== state.tab && tab !== 'all' && tab !== 'favorites');
  $('emptyJump').innerHTML = !n && state.q ? elsewhere.map(([tab, count]) =>
    `<button type="button" class="ghost-button" data-jump="${tab}">在「${TAB_NAMES[tab]}」中查看 ${fmt(count)} 项</button>`).join('') : '';
  if (!n && state.tab === 'favorites' && !state.q) {
    $('emptyState').querySelector('h3').textContent = '还没有收藏';
    $('emptyState').querySelector('p').textContent = '在卡片右上角点书签即可收藏，收藏保存在当前浏览器。';
  } else {
    $('emptyState').querySelector('h3').textContent = '没有找到匹配的素材';
    $('emptyState').querySelector('p').textContent = '换个关键词，或清除部分筛选条件。中英文名称、模型名、作者与标签都可以搜索。';
  }
  $('moreBar').hidden = shown.length >= n;
  $('moreHint').textContent = shown.length < n ? `已显示 ${fmt(shown.length)} / ${fmt(n)}` : '';
  document.querySelectorAll('[data-tab]').forEach(b => b.setAttribute('aria-selected', String(b.dataset.tab === state.tab)));
  document.querySelectorAll('[data-tab-link]').forEach(b => b.classList.toggle('active', b.dataset.tabLink === state.tab));
  $('gridColor').hidden = !(state.tab === 'icon' || state.tab === 'all' || state.tab === 'favorites');
  writeUrl();
}

function loadMore() {
  const grid = $('grid');
  const start = state.limit;
  state.limit += pageSize();
  const extra = results.slice(start, state.limit);
  grid.insertAdjacentHTML('beforeend', extra.map(card).join(''));
  if (extra.length && extra.every(it => it.type === 'icon') && !grid.classList.contains('icons') && start === 0) grid.classList.add('icons');
  $('moreBar').hidden = state.limit >= results.length;
  $('moreHint').textContent = state.limit < results.length ? `已显示 ${fmt(Math.min(state.limit, results.length))} / ${fmt(results.length)}` : '';
}

function syncControls() {
  $('searchInput').value = state.q;
  $('clearSearch').hidden = !state.q;
  $('onlyArch').checked = state.arch;
  $('onlyVector').checked = state.vector;
  $('onlyMono').checked = state.mono;
  $('onlyFeatured').checked = state.featured;
  $('sortSelect').value = state.sort;
  $('iconColor').value = state.color;
  document.documentElement.style.setProperty('--icon-color', state.color);
}

function setTab(tab) {
  state.tab = tab;
  state.category = '';
  if (tab !== 'icon' && tab !== 'all' && tab !== 'favorites') state.pack = '';
  if (tab === 'paper' || tab === 'icon') state.from = '';
  if (tab === 'icon') { state.arch = false; state.vector = false; }
  if (tab === 'paper' || tab === 'atomic') { state.mono = false; state.featured = false; }
  syncControls();
  render();
}

/* ------------------------------------------------------------------ detail */
function openDetail(it, push = true) {
  current = it;
  const drawer = $('drawer');
  const stage = $('stage');
  const isIcon = it.type === 'icon';
  stage.classList.toggle('icon', isIcon);
  setStageBg(isIcon && it.mono ? 'light' : 'light');
  const img = $('detailImage');
  img.alt = it.name;
  img.src = isIcon ? it.src : (it.files.png || it.thumb);
  $('openOriginal').href = isIcon ? it.src : (it.files.png || it.thumb);
  $('detailSize').textContent = isIcon ? `${it.packInfo.name} · SVG` : `${fmt(it.width)} × ${fmt(it.height)} px`;
  $('detailCrumb').textContent = isIcon ? `图标 / ${it.category}` : `${KIND_LABEL[it.type]} / ${it.category}`;
  $('detailTitle').textContent = it.name;
  $('detailEnglish').textContent = isIcon ? `${it.en} · ${it.id}` : `${it.en} · ${it.id}`;
  $('detailDescription').textContent = isIcon ? iconDescription(it) : (it.description || '');
  const badges = isIcon
    ? [[it.packInfo.name, 'accent'], [it.packInfo.style, ''], [it.mono ? '可改色' : '彩色', ''], [it.license || it.packInfo.license, '']]
    : it.original ? [['原创图元', 'accent'], [it.category, ''], ['可编辑 SVG', ''], ['CC0 1.0', '']]
    : it.collection ? [[it.source.short, 'accent'], [it.category, ''], [svgLabel(it), ''], [it.source.license_name, '']]
    : [[KIND_LABEL[it.type], 'accent'], [it.category, ''], [it.figure, ''], [it.source.license_name, licenseClass(it.source.license)]];
  if (!isIcon && it.architecture) badges.splice(2, 0, ['完整架构', '']);
  $('detailBadges').innerHTML = badges.filter(([t]) => t).map(([t, c]) => `<span class="${c}">${esc(t)}</span>`).join('');
  $('recolor').hidden = !(isIcon && it.mono);
  $('pngSize').hidden = !isIcon;
  if (isIcon && it.mono) { $('detailColor').value = state.color; renderSwatches(); applyDetailColor(); }
  renderActions(it);
  const caption = !isIcon && it.caption;
  $('detailCaption').hidden = !caption;
  if (caption) $('captionText').textContent = it.caption;
  renderSource(it);
  renderMeta(it);
  const tags = isIcon ? (it.tagText || '').split(' ').filter(Boolean) : it.tags;
  $('detailTags').innerHTML = [...new Set(tags)].slice(0, 14).map(t => `<button type="button" data-tag="${esc(t)}">${esc(t)}</button>`).join('');
  $('scrim').hidden = false;
  drawer.hidden = false;
  document.body.style.overflow = 'hidden';
  $('drawerBody').scrollTop = 0;
  if (push) history.replaceState(null, '', `${location.pathname}${location.search}#${encodeURIComponent(it.id)}`);
  $('closeDrawer').focus({ preventScroll: true });
}

function iconDescription(it) {
  const pack = it.packInfo;
  return `${pack.name}（${pack.style}）中的独立图标，分类为「${it.category}」。${it.mono ? '单色图标可改为任意颜色后下载 SVG 或 PNG。' : '彩色图标保留原始配色，可下载 SVG 或 PNG。'}`;
}
function svgLabel(it) {
  if (!it.files.svg) return 'PNG';
  return it.svgKind === 'mixed' ? 'SVG（含位图）' : '可编辑 SVG';
}
function licenseClass(id) { return /NC|ND|arXiv|publisher/i.test(id || '') ? 'warn' : ''; }

function renderActions(it) {
  const box = $('detailActions');
  const buttons = [];
  if (it.type === 'icon') {
    buttons.push(`<button type="button" class="primary-button" data-action="svg">${svgIcon('download')}下载 SVG</button>`);
    buttons.push(`<button type="button" class="ghost-button" data-action="png">${svgIcon('download')}下载 PNG</button>`);
    buttons.push(`<button type="button" class="ghost-button" data-action="copy-svg">${svgIcon('copy')}复制 SVG 代码</button>`);
  } else {
    buttons.push(`<a class="primary-button" href="${esc(it.files.png)}" download="${esc(fileName(it, 'png'))}">${svgIcon('download')}下载 PNG</a>`);
    if (it.files.svg) buttons.push(`<a class="ghost-button" href="${esc(it.files.svg)}" download="${esc(fileName(it, 'svg'))}">${svgIcon('download')}SVG${it.svgKind === 'mixed' ? '（含位图）' : ''}</a>`);
    if (it.files.pdf) buttons.push(`<a class="ghost-button" href="${esc(it.files.pdf)}" download="${esc(fileName(it, 'pdf'))}">${svgIcon('download')}PDF 矢量</a>`);
  }
  const saved = favorites.has(it.id);
  buttons.push(`<button type="button" class="ghost-button" data-action="favorite" aria-pressed="${saved}">${svgIcon('bookmark')}${saved ? '已收藏' : '收藏'}</button>`);
  box.innerHTML = buttons.join('');
}

function renderSource(it) {
  const card = $('sourceCard');
  if (it.type === 'icon') { card.hidden = true; return; }
  const s = it.source;
  card.hidden = false;
  card.querySelector('.cite').hidden = Boolean(it.original || it.collection);
  card.querySelector('h3').textContent = it.original ? '许可' : it.collection ? '来源与许可' : '来源';
  if (it.original) {
    $('sourceTitle').textContent = '研图原创图元 · CC0 1.0（公共领域）';
    $('sourceMeta').textContent = '可在论文、课件、海报中自由使用和修改，可商用，无需署名或引用。';
    $('sourceLinks').innerHTML = `<a href="${esc(s.license_url)}" target="_blank" rel="noopener noreferrer">${svgIcon('external')}CC0 1.0 说明</a>`
      + `<a href="${esc(it.files.svg)}" target="_blank" rel="noopener">${svgIcon('file')}查看 SVG 源文件</a>`;
    return;
  }
  if (it.collection) {
    $('sourceTitle').textContent = s.title;
    $('sourceMeta').textContent = `${(s.authors || []).join(', ')} · ${s.license_name}${licenseNote(s.license)}`;
    $('sourceLinks').innerHTML = [
      it.upstream && `<a href="${esc(it.upstream)}" target="_blank" rel="noopener noreferrer">${svgIcon('file')}${it.page ? `原幻灯片第 ${esc(it.page)} 页` : '原始文件'}</a>`,
      `<a href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">${svgIcon('link')}项目主页</a>`,
      `<a href="${esc(s.license_file || s.license_url)}" target="_blank" rel="noopener">${svgIcon('external')}${esc(s.license_name)} 许可</a>`
    ].filter(Boolean).join('');
    return;
  }
  $('sourceTitle').textContent = s.title;
  const authors = s.authors || [];
  const shown = authors.length > 6 ? authors.slice(0, 6).join(', ') + ' 等' : authors.join(', ');
  $('sourceMeta').textContent = [shown, s.venue].filter(Boolean).join(' · ');
  const links = [];
  if (s.url) links.push(`<a href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">${svgIcon('link')}论文主页</a>`);
  if (s.pdf) links.push(`<a href="${esc(s.pdf)}${it.page ? '#page=' + it.page : ''}" target="_blank" rel="noopener noreferrer">${svgIcon('file')}原文 PDF${it.page ? ' 第 ' + it.page + ' 页' : ''}</a>`);
  if (s.license_url) links.push(`<a href="${esc(s.license_url)}" target="_blank" rel="noopener noreferrer">${svgIcon('external')}${esc(s.license_name)}</a>`);
  $('sourceLinks').innerHTML = links.join('');
}

function renderMeta(it) {
  const rows = [];
  if (it.type === 'icon') {
    const p = it.packInfo;
    rows.push(['图标集', `<a href="${esc(p.homepage)}" target="_blank" rel="noopener noreferrer">${esc(p.name)}</a> · ${esc(p.version)}`]);
    rows.push(['许可', `<a href="${esc(p.license_file)}" target="_blank" rel="noopener">${esc(it.license || p.license)}</a>`]);
    if (it.author) rows.push(['作者', `${esc(it.author)}（使用时请署名）`]);
    rows.push(['文件', `<code>${esc(it.src)}</code>`]);
  } else if (it.original) {
    rows.push(['类别', esc(it.category)]);
    rows.push(['许可', 'CC0 1.0：可自由使用、修改、商用，无需署名']);
    rows.push(['编辑', 'SVG 中每个面、每个格子都是独立图形，可直接改色、增删格子或改尺寸']);
    rows.push(['格式', `SVG · PNG（${fmt(it.width)} × ${fmt(it.height)} px，透明背景）`]);
  } else if (it.collection) {
    const s = it.source;
    rows.push(['类别', esc(it.category)]);
    rows.push(['许可', `${esc(s.license_name)}${licenseNote(s.license)}`]);
    rows.push(['署名', `<code>${esc(s.attribution)}</code> <button type="button" class="link-button" data-action="copy-attribution">复制署名</button>`]);
    rows.push(['处理', esc(s.processing)]);
    rows.push(['格式', `${it.files.svg ? (it.svgKind === 'mixed' ? 'SVG（含嵌入位图）· ' : 'SVG · ') : ''}PNG（${fmt(it.width)} × ${fmt(it.height)} px）`]);
  } else {
    const s = it.source;
    if (it.figure) rows.push(['图号', esc(it.figure)]);
    rows.push(['许可', `${esc(s.license_name)}${licenseNote(s.license)}`]);
    if (it.type === 'atomic') {
      rows.push(['来源位置', it.page ? `原文第 ${esc(it.page)} 页插图` : '原文插图']);
      rows.push(['处理', it.files.svg ? '从原图中分离出这一组矢量路径，配色与形状未改动' : '按论文 PDF 中嵌入位图的原始分辨率导出，未重绘']);
    } else {
      rows.push(['裁剪', it.page ? `原文第 ${esc(it.page)} 页，按原样裁剪，未重绘或改色` : '按原样截取，未重绘或改色']);
    }
    const formats = ['PNG', it.files.svg ? 'SVG' : '', it.files.pdf ? 'PDF' : ''].filter(Boolean).join(' · ');
    rows.push(['格式', `${formats}（${fmt(it.width)} × ${fmt(it.height)} px）`]);
  }
  $('detailMeta').innerHTML = rows.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${v}</dd>`).join('');
}

function licenseNote(id) {
  if (/NC/.test(id)) return '：仅限非商业用途';
  if (/ND/.test(id)) return '：不得改编';
  if (id === 'arXiv' || id === 'publisher') return '：版权归作者或出版方，引用时注明出处';
  if (/CC0/.test(id)) return '：可自由使用，无需署名';
  if (/CC-BY-SA/.test(id)) return '：署名，改编后须以相同许可发布';
  if (/CC-BY|CC0|MIT|BSD/.test(id)) return '：署名后可再使用';
  return '';
}

function fileName(it, ext) {
  const base = `${it.id}_${it.name}`.replace(/[<>:"/\\|?*\u0000-\u001f]/g, '_').replace(/\s+/g, '-').slice(0, 120);
  return `${base}.${ext}`;
}

function closeDetail() {
  $('drawer').hidden = true;
  $('scrim').hidden = true;
  document.body.style.overflow = '';
  if (location.hash) history.replaceState(null, '', `${location.pathname}${location.search}`);
  current = null;
}

function step(delta) {
  if (!current) return;
  const index = results.findIndex(it => it.id === current.id);
  const next = results[index + delta];
  if (next) openDetail(next);
}

function setStageBg(bg) {
  $('stage').dataset.bg = bg;
  document.querySelectorAll('#stage [data-bg]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.bg === bg)));
}

function openFromHash() {
  const id = decodeURIComponent(location.hash.slice(1));
  if (id && byId.has(id)) openDetail(byId.get(id), false);
}

/* ------------------------------------------------------------------ icon colour & downloads */
const svgCache = new Map();
async function svgText(it) {
  if (!svgCache.has(it.src)) {
    svgCache.set(it.src, fetch(it.src).then(r => { if (!r.ok) throw new Error(`SVG ${r.status}`); return r.text(); })
      .catch(e => { svgCache.delete(it.src); throw e; }));
  }
  return svgCache.get(it.src);
}
async function coloredSvg(it, color) {
  let xml = await svgText(it);
  if (it.mono && color) xml = xml.replace(/currentColor/gi, color);
  return xml;
}
function renderSwatches() {
  const color = $('detailColor').value.toLowerCase();
  $('swatches').innerHTML = SWATCHES.map(c => `<button type="button" data-swatch="${c}" style="--c:${c}" aria-label="颜色 ${c}" aria-pressed="${c === color}"></button>`).join('');
}
let previewUrl = '';
async function applyDetailColor() {
  if (!current || current.type !== 'icon' || !current.mono) return;
  const it = current;
  const color = $('detailColor').value;
  try {
    const xml = await coloredSvg(it, color);
    if (current !== it) return;
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = URL.createObjectURL(new Blob([xml], { type: 'image/svg+xml' }));
    $('detailImage').src = previewUrl;
    if (color.toLowerCase() === '#ffffff') setStageBg('dark');
  } catch (e) { console.error(e); }
}
function triggerDownload(url, name, revoke = false) {
  const a = document.createElement('a');
  a.href = url; a.download = name; a.style.display = 'none';
  document.body.append(a); a.click(); a.remove();
  if (revoke) setTimeout(() => URL.revokeObjectURL(url), 30000);
}
async function downloadSvg(it) {
  const xml = await coloredSvg(it, it.mono ? $('detailColor').value : '');
  triggerDownload(URL.createObjectURL(new Blob([xml], { type: 'image/svg+xml' })), fileName(it, 'svg'), true);
  toast('已开始下载 SVG');
}
async function downloadPng(it) {
  const xml = await coloredSvg(it, it.mono ? $('detailColor').value : '');
  const doc = new DOMParser().parseFromString(xml, 'image/svg+xml');
  const svg = doc.documentElement;
  const vb = (svg.getAttribute('viewBox') || '').split(/[\s,]+/).map(Number);
  const ratio = vb.length === 4 && vb[2] > 0 && vb[3] > 0 ? vb[2] / vb[3] : 1;
  const size = pngSize;
  const w = ratio >= 1 ? size : Math.round(size * ratio);
  const h = ratio >= 1 ? Math.round(size / ratio) : size;
  svg.setAttribute('width', w); svg.setAttribute('height', h);
  const url = URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(svg)], { type: 'image/svg+xml' }));
  try {
    const img = await new Promise((resolve, reject) => { const i = new Image(); i.onload = () => resolve(i); i.onerror = reject; i.src = url; });
    const canvas = document.createElement('canvas');
    canvas.width = w; canvas.height = h;
    canvas.getContext('2d').drawImage(img, 0, 0, w, h);
    const blob = await new Promise((resolve, reject) => canvas.toBlob(b => b ? resolve(b) : reject(new Error('PNG')), 'image/png'));
    triggerDownload(URL.createObjectURL(blob), fileName(it, 'png'), true);
    toast(`已生成 ${w} × ${h} 透明 PNG`);
  } finally { URL.revokeObjectURL(url); }
}
async function copyText(text, message) {
  try { await navigator.clipboard.writeText(text); toast(message); }
  catch {
    const area = Object.assign(document.createElement('textarea'), { value: text });
    document.body.append(area); area.select();
    const ok = document.execCommand('copy'); area.remove();
    toast(ok ? message : '复制失败，请手动选择文本');
  }
}

/* ------------------------------------------------------------------ citations */
const JOURNAL = /(TPAMI|Nature|Science|JMLR|TMLR|Journal|Letters|Transactions|Computation|Proceedings of the IEEE|npj|ACM TOG|Distill|International Journal)/i;
function bibtex(it) {
  const s = it.source;
  const first = (s.authors?.[0] || 'anon').split(/\s+/).pop().normalize('NFKD').replace(/[^A-Za-z]/g, '').toLowerCase();
  const word = (s.title || '').toLowerCase().replace(/[^a-z0-9 ]/g, ' ').split(/\s+/).find(w => w.length > 3 && !['with', 'from', 'that', 'this', 'using', 'towards'].includes(w)) || 'paper';
  const key = `${first}${s.year || ''}${word}`;
  const venue = (s.venue || '').replace(/\s*\d{4}.*$/, '').trim();
  const lines = [`  title = {${s.title}}`, `  author = {${(s.authors || []).join(' and ')}}`, `  year = {${s.year || ''}}`];
  let type = 'misc';
  if (/^arXiv/i.test(s.venue || '') || !venue) {
    type = 'article';
    lines.push(`  journal = {arXiv preprint arXiv:${s.arxiv}}`);
  } else if (JOURNAL.test(venue)) {
    type = 'article'; lines.push(`  journal = {${venue}}`);
  } else {
    type = 'inproceedings'; lines.push(`  booktitle = {${venue.replace(/\s*Workshops?$/i, ' Workshops')}}`);
  }
  if (s.arxiv) lines.push(`  eprint = {${s.arxiv}}`, '  archivePrefix = {arXiv}');
  if (s.url) lines.push(`  url = {${s.url}}`);
  return `@${type}{${key},\n${lines.join(',\n')}\n}`;
}
function citation(it) {
  const s = it.source;
  const authors = s.authors || [];
  const names = authors.length > 3 ? `${authors.slice(0, 3).join(', ')}, et al.` : authors.join(', ');
  return `${names}. ${s.title}. ${s.venue}. ${s.url}（${it.figure}）`;
}

/* ------------------------------------------------------------------ misc */
let toastTimer = 0;
function toast(message) {
  clearTimeout(toastTimer);
  $('toast').textContent = message;
  $('toast').hidden = false;
  toastTimer = setTimeout(() => { $('toast').hidden = true; }, 2600);
}
function toggleFavorite(id) {
  if (favorites.has(id)) favorites.delete(id); else favorites.add(id);
  store.set(FAVORITES_KEY, [...favorites]);
  updateTabCounts();
  document.querySelectorAll(`[data-save="${CSS.escape(id)}"]`).forEach(b => {
    const on = favorites.has(id);
    b.classList.toggle('on', on); b.setAttribute('aria-pressed', String(on)); b.setAttribute('aria-label', on ? '取消收藏' : '收藏');
  });
  if (current?.id === id) renderActions(current);
  if (state.tab === 'favorites') render(true);
}
function resetFilters() {
  Object.assign(state, { q: '', category: '', pack: '', from: '', arch: false, vector: false, mono: false, featured: false, sort: 'relevance' });
  syncControls();
  render();
}

/* ------------------------------------------------------------------ events */
$('searchInput').addEventListener('input', e => {
  clearTimeout(searchTimer);
  state.q = e.target.value.trim();
  $('clearSearch').hidden = !state.q;
  searchTimer = setTimeout(() => render(), 140);
});
$('searchForm').addEventListener('submit', e => { e.preventDefault(); $('results').scrollIntoView({ behavior: 'smooth' }); });
$('clearSearch').addEventListener('click', () => { state.q = ''; syncControls(); render(); $('searchInput').focus(); });
document.querySelectorAll('[data-query]').forEach(b => b.addEventListener('click', () => {
  state.q = b.dataset.query; syncControls(); render(); $('results').scrollIntoView({ behavior: 'smooth' });
}));
document.querySelectorAll('[data-tab]').forEach(b => b.addEventListener('click', () => setTab(b.dataset.tab)));
document.querySelectorAll('[data-tab-link]').forEach(b => b.addEventListener('click', () => { setTab(b.dataset.tabLink); $('tabs').scrollIntoView({ behavior: 'smooth' }); }));
$('openFavorites').addEventListener('click', () => { setTab('favorites'); $('tabs').scrollIntoView({ behavior: 'smooth' }); });
$('categoryFacet').addEventListener('click', e => {
  const b = e.target.closest('[data-category]'); if (!b) return;
  state.category = state.category === b.dataset.category ? '' : b.dataset.category; render();
});
$('packFacet').addEventListener('click', e => {
  const b = e.target.closest('[data-pack]'); if (!b) return;
  state.pack = state.pack === b.dataset.pack ? '' : b.dataset.pack; render();
});
$('fromFacet').addEventListener('click', e => {
  const b = e.target.closest('[data-from]'); if (!b) return;
  state.from = state.from === b.dataset.from ? '' : b.dataset.from; render();
});
$('detailMeta').addEventListener('click', e => {
  if (e.target.closest('[data-action="copy-attribution"]') && current) copyText(current.source.attribution, '已复制署名');
});
[['onlyArch', 'arch'], ['onlyVector', 'vector'], ['onlyMono', 'mono'], ['onlyFeatured', 'featured']].forEach(([id, key]) => {
  $(id).addEventListener('change', e => { state[key] = e.target.checked; render(); });
});
$('sortSelect').addEventListener('change', e => { state.sort = e.target.value; render(); });
$('iconColor').addEventListener('input', e => {
  state.color = e.target.value;
  document.documentElement.style.setProperty('--icon-color', state.color);
  store.set('figure-atlas-color', state.color);
});
$('resetFilters').addEventListener('click', resetFilters);
$('emptyJump').addEventListener('click', e => {
  const b = e.target.closest('[data-jump]'); if (!b) return;
  const q = state.q; setTab(b.dataset.jump); state.q = q; syncControls(); render();
});
$('emptyReset').addEventListener('click', () => { if (state.tab === 'favorites' && !favorites.size) setTab('all'); else resetFilters(); });
$('retryLoad').addEventListener('click', load);
$('loadMore').addEventListener('click', loadMore);
$('activeFilters').addEventListener('click', e => {
  const b = e.target.closest('[data-clear]'); if (!b) return;
  const k = b.dataset.clear;
  if (k === 'q') state.q = ''; else if (typeof state[k] === 'boolean') state[k] = false; else state[k] = '';
  syncControls(); render();
});
$('grid').addEventListener('click', e => {
  const save = e.target.closest('[data-save]');
  if (save) { toggleFavorite(save.dataset.save); return; }
  const open = e.target.closest('[data-open]');
  if (open) openDetail(byId.get(open.dataset.open));
});
$('closeDrawer').addEventListener('click', closeDetail);
$('scrim').addEventListener('click', () => { closeDetail(); $('sidebar').classList.remove('open'); });
$('prevItem').addEventListener('click', () => step(-1));
$('nextItem').addEventListener('click', () => step(1));
document.querySelectorAll('#stage [data-bg]').forEach(b => b.addEventListener('click', () => setStageBg(b.dataset.bg)));
$('detailColor').addEventListener('input', () => { renderSwatches(); applyDetailColor(); });
$('swatches').addEventListener('click', e => {
  const b = e.target.closest('[data-swatch]'); if (!b) return;
  $('detailColor').value = b.dataset.swatch; renderSwatches(); applyDetailColor();
});
document.querySelectorAll('#pngSize [data-size]').forEach(b => b.addEventListener('click', () => {
  pngSize = Number(b.dataset.size);
  document.querySelectorAll('#pngSize [data-size]').forEach(x => x.setAttribute('aria-pressed', String(x === b)));
}));
$('detailActions').addEventListener('click', async e => {
  const b = e.target.closest('[data-action]'); if (!b || !current) return;
  const it = current;
  try {
    if (b.dataset.action === 'svg') await downloadSvg(it);
    else if (b.dataset.action === 'png') { b.disabled = true; await downloadPng(it); }
    else if (b.dataset.action === 'copy-svg') await copyText(await coloredSvg(it, it.mono ? $('detailColor').value : ''), '已复制 SVG 代码');
    else if (b.dataset.action === 'favorite') toggleFavorite(it.id);
  } catch (error) { console.error(error); toast('操作失败，请重试'); }
  finally { b.disabled = false; }
});
$('copyBibtex').addEventListener('click', () => current && copyText(bibtex(current), '已复制 BibTeX'));
$('copyCitation').addEventListener('click', () => current && copyText(citation(current), '已复制引用'));
$('detailTags').addEventListener('click', e => {
  const b = e.target.closest('[data-tag]'); if (!b) return;
  closeDetail(); state.q = b.dataset.tag; syncControls(); render(); $('results').scrollIntoView({ behavior: 'smooth' });
});
$('openSidebar').addEventListener('click', () => { $('sidebar').classList.add('open'); $('scrim').hidden = false; });
$('closeSidebar').addEventListener('click', () => { $('sidebar').classList.remove('open'); if ($('drawer').hidden) $('scrim').hidden = true; });
document.addEventListener('keydown', e => {
  const typing = ['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName);
  if (e.key === '/' && !typing && $('drawer').hidden) { e.preventDefault(); $('searchInput').focus(); }
  if (e.key === 'Escape') { if (!$('drawer').hidden) closeDetail(); else if ($('sidebar').classList.contains('open')) $('closeSidebar').click(); }
  if (!$('drawer').hidden && !typing && (e.key === 'ArrowRight' || e.key === 'ArrowLeft')) step(e.key === 'ArrowRight' ? 1 : -1);
});
window.addEventListener('hashchange', openFromHash);
window.addEventListener('storage', e => {
  if (e.key !== FAVORITES_KEY) return;
  favorites = new Set((store.get(FAVORITES_KEY, []) || []).map(String));
  updateTabCounts();
  if (state.tab === 'favorites') render(true);
});
const observer = 'IntersectionObserver' in window ? new IntersectionObserver(entries => {
  if (entries.some(en => en.isIntersecting) && !$('moreBar').hidden && results.length > state.limit && state.limit < 2000) loadMore();
}, { rootMargin: '600px' }) : null;
if (observer) observer.observe($('moreBar'));

load();
