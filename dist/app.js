'use strict';

const ICONS = {
  search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4 4"/>',
  bookmark: '<path d="M6 4.5A1.5 1.5 0 0 1 7.5 3h9A1.5 1.5 0 0 1 18 4.5V21l-6-4-6 4Z"/>',
  download: '<path d="M12 3v12m-4-4 4 4 4-4M4 16v4a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-4"/>',
  close: '<path d="m6 6 12 12M6 18 18 6"/>',
  layers: '<path d="m12 3 9 5-9 5-9-5 9-5Zm-9 9 9 5 9-5M3 16l9 5 9-5"/>',
  link: '<path d="m9 15 6-6m-8 4-1 1a4 4 0 0 0 6 6l3-3a4 4 0 0 0 0-6M9 13a4 4 0 0 1 0-6l3-3a4 4 0 0 1 6 6l-1 1"/>',
  external: '<path d="M14 3h7v7m0-7L11 13m-1-8H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-5"/>',
  left: '<path d="m14 6-6 6 6 6"/>',
  right: '<path d="m10 6 6 6-6 6"/>',
  document: '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9Zm0 0v6h6M8 13h8m-8 4h5"/>'
};
const icon = name => `<svg viewBox="0 0 24 24" aria-hidden="true">${ICONS[name] || ICONS.document}</svg>`;
document.querySelectorAll('[data-icon]').forEach(el => { el.innerHTML = icon(el.dataset.icon); });

