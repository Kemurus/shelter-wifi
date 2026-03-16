'use strict';

// ── State ─────────────────────────────────────────────────────
const state = {
  scanning: false,
  connecting: false,
  currentSsid: '',
  hotspotChannel: 13,
  hotspotSecurity: 'open',
};

// ── Utils ─────────────────────────────────────────────────────
function $(id) { return document.getElementById(id); }

async function api(method, path, body) {
  const opts = { method, headers: {} };
  if (body) { opts.headers['Content-Type'] = 'application/json'; opts.body = JSON.stringify(body); }
  const r = await fetch(path, opts);
  return r.json();
}

function toast(msg, type = 'info', icon = null) {
  const icons = { success: 'fa-circle-check', error: 'fa-circle-xmark', info: 'fa-circle-info' };
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.innerHTML = `<i class="fa-solid ${icon || icons[type]}"></i><span>${msg}</span>`;
  $('toast-container').prepend(el);
  setTimeout(() => el.remove(), 3500);
}

function signalBars(dbm) {
  const lvl = dbm > -55 ? 4 : dbm > -65 ? 3 : dbm > -75 ? 2 : 1;
  const cls  = dbm > -65 ? 'on' : dbm > -75 ? 'med' : 'low';
  return `<span class="signal">` +
    [4, 8, 12, 16].map((h, i) =>
      `<span class="signal-bar ${i < lvl ? cls : ''}" style="height:${h}px"></span>`
    ).join('') +
    `</span>`;
}

function signalLabel(dbm) {
  if (dbm === null || dbm === undefined) return '—';
  const q = dbm > -55 ? 'Excellent' : dbm > -65 ? 'Good' : dbm > -75 ? 'Weak' : 'Poor';
  return `${signalBars(dbm)} <span style="margin-left:6px;font-size:.8rem;color:var(--text-muted)">${dbm} dBm · ${q}</span>`;
}

function flagSecurity(flags) {
  if (!flags) return 'Open';
  if (flags.includes('WPA2')) return 'WPA2';
  if (flags.includes('WPA'))  return 'WPA';
  return 'Open';
}

function togglePass(inputId, btn) {
  const inp = $(inputId);
  const show = inp.type === 'password';
  inp.type = show ? 'text' : 'password';
  btn.innerHTML = `<i class="fa-solid ${show ? 'fa-eye-slash' : 'fa-eye'}"></i>`;
}

// ── Tabs ──────────────────────────────────────────────────────
document.querySelectorAll('.tab').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(s => s.classList.remove('active'));
    btn.classList.add('active');
    $('tab-' + btn.dataset.tab).classList.add('active');
    if (btn.dataset.tab === 'clients') refreshClients();
    if (btn.dataset.tab === 'hotspot') loadHotspotConfig();
  });
});

// ── Status Polling ────────────────────────────────────────────
async function refreshStatus() {
  try {
    const d = await api('GET', '/api/status');
    const up = d.upstream;
    const hs = d.hotspot;

    // Header
    $('h-temp').innerHTML   = `<i class="fa-solid fa-temperature-half"></i> ${d.system.cpu_temp ? d.system.cpu_temp.toFixed(1) + '°C' : '—'}`;
    $('h-uptime').innerHTML = `<i class="fa-solid fa-clock"></i> ${d.system.uptime}`;

    const mgmt = d.management || {};

    // Alfa upstream (wlan1)
    $('cv-wan-line').className = 'conn-line ' + (up.connected ? 'connected' : 'disconnected');
    $('cv-wan-label').textContent = up.connected ? up.ssid : 'Not connected';
    $('up-ip').textContent = up.connected ? up.ip_address : '';
    $('cv-internet-icon').className = 'conn-icon ' + (up.connected ? 'green' : '');
    const sigDbm = up.signal_dbm;
    $('up-signal-val').innerHTML = sigDbm != null
      ? `${signalBars(sigDbm)} ${sigDbm}`
      : '—';

    // Management WiFi (wlan0 built-in)
    $('mgmt-line').className = 'conn-line ' + (mgmt.connected ? 'connected' : 'disconnected');
    $('mgmt-ssid').textContent = mgmt.connected ? mgmt.ssid : 'Not connected';
    $('mgmt-ip').textContent = mgmt.connected ? mgmt.ip_address : '';
    $('mgmt-icon').className = 'conn-icon ' + (mgmt.connected ? 'accent' : '');

    // Hotspot
    $('hs-ssid').textContent      = hs.ssid || '—';
    $('hs-clients').textContent   = hs.clients;
    $('cv-hs-label').textContent  = hs.ssid || '—';

    // Client badge in tab
    const cb = $('client-badge');
    if (hs.clients > 0) {
      cb.textContent = hs.clients;
      cb.classList.remove('hidden');
    } else {
      cb.classList.add('hidden');
    }

    state.currentSsid = up.ssid;
  } catch(e) { /* silent */ }
}

// ── Disconnect ────────────────────────────────────────────────
async function doDisconnect() {
  await api('POST', '/api/networks/disconnect');
  toast('Disconnected from upstream network', 'info');
  setTimeout(refreshStatus, 1000);
}

