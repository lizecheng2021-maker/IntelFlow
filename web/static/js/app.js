/* IntelFlow — Frontend Logic */

// Tab switching
document.querySelectorAll('.tabs .tab').forEach(tab => {
    tab.addEventListener('click', () => {
        const target = tab.dataset.tab;
        if (!target) return;
        document.querySelectorAll('.tabs .tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        tab.classList.add('active');
        document.getElementById('tab-' + target).classList.add('active');
    });
});

// API helpers
async function postJSON(url, data) {
    const resp = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    });
    return resp.json();
}

function showStatus(id, msg, ok) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = msg;
    el.className = 'status-msg ' + (ok ? 'ok' : 'error');
    setTimeout(() => { el.textContent = ''; }, 3000);
}

// Save API Keys
async function saveEnvKeys() {
    const data = {};
    document.querySelectorAll('[id^="key-"]').forEach(input => {
        const key = input.id.replace('key-', '');
        if (input.value) data[key] = input.value;
    });
    const result = await postJSON('/api/save-env', data);
    showStatus('keys-status', result.ok ? 'Saved!' : 'Error: ' + result.error, result.ok);
}

// Test API Key
async function testKey(service) {
    const keyMap = { gnews: 'GNEWS_API_KEY', tavily: 'TAVILY_API_KEY', gemini: 'GEMINI_API_KEY', anthropic: 'ANTHROPIC_API_KEY' };
    const input = document.getElementById('key-' + keyMap[service]);
    if (!input || !input.value || input.value.includes('****')) {
        alert('Please enter the full API key first.');
        return;
    }
    const btn = event.target;
    btn.textContent = '...';
    btn.disabled = true;
    const result = await postJSON('/api/test-key', { service, key: input.value });
    btn.textContent = result.ok ? 'OK' : 'Fail';
    btn.style.color = result.ok ? 'var(--success)' : 'var(--danger)';
    setTimeout(() => { btn.textContent = 'Test'; btn.style.color = ''; btn.disabled = false; }, 2000);
}

// Save Sources
async function saveSources() {
    const data = {};
    document.querySelectorAll('[data-source]').forEach(cb => {
        data[cb.dataset.source] = { enabled: cb.checked };
    });

    // Custom RSS
    const rssInputs = document.querySelectorAll('.rss-input');
    data.custom_rss = Array.from(rssInputs).map(i => i.value).filter(v => v.trim());

    // Custom subreddits
    const subInput = document.getElementById('subreddit-input');
    if (subInput && subInput.value) {
        data.custom_subreddits = subInput.value.split(',').map(s => s.trim()).filter(Boolean);
    }

    // YouTube channels
    const ytInput = document.getElementById('youtube-channels');
    if (ytInput && ytInput.value) {
        data.youtube_channels = ytInput.value.split('\n').map(s => s.trim()).filter(Boolean);
    }

    const result = await postJSON('/api/save-sources', data);
    showStatus('sources-status', result.ok ? 'Saved!' : 'Error', result.ok);
}

// Add RSS field
function addRssField() {
    const container = document.getElementById('custom-rss');
    const row = document.createElement('div');
    row.className = 'form-row';
    row.innerHTML = '<input type="text" class="rss-input" placeholder="https://example.com/feed.xml"> <button class="btn btn-sm" onclick="this.parentElement.remove()">-</button>';
    container.appendChild(row);
}

// Focus area weights
function updateWeight(slider) {
    const dim = slider.dataset.dim;
    document.getElementById('weight-' + dim).textContent = slider.value + '%';
    recalcTotal();
}

function recalcTotal() {
    let total = 0;
    document.querySelectorAll('.weight-slider').forEach(s => {
        const cb = document.querySelector(`[data-dim="${s.dataset.dim}"]`);
        if (cb && cb.checked) total += parseInt(s.value);
    });
    const el = document.getElementById('total-weight');
    if (el) {
        el.textContent = total;
        el.style.color = total === 100 ? 'var(--success)' : 'var(--warning)';
    }
}

// Save Focus
async function saveFocus() {
    const dimensions = {};
    document.querySelectorAll('.focus-item').forEach(item => {
        const cb = item.querySelector('input[type="checkbox"]');
        const slider = item.querySelector('.weight-slider');
        if (cb && slider) {
            dimensions[cb.dataset.dim] = {
                enabled: cb.checked,
                weight: parseInt(slider.value),
                label: cb.parentElement.textContent.trim()
            };
        }
    });

    const languages = [];
    if (document.getElementById('lang-en')?.checked) languages.push('en');
    if (document.getElementById('lang-zh')?.checked) languages.push('zh');

    const data = {
        dimensions,
        languages,
        report_length: document.getElementById('report-length')?.value || 'standard'
    };
    const result = await postJSON('/api/save-focus', data);
    showStatus('focus-status', result.ok ? 'Saved!' : 'Error', result.ok);
}

// Save Profile
async function saveProfile() {
    const data = {
        name: document.getElementById('profile-name')?.value || '',
        background: document.getElementById('profile-background')?.value || '',
        tone: document.getElementById('profile-tone')?.value || 'analytical',
        catchphrases: (document.getElementById('profile-catchphrases')?.value || '').split('\n').filter(Boolean),
        analysis_style: document.getElementById('profile-style')?.value || ''
    };
    const result = await postJSON('/api/save-profile', data);
    showStatus('profile-status', result.ok ? 'Saved!' : 'Error', result.ok);
}

// Save Platforms
async function savePlatforms() {
    const data = {};
    document.querySelectorAll('[data-platform]').forEach(cb => {
        if (cb.type === 'checkbox') {
            data[cb.dataset.platform] = data[cb.dataset.platform] || {};
            data[cb.dataset.platform].enabled = cb.checked;
        }
    });
    document.querySelectorAll('[data-platform-opt]').forEach(input => {
        const key = input.dataset.platformOpt;
        const [platform] = key.split('_');
        if (!data[platform]) data[platform] = {};
        data[platform][key] = input.value;
    });
    const result = await postJSON('/api/save-platforms', data);
    showStatus('platforms-status', result.ok ? 'Saved!' : 'Error', result.ok);
}

// Run pipeline
async function runPipeline() {
    if (!confirm('Run the daily intelligence pipeline now?')) return;
    const btn = document.getElementById('btn-run');
    btn.textContent = 'Starting...';
    btn.disabled = true;
    const result = await postJSON('/api/run', { date: new Date().toISOString().slice(0, 10) });
    if (result.ok) {
        btn.textContent = 'Running...';
        document.getElementById('pipeline-log').style.display = 'block';
        pollStatus();
    } else {
        alert(result.error || 'Failed to start pipeline');
        btn.textContent = 'Run Daily Pipeline';
        btn.disabled = false;
    }
}

// Poll pipeline status
let pollTimer = null;
function pollStatus() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(async () => {
        const resp = await fetch('/api/status');
        const data = await resp.json();
        const logEl = document.getElementById('log-output');
        if (logEl) logEl.textContent = data.log.join('\n');
        if (data.status === 'idle') {
            clearInterval(pollTimer);
            const btn = document.getElementById('btn-run');
            if (btn) { btn.textContent = 'Run Daily Pipeline'; btn.disabled = false; }
            location.reload();
        }
    }, 3000);
}

// Init
document.addEventListener('DOMContentLoaded', () => {
    recalcTotal();
});