const $ = id => document.getElementById(id);
const TYPE_NAMES = {icon:'独立图标',atomic:'小图元',paper:'论文配图',architecture:'架构示意图'};
const COLLECTION_NAMES = {featured:'论文常用',all:'全部素材',architecture:'经典架构',paper:'论文配图',atomic:'小图元',icon:'独立图标',favorites:'我的收藏'};
const STORAGE_KEY = 'paper-elements-favorites-v1';
let favorites;
try { favorites = new Set(JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]').map(String)); }
catch { favorites = new Set(); }
const state = {collection:'featured',query:'',category:'',style:'',svgOnly:false,pdfOnly:false,sort:'recommended',page:1,pageSize:96};
const urlParams = new URLSearchParams(location.search);
if (urlParams.get('q')) state.query = urlParams.get('q');
if (COLLECTION_NAMES[urlParams.get('collection')]) state.collection = urlParams.get('collection');
let assets = [], filtered = [], catalog = {}, activeAsset = null, toastTimer, searchTimer;
let previewBlob = '', previewSequence = 0, selectedColor = '#334155';
const svgCache = new Map();
const number = value => Number(value || 0).toLocaleString('zh-CN');
const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const normalize = value => String(value ?? '').normalize('NFKC').toLocaleLowerCase().replace(/[_-]+/g,' ').trim();
const isSourceOnly = a => a.source_only === true || a.available === false || (!a.preview && !a.svg && !a.png && !a.pdf);
const isRecolorable = a => a.type === 'icon' && (['tabler','phosphor'].includes(a.pack) || String(a.style).startsWith('Tabler'));
const canExportPng = a => !!a.svg && ['icon','architecture'].includes(a.type);
function pngDimensions(a) {
  if(a.type !== 'architecture') return {width:512,height:512,padding:16};
  const width=Number(a.width)||1600,height=Number(a.height)||900;
  const scale=1984/Math.max(width,height);
  return {width:Math.round(width*scale)+64,height:Math.round(height*scale)+64,padding:32};
}
const imagePath = a => a.preview || a.png || a.svg || '';
function svgLabel(a) {
  if (!a.svg) return '';
  if (a.svg_kind === 'raster_container' || String(a.svg_kind).includes('raster_container')) return 'SVG 位图封装';
  if (a.svg_kind === 'mixed' || String(a.svg_kind).includes('embedded_raster')) return 'SVG 混合内容';
  if (a.type === 'icon' || a.svg_kind === 'vector' || String(a.svg_kind).includes('vector_paths')) return '矢量 SVG';
  return 'SVG 文件';
}
function showToast(message) {
  clearTimeout(toastTimer); $('toast').textContent = message; $('toast').hidden = false;
  toastTimer = setTimeout(() => { $('toast').hidden = true; }, 3200);
}
function saveFavorites() {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify([...favorites])); }
  catch { showToast('收藏已保留在本次浏览中；当前浏览器无法写入本地存储。'); }
}
function toggleFavorite(id) {
  if (favorites.has(id)) favorites.delete(id); else favorites.add(id);
  saveFavorites(); updateCounts();
  document.querySelectorAll('[data-favorite-id]').forEach(button => {
    if (button.dataset.favoriteId !== id) return;
    const saved = favorites.has(id); button.classList.toggle('saved',saved);
    button.setAttribute('aria-pressed',String(saved)); button.setAttribute('aria-label',saved?'取消收藏':'加入收藏');
  });
  if (activeAsset?.id === id) updateDetailFavorite();
  if (state.collection === 'favorites') applyFilters();
}
function scopeAssets() {
  switch (state.collection) {
    case 'featured': return assets.filter(a => a.featured);
    case 'favorites': return assets.filter(a => favorites.has(a.id));
    case 'all': return assets;
    case 'architecture': return assets.filter(a => a.architecture || a.type === 'architecture');
    default: return assets.filter(a => a.type === state.collection);
  }
}
function updateCounts() {
  const counts = {all:assets.length,featured:assets.filter(a=>a.featured).length,architecture:assets.filter(a=>a.architecture||a.type==='architecture').length,paper:assets.filter(a=>a.type==='paper').length,atomic:assets.filter(a=>a.type==='atomic').length,icon:assets.filter(a=>a.type==='icon').length,favorites:assets.filter(a=>favorites.has(a.id)).length};
  document.querySelectorAll('[data-collection]').forEach(button => {
    const count = button.querySelector('span:not([data-icon])'); if (count) count.textContent = number(counts[button.dataset.collection]);
  });
  $('headerFavoriteCount').textContent = number(counts.favorites);
  $('totalCount').textContent = number(assets.length);
  const sourceOnly = assets.filter(isSourceOnly).length;
  $('availabilityNote').hidden = !sourceOnly;
  $('availabilityNote').textContent = `${number(assets.length-sourceOnly)} 项可下载 · ${number(sourceOnly)} 项论文来源档案（原配图保存在本地版）`;
}
function updateTabs() {
  document.querySelectorAll('[data-collection]').forEach(button => {
    const active = button.dataset.collection === state.collection;
    button.classList.toggle('active', active);
    if (active) button.setAttribute('aria-current','page'); else button.removeAttribute('aria-current');
  });
  $('resultsTitle').textContent = COLLECTION_NAMES[state.collection];
}
function populateFilters() {
  const scope = scopeAssets();
  [['category','categoryFilter','全部分类'],['style','styleFilter','全部风格']].forEach(([key,id,title])=>{
    const counts = new Map(); scope.forEach(a=>{if(a[key]) counts.set(a[key],(counts.get(a[key])||0)+1);});
    if (state[key] && !counts.has(state[key])) state[key] = '';
    const select=$(id); select.replaceChildren(new Option(title,''));
    [...counts.entries()].sort((a,b)=>a[0].localeCompare(b[0],'zh-CN')).forEach(([value,count])=>select.add(new Option(`${value} · ${number(count)}`,value)));
    select.value=state[key];
  });
}
function setCollection(value,clear=false) {
  state.collection=value; state.page=1;
  if(clear) {state.query=''; state.category='';state.style='';state.svgOnly=false;state.pdfOnly=false;}
  syncInputs(); updateTabs(); populateFilters(); applyFilters();
}
function syncInputs() {
  $('searchInput').value=state.query; $('clearSearch').hidden=!state.query;
  $('categoryFilter').value=state.category; $('styleFilter').value=state.style;
  $('svgOnly').checked=state.svgOnly; $('pdfOnly').checked=state.pdfOnly;
  $('sortSelect').value=state.sort; $('pageSize').value=String(state.pageSize);
}
function resetFilters() {
  state.query='';state.category='';state.style='';state.svgOnly=false;state.pdfOnly=false;state.page=1;
  syncInputs(); applyFilters();
}
function applyFilters() {
  const tokens=normalize(state.query).split(/\s+/).filter(Boolean);
  filtered=scopeAssets().filter(a=>(!state.category||a.category===state.category)&&(!state.style||a.style===state.style)&&(!state.svgOnly||!!a.svg)&&(!state.pdfOnly||!!a.pdf)&&tokens.every(token=>a._search.includes(token)));
  if(state.sort==='name') filtered.sort((a,b)=>a.name.localeCompare(b.name,'zh-CN'));
  else filtered.sort((a,b)=>Number(b.featured)-Number(a.featured)||a._order-b._order);
  state.page=Math.min(state.page,Math.max(1,Math.ceil(filtered.length/state.pageSize)));
  renderActiveFilters(); renderResults();
}
function renderActiveFilters() {
  const tags=[];
  if(state.query) tags.push(['query',`搜索：${state.query}`]);
  if(state.category) tags.push(['category',state.category]);
  if(state.style) tags.push(['style',state.style]);
  if(state.svgOnly) tags.push(['svgOnly','包含 SVG']);
  if(state.pdfOnly) tags.push(['pdfOnly','包含 PDF']);
  const container=$('activeFilters');container.replaceChildren();container.hidden=!tags.length;
  tags.forEach(([key,label])=>{const button=document.createElement('button');button.type='button';button.innerHTML=`${escapeHTML(label)}${icon('close')}`;button.setAttribute('aria-label',`移除筛选：${label}`);button.onclick=()=>{state[key]=key.endsWith('Only')?false:'';state.page=1;syncInputs();applyFilters();};container.append(button);});
}
function createCard(a) {
  const sourceOnly=isSourceOnly(a);const saved=favorites.has(a.id);
  const card=document.createElement('article');card.className=`asset-card${sourceOnly?' source-only':''}`;
  const formats=sourceOnly?['来源']:['PNG',...(a.svg?['SVG']:[]),...(a.pdf?['PDF']:[])];
  card.innerHTML=`<button class="card-open" type="button"><div class="card-preview ${escapeHTML(a.type)}"><span class="card-type">${escapeHTML(TYPE_NAMES[a.type]||'素材')}</span>${imagePath(a)?`<img src="${escapeHTML(imagePath(a))}" alt="" loading="lazy" decoding="async">`:`<span class="source-placeholder">${icon('document')}<span>论文来源</span></span>`}</div><div class="card-body"><h3 class="card-name">${escapeHTML(a.name)}</h3><div class="card-category" title="${escapeHTML(a.category+' · '+a.style)}">${escapeHTML(a.category||a.style)}</div></div></button><button class="card-save${saved?' saved':''}" type="button" data-favorite-id="${escapeHTML(a.id)}" aria-label="${saved?'取消收藏':'加入收藏'}" aria-pressed="${saved}">${icon('bookmark')}</button><div class="card-footer"><div class="card-formats">${formats.map(f=>`<span>${f}</span>`).join('')}</div><button class="card-download" type="button" aria-label="${sourceOnly?'查看来源':'下载 '+escapeHTML(a.name)}">${icon(sourceOnly?'external':'download')}</button></div>`;
  card.querySelector('.card-open').onclick=()=>openDetail(a);
  card.querySelector('.card-save').onclick=()=>toggleFavorite(a.id);
  card.querySelector('.card-download').onclick=async event=>{if(sourceOnly){openDetail(a);return;}const button=event.currentTarget;button.disabled=true;try{await downloadAsset(a,canExportPng(a)?'svg':a.png?'png':a.svg?'svg':'pdf');}catch(error){console.error(error);showToast('下载暂时失败，请重试或查看原始来源。');}finally{button.disabled=false;}};
  const img=card.querySelector('img');if(img) img.addEventListener('error',()=>card.classList.add('is-broken'),{once:true});
  return card;
}
function renderResults() {
  const start=(state.page-1)*state.pageSize;const items=filtered.slice(start,start+state.pageSize);
  const grid=$('assetGrid');grid.replaceChildren();grid.setAttribute('aria-busy','false');grid.classList.toggle('architecture-grid',state.collection==='architecture');
  const fragment=document.createDocumentFragment();items.forEach(a=>fragment.append(createCard(a)));grid.append(fragment);
  const sourceOnly=filtered.filter(isSourceOnly).length;
  $('resultsSummary').textContent=filtered.length?`找到 ${number(filtered.length)} 个条目${sourceOnly?` · ${number(sourceOnly)} 项来源档案`:''} · 当前 ${number(start+1)}–${number(start+items.length)}`:'没有匹配的素材';
  $('emptyState').hidden=!!filtered.length;
  if(!filtered.length&&state.collection==='favorites'&&!state.query&&!state.category&&!state.style&&!state.svgOnly&&!state.pdfOnly){$('emptyState').querySelector('h3').textContent='把喜欢的图元，留在这里';$('emptyState').querySelector('p').textContent='点击素材右上角的收藏按钮，下次回来就能快速找到。';$('emptyReset').textContent='浏览论文常用';}
  else {$('emptyState').querySelector('h3').textContent='还没有找到合适的素材';$('emptyState').querySelector('p').textContent='试试更短的关键词，或清除一些筛选条件。';$('emptyReset').textContent='清除筛选';}
  renderPagination();
}
function renderPagination() {
  const nav=$('pagination');nav.replaceChildren();const total=Math.ceil(filtered.length/state.pageSize);if(total<=1)return;
  function addPage(label,page,disabled=false,active=false,direction='') {const button=document.createElement('button');button.type='button';button.disabled=disabled;button.className=active?'active':direction?'page-direction':'';button.innerHTML=direction==='left'?icon('left')+label:direction==='right'?label+icon('right'):label;button.setAttribute('aria-label',direction?label:`第 ${page} 页`);if(active)button.setAttribute('aria-current','page');button.onclick=()=>{state.page=page;renderResults();$('resultsPanel').scrollIntoView({behavior:'smooth',block:'start'});};nav.append(button);}
  addPage('上一页',state.page-1,state.page===1,false,'left');
  const pages=new Set([1,total,state.page-2,state.page-1,state.page,state.page+1,state.page+2]);let last=0;
  [...pages].filter(p=>p>=1&&p<=total).sort((a,b)=>a-b).forEach(p=>{if(last&&p-last>1){const dots=document.createElement('span');dots.className='page-dots';dots.textContent='…';nav.append(dots);}addPage(String(p),p,false,p===state.page);last=p;});
  addPage('下一页',state.page+1,state.page===total,false,'right');
  const detail=document.createElement('div');detail.className='page-detail';detail.textContent=`第 ${state.page} / ${total} 页 · 每页 ${state.pageSize} 个`;nav.append(detail);
}
function fillHero() {
  const fluent=assets.filter(a=>a.type==='icon'&&String(a.style).includes('Fluent')&&imagePath(a));
  const needles=['brain','robot','microscope','satellite','cloud with rain','dna'];
  const selected=needles.map(needle=>fluent.find(a=>normalize(a.english)===needle)).filter(Boolean);
  if(selected.length<6) for(const a of assets.filter(a=>a.type==='icon'&&a.featured&&imagePath(a))){if(!selected.includes(a))selected.push(a);if(selected.length===6)break;}
  const art=$('heroArt');art.querySelectorAll('.sample-tile').forEach(el=>el.remove());
  selected.slice(0,6).forEach(a=>{const tile=document.createElement('div');tile.className='sample-tile';const img=document.createElement('img');img.src=imagePath(a);img.alt='';img.decoding='async';tile.append(img);art.insertBefore(tile,art.querySelector('.art-caption'));});
}
function updateDetailFavorite() {
  if(!activeAsset)return;const button=$('detailFavorite');const saved=favorites.has(activeAsset.id);
  button.classList.toggle('saved',saved);button.setAttribute('aria-pressed',String(saved));button.querySelector('span:last-child').textContent=saved?'已收藏 · 点击取消':'加入收藏';
}
function setPreviewBackground(background) {
  const stage=$('previewStage');stage.classList.remove('checker','light','dark');stage.classList.add(background);
  document.querySelectorAll('[data-background]').forEach(b=>{const selected=b.dataset.background===background;b.classList.toggle('selected',selected);b.setAttribute('aria-pressed',String(selected));});
}
function releasePreview() {if(previewBlob){URL.revokeObjectURL(previewBlob);previewBlob='';}}
async function updateColorPreview() {
  const a=activeAsset;if(!a||!isRecolorable(a)||!a.svg)return;const sequence=++previewSequence;
  $('colorValue').textContent=selectedColor;$('iconColor').value=selectedColor;
  try {const xml=await prepareSvg(a,selectedColor);if(sequence!==previewSequence||activeAsset?.id!==a.id)return;releasePreview();previewBlob=URL.createObjectURL(new Blob([xml],{type:'image/svg+xml;charset=utf-8'}));$('detailImage').src=previewBlob;}
  catch(error){console.error(error);showToast('颜色预览暂时不可用，仍可下载原始 SVG。');}
}
function openDetail(a) {
  activeAsset=a;previewSequence++;releasePreview();selectedColor='#334155';setPreviewBackground('checker');
  const sourceOnly=isSourceOnly(a);const stage=$('previewStage');stage.classList.toggle('icon',a.type==='icon');stage.querySelector('.detail-source-placeholder')?.remove();
  const img=$('detailImage');img.hidden=!imagePath(a);img.alt=a.name;
  if(imagePath(a))img.src=imagePath(a);else {img.removeAttribute('src');const placeholder=document.createElement('div');placeholder.className='detail-source-placeholder';placeholder.innerHTML=`${icon('document')}<strong>论文来源档案</strong><p>此配图仅保存在本地，<br>公开版本提供论文来源。</p>`;stage.append(placeholder);}
  $('detailTitle').textContent=a.name;$('detailEnglish').textContent=a.english||a.id;
  $('detailBreadcrumb').textContent=`${TYPE_NAMES[a.type]||'素材'} / ${a.category||a.style||'来源档案'}`;
  $('detailDescription').textContent=sourceOnly?'此配图仅保存在本地，公开版本提供论文来源。可通过下方链接查看原论文及使用条件。':a.description||a.usage||(a.type==='icon'?'独立图标，可用于表示对象、设备、数据或应用场景。':'从原论文提取的图元，具体使用条件请查看原始来源。');
  $('detailBadges').innerHTML=[TYPE_NAMES[a.type],a.style,sourceOnly?'来源档案':svgLabel(a)].filter(Boolean).map(t=>`<span>${escapeHTML(t)}</span>`).join('');
  $('previewDimensions').textContent=a.width&&a.height&&!sourceOnly?`${a.width} × ${a.height}${canExportPng(a)?' · SVG':' px'}`:'';
  const tagContainer=$('detailTags');tagContainer.replaceChildren();[...new Set(a.tags||[])].filter(t=>t&&t!==a.name&&t!==a.english).slice(0,10).forEach(tag=>{const button=document.createElement('button');button.type='button';button.textContent=tag;button.title='搜索此标签';button.onclick=()=>{$('assetDialog').close();state.query=tag;state.page=1;syncInputs();applyFilters();$('resultsPanel').scrollIntoView({behavior:'smooth'});};tagContainer.append(button);});
  const downloads=$('downloadActions');downloads.replaceChildren();downloads.hidden=sourceOnly;
  if(!sourceOnly) ['png','svg','pdf'].filter(format=>a[format]||(format==='png'&&canExportPng(a))).forEach((format,index)=>{const button=document.createElement('button');button.type='button';button.className='button'+(index===0?' primary':'');button.innerHTML=icon('download')+`下载 ${format.toUpperCase()}`;button.onclick=async()=>{button.disabled=true;try{await downloadAsset(a,format,selectedColor);}catch(error){console.error(error);showToast('下载暂时失败，请重试或查看原始来源。');}finally{button.disabled=false;}};downloads.append(button);});
  const metadata=[['素材编号',a.id],['分类',a.category],['出处',a.source_title],['论文信息',[a.year,a.figure].filter(Boolean).join(' · ')],['许可',a.license_note||a.license||'以原始来源为准'],['SVG 类型',svgLabel(a)]];
  const dl=$('detailMetadata');dl.replaceChildren();metadata.filter(([,value])=>value).forEach(([label,value])=>{const dt=document.createElement('dt');dt.textContent=label;const dd=document.createElement('dd');dd.textContent=value;if(label==='许可'&&a.license_url){const link=document.createElement('a');link.href=a.license_url;link.target='_blank';link.rel='noopener';link.textContent=value;dd.replaceChildren(link);}dl.append(dt,dd);});
  const source=$('detailSource');source.hidden=!a.source_url;if(a.source_url)source.href=a.source_url;else source.removeAttribute('href');
  let svgNote='';
  if(a.svg_kind==='raster_container'||String(a.svg_kind).includes('raster_container'))svgNote='此 SVG 是位图封装，用于保持原图外观；放大后的清晰度仍受原 PNG 分辨率限制。';
  else if(a.svg_kind==='mixed'||String(a.svg_kind).includes('embedded_raster'))svgNote='此 SVG 同时包含矢量与位图内容，其中的位图部分受原始分辨率限制。';
  if(a.svg_note&&!svgNote)svgNote=a.svg_note;
  $('svgNote').textContent=svgNote;$('svgNote').hidden=!svgNote;
  $('colorEditor').hidden=!isRecolorable(a)||sourceOnly;
  updateDetailFavorite();if(!$('assetDialog').open)$('assetDialog').showModal();$('assetDialog').scrollTop=0;
  if(isRecolorable(a)&&!sourceOnly)updateColorPreview();
}
async function fetchSvg(a) {
  if(!svgCache.has(a.svg))svgCache.set(a.svg,fetch(a.svg).then(response=>{if(!response.ok)throw new Error(`SVG ${response.status}`);return response.text();}).catch(error=>{svgCache.delete(a.svg);throw error;}));
  return svgCache.get(a.svg);
}
async function prepareSvg(a,color,forPng=false) {
  let xml=await fetchSvg(a);
  if(isRecolorable(a)&&color)xml=xml.replace(/currentColor/gi,color);
  const doc=new DOMParser().parseFromString(xml,'image/svg+xml');
  if(doc.querySelector('parsererror'))throw new Error('Invalid SVG');
  const svg=doc.documentElement;
  if(forPng){const size=pngDimensions(a);svg.setAttribute('width',String(size.width-size.padding*2));svg.setAttribute('height',String(size.height-size.padding*2));}
  return new XMLSerializer().serializeToString(svg);
}
function downloadName(a,format) {return `${a.id}_${a.name||a.english}`.replace(/[<>:"/\\|?*\u0000-\u001f]/g,'_').slice(0,160)+'.'+format;}
function triggerDownload(url,name,temporary=false) {
  const link=document.createElement('a');link.href=url;link.download=name;link.style.display='none';document.body.append(link);link.click();link.remove();
  if(temporary)setTimeout(()=>URL.revokeObjectURL(url),60000);
}
async function downloadAsset(a,format,color='') {
  if(isSourceOnly(a))return;
  if(format==='png'&&!a.png&&canExportPng(a)) {
    const xml=await prepareSvg(a,color,true);const url=URL.createObjectURL(new Blob([xml],{type:'image/svg+xml;charset=utf-8'}));
    try {const image=await new Promise((resolve,reject)=>{const img=new Image();img.onload=()=>resolve(img);img.onerror=()=>reject(new Error('SVG rasterization failed'));img.src=url;});
      const size=pngDimensions(a);const canvas=document.createElement('canvas');canvas.width=size.width;canvas.height=size.height;const context=canvas.getContext('2d');if(!context)throw new Error('Canvas unavailable');
      context.clearRect(0,0,size.width,size.height);context.drawImage(image,size.padding,size.padding,size.width-size.padding*2,size.height-size.padding*2);
      const blob=await new Promise((resolve,reject)=>canvas.toBlob(value=>value?resolve(value):reject(new Error('PNG export failed')),'image/png'));
      triggerDownload(URL.createObjectURL(blob),downloadName(a,'png'),true);
    }finally{URL.revokeObjectURL(url);}
  } else if(format==='svg'&&isRecolorable(a)&&color) {
    const xml=await prepareSvg(a,color);triggerDownload(URL.createObjectURL(new Blob([xml],{type:'image/svg+xml;charset=utf-8'})),downloadName(a,'svg'),true);
  } else if(a[format])triggerDownload(a[format],downloadName(a,format));
  else throw new Error('Format unavailable');
  const size=pngDimensions(a);showToast(format==='png'&&!a.png?`已生成 ${size.width} × ${size.height} 透明 PNG`:'已开始下载 '+format.toUpperCase());
}
function showSkeletons() {
  $('assetGrid').innerHTML=Array.from({length:18},()=>'<div class="skeleton-card" aria-hidden="true"></div>').join('');$('assetGrid').setAttribute('aria-busy','true');
}
async function loadCatalog() {
  $('loadError').hidden=true;$('emptyState').hidden=true;showSkeletons();
  try {
    const response=await fetch('data.json');if(!response.ok)throw new Error(`HTTP ${response.status}`);catalog=await response.json();const rows=Array.isArray(catalog)?catalog:catalog.assets;
    if(!Array.isArray(rows))throw new Error('素材索引格式不正确');
    assets=rows.map((row,index)=>{const a={...row,id:String(row.id),name:String(row.name||row.english||row.id),tags:Array.isArray(row.tags)?row.tags:[],_order:index};a._search=normalize([a.id,a.name,a.english,a.category,a.style,a.description,a.usage,a.source_title,a.source_url,a.figure,a.year,...a.tags].filter(Boolean).join(' '));return a;});
    updateCounts();updateTabs();populateFilters();syncInputs();fillHero();applyFilters();
  } catch(error) {
    console.error(error);$('assetGrid').replaceChildren();$('assetGrid').setAttribute('aria-busy','false');$('loadError').hidden=false;$('resultsSummary').textContent='素材加载失败';
    $('loadErrorMessage').textContent=location.protocol==='file:'?'请通过项目的本地启动网址打开页面，再重新加载。':'请检查网络连接后重试。';
  }
}

$('collectionTabs').addEventListener('click',event=>{const button=event.target.closest('[data-collection]');if(button)setCollection(button.dataset.collection);});
$('headerFavorites').onclick=()=>{setCollection('favorites',true);$('resultsPanel').scrollIntoView({behavior:'smooth'});};
$('searchInput').addEventListener('input',event=>{clearTimeout(searchTimer);state.query=event.target.value;$('clearSearch').hidden=!state.query;searchTimer=setTimeout(()=>{state.page=1;applyFilters();},170);});
$('clearSearch').onclick=()=>{clearTimeout(searchTimer);state.query='';state.page=1;syncInputs();applyFilters();$('searchInput').focus();};
document.querySelectorAll('[data-query]').forEach(button=>button.onclick=()=>{clearTimeout(searchTimer);state.query=button.dataset.query;state.page=1;syncInputs();applyFilters();});
[['categoryFilter','category'],['styleFilter','style']].forEach(([id,key])=>$(id).onchange=event=>{state[key]=event.target.value;state.page=1;applyFilters();});
[['svgOnly','svgOnly'],['pdfOnly','pdfOnly']].forEach(([id,key])=>$(id).onchange=event=>{state[key]=event.target.checked;state.page=1;applyFilters();});
$('sortSelect').onchange=event=>{state.sort=event.target.value;state.page=1;applyFilters();};
$('pageSize').onchange=event=>{state.pageSize=Number(event.target.value);state.page=1;renderResults();};
$('resetFilters').onclick=resetFilters;
$('emptyReset').onclick=()=>{if(state.collection==='favorites'&&!favorites.size)setCollection('featured',true);else resetFilters();};
$('retryLoad').onclick=loadCatalog;
$('detailFavorite').onclick=()=>{if(activeAsset)toggleFavorite(activeAsset.id);};
$('closeDialog').onclick=()=>$('assetDialog').close();
$('assetDialog').addEventListener('click',event=>{if(event.target===$('assetDialog')){const rect=$('assetDialog').getBoundingClientRect();if(event.clientX<rect.left||event.clientX>rect.right||event.clientY<rect.top||event.clientY>rect.bottom)$('assetDialog').close();}});
$('assetDialog').addEventListener('close',()=>{previewSequence++;releasePreview();activeAsset=null;});
document.querySelectorAll('[data-background]').forEach(button=>button.onclick=()=>setPreviewBackground(button.dataset.background));
$('iconColor').addEventListener('input',event=>{selectedColor=event.target.value;updateColorPreview();});
document.querySelectorAll('[data-color]').forEach(button=>button.onclick=()=>{selectedColor=button.dataset.color;updateColorPreview();});
document.addEventListener('keydown',event=>{if(event.key==='/'&&!$('assetDialog').open&&!['INPUT','TEXTAREA','SELECT'].includes(document.activeElement?.tagName)&&!document.activeElement?.isContentEditable){event.preventDefault();$('searchInput').focus();}});
window.addEventListener('storage',event=>{if(event.key===STORAGE_KEY){try{favorites=new Set(JSON.parse(event.newValue||'[]').map(String));updateCounts();applyFilters();updateDetailFavorite();}catch{}}});
loadCatalog();
