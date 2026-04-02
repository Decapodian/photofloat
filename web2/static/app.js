let currentPath = "";
let currentPhotos = [];
let currentIndex = 0;

function escapeHtml(str) {
  return str.replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/'/g,'&#39;').replace(/</g,'&lt;');
}

function buildBreadcrumb(path) {
  const bc = document.getElementById('breadcrumb');
  if (!path) { bc.innerHTML = ''; return; }
  const parts = path.split('/');
  let html = '<a href="#" onclick="browse(\'\'); return false;">Home</a>';
  let accumulated = '';
  parts.forEach((p, i) => {
    accumulated += (i ? '/' : '') + p;
    const link = accumulated;
    if (i < parts.length - 1) {
      html += ' / <a href="#" onclick="browse(\'' + escapeHtml(link) + '\'); return false;">' + escapeHtml(p) + '</a>';
    } else {
      html += ' / ' + escapeHtml(p);
    }
  });
  bc.innerHTML = html;
}

async function browse(path) {
  currentPath = path;
  buildBreadcrumb(path);

  const albumsView = document.getElementById('albums-view');
  const photosView = document.getElementById('photos-view');
  albumsView.style.display = '';
  albumsView.innerHTML = '<div style="color:#666">Loading...</div>';
  photosView.style.display = 'none';
  photosView.innerHTML = '';

  const url = path ? '/api/browse/' + encodeURI(path) : '/api/browse';
  const res = await fetch(url);
  const data = await res.json();

  // Render subalbums
  albumsView.innerHTML = '';
  if (data.albums.length) {
    data.albums.forEach(a => {
      const card = document.createElement('div');
      card.className = 'album-card';
      card.onclick = () => browse(a.id);

      const img = document.createElement('img');
      img.src = a.cover || '';
      img.alt = a.name;
      img.loading = 'lazy';
      img.onerror = () => { img.style.display = 'none'; };

      const label = document.createElement('div');
      label.className = 'label';
      label.textContent = a.name;

      card.appendChild(img);
      card.appendChild(label);
      albumsView.appendChild(card);
    });
  }

  // Render photos
  if (data.photos.length) {
    photosView.style.display = '';
    currentPhotos = data.photos;
    document.getElementById('sort-select').style.display = '';
    applySort();
  } else {
    document.getElementById('sort-select').style.display = 'none';
  }

  if (!data.albums.length && !data.photos.length) {
    albumsView.innerHTML = '<div style="color:#666;grid-column:1/-1">Empty folder</div>';
  }
}

function applySort() {
  const val = document.getElementById('sort-select').value;
  const [field, dir] = val.split('-');
  const sorted = [...currentPhotos].sort((a, b) => {
    let va = a[field], vb = b[field];
    if (field === 'name') { va = va.toLowerCase(); vb = vb.toLowerCase(); }
    if (va < vb) return dir === 'asc' ? -1 : 1;
    if (va > vb) return dir === 'asc' ? 1 : -1;
    return 0;
  });
  currentPhotos = sorted;
  renderPhotos();
}

function renderPhotos() {
  const view = document.getElementById('photos-view');
  view.innerHTML = '';
  currentPhotos.forEach((p, i) => {
    const div = document.createElement('div');
    div.className = 'photo-thumb';
    div.onclick = () => openLightbox(i);

    const img = document.createElement('img');
    img.className = 'loading';
    img.src = p.thumb;
    img.alt = p.name;
    img.loading = 'lazy';
    img.onload = () => { img.className = 'loaded'; };
    img.onerror = () => { div.style.display = 'none'; };

    div.appendChild(img);
    view.appendChild(div);
  });
}

function openLightbox(index) {
  currentIndex = index;
  updateLightbox();
  document.getElementById('lightbox').style.display = 'flex';
  document.body.style.overflow = 'hidden';
}