// ── Network Scan ──────────────────────────────────────────────
let _scanTimer = null;

async function startScan() {
  if (state.scanning) return;
  state.scanning = true;

  const btn = $('scan-btn');
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner"></span> Scanning...`;

  $('networks-list').innerHTML = `
    <div class="card">
      <div class="card-body scanning-state">
        <i class="fa-solid fa-satellite-dish pulse-icon"></i>
        <p style="color:var(--text-muted);font-size:.875rem">Alfa is scanning for WiFi networks...</p>
      </div>
    </div>`;

  await api('POST', '/api/networks/scan');
  _scanTimer = setInterval(pollScan, 1200);
}

async function pollScan() {
  const d = await api('GET', '/api/networks/scan/results');
  if (!d.scanning) {
    clearInterval(_scanTimer);
    state.scanning = false;
    const btn = $('scan-btn');
    btn.disabled = false;
    btn.innerHTML = `<i class="fa-solid fa-satellite-dish"></i> Scan`;
    renderNetworks(d.networks || []);
  }
}

function renderNetworks(nets) {
  if (!nets.length) {
    $('networks-list').innerHTML = `
      <div class="card"><div class="card-body empty-state">
        <i class="fa-solid fa-wifi" style="font-size:2rem;opacity:.3;display:block;margin-bottom:10px"></i>
        <p>No networks found. Try again.</p>
      </div></div>`;
    return;
  }

  const seen = new Set();
  const unique = nets.filter(n => {
    if (!n.ssid || seen.has(n.ssid)) return false;
    seen.add(n.ssid); return true;
  });

  const isConnected = ssid => ssid === state.currentSsid;

  $('networks-list').innerHTML = `
    <div class="card">
      ${unique.map(n => {
        const sec      = flagSecurity(n.flags);
        const secIcon  = sec === 'Open' ? 'fa-lock-open' : 'fa-lock';
        const lvl      = n.signal > -55 ? 4 : n.signal > -65 ? 3 : n.signal > -75 ? 2 : 1;
        const cls      = n.signal > -65 ? 'on' : n.signal > -75 ? 'med' : 'low';
        const bars     = [4,8,12,16].map((h,i) =>
          `<span class="signal-bar ${i<lvl?cls:''}" style="height:${h}px"></span>`
        ).join('');
        const connected = isConnected(n.ssid);
        return `
          <div class="network-item">
            <span class="signal" style="flex-shrink:0">${bars}</span>
            <div class="network-info">
              <div class="network-name">${esc(n.ssid)}</div>
              <div class="network-meta">
                <i class="fa-solid ${secIcon}" style="font-size:.7rem"></i> ${sec}
                &nbsp;·&nbsp; ${n.signal} dBm
                &nbsp;·&nbsp; ${n.frequency} MHz
              </div>
              ${connected ? `<div class="network-connected"><i class="fa-solid fa-circle-check"></i> Connected</div>` : ''}
            </div>
            ${connected
              ? `<button class="btn btn-danger btn-sm" onclick="doDisconnect()">Disconnect</button>`
              : `<button class="btn btn-primary btn-sm" onclick="openModal('${escAttr(n.ssid)}','${sec}')">Connect</button>`
            }
          </div>`;
      }).join('')}
    </div>`;
}

// ── Connect Modal ─────────────────────────────────────────────
function openModal(ssid, security) {
  $('modal-ssid-label').textContent = ssid;
  $('modal-ssid-value').value = ssid;
  $('modal-pass').value = '';
  $('modal-pass-group').style.display = security === 'Open' ? 'none' : 'block';
  $('connect-status').className = 'connect-status hidden';
  $('connect-status').innerHTML = '';
  $('modal-connect-btn').disabled = false;
  $('modal-connect-btn').innerHTML = `<i class="fa-solid fa-plug"></i> Connect`;
  $('modal-overlay').classList.remove('hidden');
  setTimeout(() => $('modal-pass').focus(), 100);
}

function closeModal() {
  $('modal-overlay').classList.add('hidden');
}

let _connectTimer = null;

async function submitConnect() {
  const ssid     = $('modal-ssid-value').value;
  const password = $('modal-pass').value;
  const btn      = $('modal-connect-btn');

  btn.disabled = true;
  btn.innerHTML = `<span class="spinner"></span> Connecting...`;

  const status = $('connect-status');
  status.className = 'connect-status connecting';
  status.innerHTML = `<span class="spinner"></span> Connecting to <b>${esc(ssid)}</b>...`;
  status.classList.remove('hidden');

  await api('POST', '/api/networks/connect', { ssid, password });
  _connectTimer = setInterval(pollConnect, 1500);
}

