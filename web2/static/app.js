let currentAlbum = null;
let currentPhotos = [];
let currentIndex = 0;

function escapeHtml(str) {
  return str.replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/'/g,'&#39;').replace(/</g,'&lt;');
}

async function showAlbums() {
  currentAlbum = null;
  document.getElementById('breadcrumb').innerHTML = '';
  document.getElementById('photos-view').style.display = 'none';
  const view = document.getElementById('albums-view');
  view.style.display = '';
  view.innerHTML = '<div style="color:#666">Loading...</div>';

  const res = await fetch('/api/albums');
  const albums = await res.json();

  if (!albums.length) {
    view.innerHTML = '<div style="color:#666;grid-column:1/-1">No albums found. Check config.json paths.</div>';
    return;
  }

  view.innerHTML = '';
  albums.forEach(a => {
    const card = document.createElement('div');
    card.className = 'album-card';
    card.onclick = () => showPhotos(a.id, a.name);

    const img = document.createElement('img');
    img.src = a.cover;
    img.alt = a.name;
    img.loading = 'lazy';
    img.onerror = () => { img.style.display = 'none'; };

    const label = document.createElement('div');
    label.className = 'label';
    label.innerHTML = escapeHtml(a.name) + '<br><span class="count">' + a.count + ' photos</span>';

    card.appendChild(img);
    card.appendChild(label);
    view.appendChild(card);
  });
}

async function showPhotos(albumId, albumName) {
  currentAlbum = albumId;
  document.getElementById('breadcrumb').innerHTML = '<a href="#" onclick="showAlbums(); return false;">Albums</a> / ' + escapeHtml(albumName || albumId);
  document.getElementById('albums-view').style.display = 'none';
  const view = document.getElementById('photos-view');
  view.style.display = '';
  view.innerHTML = '<div style="color:#666">Loading...</div>';

  const res = await fetch('/api/photos/' + encodeURIComponent(albumId));
  currentPhotos = await res.json();

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
  const img = document.getElementById('lb-img');
  img.src = photo.full;
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
  showAlbums();
}

async function refreshStatus() {
  const panel = document.getElementById('status-panel');
  const res = await fetch('/api/status');
  const data = await res.json();
  const bg = data.bg;
  const albums = data.albums;

  let html = '<h2>📊 Albums Status ';
  if (bg.running) {
    html += '<span style="color:#f59e0b;font-size:0.8rem;font-weight:400">⏳ ' + bg.done + '/' + bg.total + ' — ' + escapeHtml(bg.current) + '</span>';
  } else {
    html += '<span style="color:#4ade80;font-size:0.8rem;font-weight:400">✅ Done</span>'
      + ' <button onclick="triggerGenerate()" style="background:#222;border:1px solid #333;color:#aaa;padding:0.2rem 0.6rem;border-radius:4px;cursor:pointer;font-size:0.75rem;margin-left:0.5rem">🔄 Regenerate</button>'
      + ' <button onclick="triggerCleanup()" style="background:#222;border:1px solid #333;color:#aaa;padding:0.2rem 0.6rem;border-radius:4px;cursor:pointer;font-size:0.75rem;margin-left:0.3rem">🧹 Cleanup</button>';
  }
  html += '</h2>';

  albums.forEach(a => {
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
}

showAlbums();