function closeLightbox(e) {
  if (e && e.target !== e.currentTarget) return;
  document.getElementById('lightbox').style.display = 'none';
  document.body.style.overflow = '';
}

function updateLightbox() {
  const photo = currentPhotos[currentIndex];
  document.getElementById('lb-img').src = photo.full;
  document.getElementById('lb-caption').textContent = photo.name;
  document.getElementById('lb-counter').textContent = (currentIndex + 1) + ' / ' + currentPhotos.length;
}

function prevPhoto(e) {
  e && e.stopPropagation();
  currentIndex = (currentIndex - 1 + currentPhotos.length) % currentPhotos.length;
  updateLightbox();
}

function nextPhoto(e) {
  e && e.stopPropagation();
  currentIndex = (currentIndex + 1) % currentPhotos.length;
  updateLightbox();
}

document.addEventListener('keydown', e => {
  if (document.getElementById('lightbox').style.display === 'none') return;
  if (e.key === 'ArrowRight') nextPhoto();
  else if (e.key === 'ArrowLeft') prevPhoto();
  else if (e.key === 'Escape') closeLightbox();
});

// Status panel
let statusInterval = null;

async function toggleStatus() {
  const panel = document.getElementById('status-panel');
  if (panel.style.display !== 'none') {
    panel.style.display = 'none';
    if (statusInterval) { clearInterval(statusInterval); statusInterval = null; }
    return;
  }
  panel.style.display = '';
  await refreshStatus();
  statusInterval = setInterval(refreshStatus, 2000);
}

async function triggerGenerate() {
  await fetch('/api/generate');
  await refreshStatus();
}

async function triggerCleanup() {
  const res = await fetch('/api/cleanup');
  const data = await res.json();
  alert('Cleaned ' + data.removed + ' orphan thumbnails');
  await refreshStatus();
}

async function refreshStatus() {
  const panel = document.getElementById('status-panel');
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000);
    const res = await fetch('/api/status', { signal: controller.signal });
    clearTimeout(timeout);
    const data = await res.json();
  const bg = data.bg;

  let html = '<h2>📊 Status ';
  if (bg.running) {
    html += '<span style="color:#f59e0b;font-size:0.8rem;font-weight:400">⏳ ' + bg.done + '/' + bg.total + ' — ' + escapeHtml(bg.current) + '</span>';
  } else {
    html += '<span style="color:#4ade80;font-size:0.8rem;font-weight:400">✅ Done</span>'
      + ' <button onclick="triggerGenerate()" style="background:#222;border:1px solid #333;color:#aaa;padding:0.2rem 0.6rem;border-radius:4px;cursor:pointer;font-size:0.75rem;margin-left:0.5rem">🔄 Regenerate</button>'
      + ' <button onclick="triggerCleanup()" style="background:#222;border:1px solid #333;color:#aaa;padding:0.2rem 0.6rem;border-radius:4px;cursor:pointer;font-size:0.75rem;margin-left:0.3rem">🧹 Cleanup</button>';
  }
  html += '</h2>';

  data.albums.forEach(a => {
    const pct = a.photos > 0 ? Math.round(a.thumbs / a.photos * 100) : 0;
    const color = pct >= 100 ? '#4ade80' : '#f59e0b';
    html += '<div class="status-row">'
      + '<div class="status-name">' + escapeHtml(a.name) + '</div>'
      + '<div class="status-path">' + escapeHtml(a.path) + '</div>'
      + '<div class="status-bar"><div class="status-bar-fill" style="width:' + pct + '%;background:' + color + '"></div></div>'
      + '<div class="status-count">' + a.thumbs + '/' + a.photos + ' (' + pct + '%)</div>'
      + '</div>';
  });
  panel.innerHTML = html;
  } catch(e) {
    panel.innerHTML = '<h2>📊 Status</h2><div style="color:#666;padding:0.5rem">Loading... (scanning folders)</div>';
  }
}

// Start
browse("");