async function pollConnect() {
  const d = await api('GET', '/api/networks/connect/status');
  if (!d.running) {
    clearInterval(_connectTimer);
    const status = $('connect-status');
    const btn    = $('modal-connect-btn');
    if (d.success) {
      status.className = 'connect-status success';
      status.innerHTML = `<i class="fa-solid fa-circle-check"></i> Connected to <b>${esc(d.ssid)}</b>`;
      btn.innerHTML = `<i class="fa-solid fa-check"></i> Done`;
      toast(`Connected to ${d.ssid}`, 'success');
      refreshStatus();
      setTimeout(closeModal, 1800);
    } else {
      status.className = 'connect-status error';
      status.innerHTML = `<i class="fa-solid fa-circle-xmark"></i> ${d.error || 'Failed to connect. Check password.'}`;
      btn.disabled = false;
      btn.innerHTML = `<i class="fa-solid fa-rotate-right"></i> Try again`;
    }
  }
}

// ── Hotspot Config ────────────────────────────────────────────
function buildChannelGrid(active) {
  const grid = $('channel-grid');
  grid.innerHTML = [1,2,3,4,5,6,7,8,9,10,11,12,13].map(ch =>
    `<button class="ch-btn ${ch == active ? 'active' : ''}"
      onclick="selectChannel(${ch}, this)">${ch}</button>`
  ).join('');
  state.hotspotChannel = active;
}

function selectChannel(ch, el) {
  document.querySelectorAll('.ch-btn').forEach(b => b.classList.remove('active'));
  el.classList.add('active');
  state.hotspotChannel = ch;
}

async function loadHotspotConfig() {
  const d = await api('GET', '/api/hotspot/config');
  $('hs-ssid-input').value = d.ssid || '';
  buildChannelGrid(d.channel || 13);

  const hasPsk = d.has_password;
  document.querySelectorAll('input[name="security"]').forEach(r => {
    r.checked = r.value === (hasPsk ? 'wpa2' : 'open');
  });
  $('password-group').style.display = hasPsk ? 'block' : 'none';
}

document.querySelectorAll('input[name="security"]').forEach(r => {
  r.addEventListener('change', () => {
    $('password-group').style.display = r.value === 'wpa2' ? 'block' : 'none';
  });
});

async function saveHotspot() {
  const ssid     = $('hs-ssid-input').value.trim();
  const security = document.querySelector('input[name="security"]:checked').value;
  const password = $('hs-pass-input').value.trim();
  const channel  = state.hotspotChannel;

  if (!ssid) { toast('Enter a network name', 'error'); return; }
  if (security === 'wpa2' && password.length < 8) {
    toast('Password must be at least 8 characters', 'error'); return;
  }

  const body = { ssid, channel };
  if (security === 'wpa2') body.password = password;
  else body.open = true;

  const btn = document.querySelector('[onclick="saveHotspot()"]');
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner"></span> Saving...`;

  try {
    const d = await api('PUT', '/api/hotspot/config', body);
    if (d.error) { toast(d.error, 'error'); }
    else {
      toast('Hotspot settings updated', 'success');
      $('hs-pass-input').value = '';
      refreshStatus();
    }
  } catch(e) { toast('Save failed', 'error'); }

  btn.disabled = false;
  btn.innerHTML = `<i class="fa-solid fa-floppy-disk"></i> Save`;
}

// ── Clients ───────────────────────────────────────────────────
async function refreshClients() {
  const list = $('clients-list');
  try {
    const d = await api('GET', '/api/clients/');
    const clients = d.clients || [];

    if (!clients.length) {
      list.innerHTML = `<div class="empty-state">
        <i class="fa-solid fa-user-slash"></i>
        <p>No connected devices</p>
      </div>`;
      return;
    }

    list.innerHTML = clients.map(c => `
      <div class="client-item" id="client-${c.mac.replace(/:/g,'')}">
        <div class="client-icon"><i class="fa-solid fa-mobile-screen-button"></i></div>
        <div class="client-info">
          <div class="client-name">${esc(c.hostname) || 'Device'}</div>
          <div class="client-meta">${c.ip} &nbsp;·&nbsp; ${c.mac}</div>
        </div>
        <button class="btn btn-danger btn-sm" onclick="kickClient('${c.mac}', this)">
          <i class="fa-solid fa-user-xmark"></i> Kick
        </button>
      </div>`).join('');
  } catch(e) {
    list.innerHTML = `<div class="empty-state"><i class="fa-solid fa-triangle-exclamation"></i><p>Failed to load</p></div>`;
  }
}

async function kickClient(mac, btn) {
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner"></span>`;
  try {
    await fetch(`/api/clients/${mac}`, { method: 'DELETE' });
    const el = $('client-' + mac.replace(/:/g,''));
    if (el) { el.style.opacity = '0'; el.style.transition = 'opacity .3s'; setTimeout(() => el.remove(), 300); }
    toast('Client disconnected', 'info');
  } catch(e) { toast('Error', 'error'); btn.disabled = false; }
}

// ── Escape ────────────────────────────────────────────────────
function esc(s) {
  return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
function escAttr(s) {
  return (s||'').replace(/'/g,"\\'").replace(/\\/g,'\\\\');
}

// ── Init ──────────────────────────────────────────────────────
refreshStatus();
setInterval(refreshStatus, 5000);
setInterval(() => {
  if (document.querySelector('.tab[data-tab="clients"].active')) refreshClients();
}, 10000);

document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });
