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

// Add a new custom dimension
function addDimension() {
    const key = prompt('Dimension key (lowercase, no spaces, e.g. "healthcare"):');
    if (!key || !key.match(/^[a-z][a-z0-9_]*$/)) {
        if (key !== null) alert('Key must be lowercase letters, digits, and underscores (start with a letter).');
        return;
    }
    // Check for duplicate
    if (document.querySelector(`[data-dim-key="${key}"]`)) {
        alert('A dimension with this key already exists.');
        return;
    }
    const label = prompt('Display label (e.g. "Healthcare & Biotech"):') || key;
    const weight = parseInt(prompt('Weight (0-50, e.g. 10):') || '10', 10);
    if (isNaN(weight) || weight < 0 || weight > 50) {
        alert('Weight must be a number between 0 and 50.');
        return;
    }

    const grid = document.getElementById('focus-grid');
    const div = document.createElement('div');
    div.className = 'focus-item';
    div.dataset.dimKey = key;
    div.innerHTML = `
        <div class="focus-item-header">
            <label class="toggle">
                <input type="checkbox" data-dim="${key}" checked>
                <span class="dim-label">${label}</span>
            </label>
            <button class="btn btn-sm btn-danger" onclick="removeDimension('${key}')" title="Remove dimension">&times;</button>
        </div>
        <input type="text" class="dim-description" data-dim-desc="${key}" value="" placeholder="Brief description of this dimension">
        <div class="focus-item-weight">
            <input type="range" min="0" max="50" value="${weight}"
                   class="weight-slider" data-dim="${key}"
                   oninput="updateWeight(this)">
            <span class="weight-val" id="weight-${key}">${weight}%</span>
        </div>
    `;
    grid.appendChild(div);
    recalcTotal();
}

// Remove a dimension row
function removeDimension(key) {
    const item = document.querySelector(`[data-dim-key="${key}"]`);
    if (item && confirm(`Remove dimension "${key}"?`)) {
        item.remove();
        recalcTotal();
    }
}

// Save Focus
async function saveFocus() {
    const dimensions = {};
    document.querySelectorAll('.focus-item').forEach(item => {
        const cb = item.querySelector('input[type="checkbox"]');
        const slider = item.querySelector('.weight-slider');
        const descInput = item.querySelector('.dim-description');
        const labelEl = item.querySelector('.dim-label');
        if (cb && slider) {
            dimensions[cb.dataset.dim] = {
                enabled: cb.checked,
                weight: parseInt(slider.value),
                label: labelEl ? labelEl.textContent.trim() : cb.dataset.dim,
                description: descInput ? descInput.value.trim() : ''
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

// AI Model config
const MODEL_OPTIONS = {
    anthropic: ["claude-sonnet-4-20250514", "claude-opus-4-20250514", "claude-haiku-4-20250414"],
    openai: ["gpt-4o", "gpt-4o-mini", "o1"],
    gemini: ["gemini-2.5-pro", "gemini-2.5-flash"],
    zhipu: ["glm-4-plus", "glm-4"],
    dashscope: ["qwen-max", "qwen-plus", "qwen-turbo"],
    ollama: ["llama3", "mistral", "qwen2"]
};

function onProviderChange() {
    const providerEl = document.getElementById('ai-provider');
    if (!providerEl) return;
    const provider = providerEl.value;
    const modelSelect = document.getElementById('ai-model');
    const ollamaRow = document.getElementById('ollama-url-row');

    // Update model options
    modelSelect.innerHTML = '';
    (MODEL_OPTIONS[provider] || []).forEach(m => {
        const opt = document.createElement('option');
        opt.value = m;
        opt.textContent = m;
        modelSelect.appendChild(opt);
    });

    // Show/hide Ollama URL, hide API key for Ollama
    if (ollamaRow) ollamaRow.style.display = provider === 'ollama' ? '' : 'none';
    const aiKeyRow = document.getElementById('ai-key-row');
    if (aiKeyRow) aiKeyRow.style.display = provider === 'ollama' ? 'none' : '';

    // Update API key placeholder per provider
    const keyInput = document.getElementById('ai-api-key');
    if (keyInput) {
        const placeholders = {
            anthropic: 'sk-ant-...', openai: 'sk-...', gemini: 'AIza...',
            zhipu: 'Your Zhipu API key', dashscope: 'sk-...'
        };
        keyInput.placeholder = placeholders[provider] || 'Paste your API key here';
    }
}

async function saveAiConfig() {
    const provider = document.getElementById('ai-provider')?.value || 'anthropic';
    const apiKey = document.getElementById('ai-api-key')?.value || '';
    const data = {
        llm: {
            provider,
            model: document.getElementById('ai-model')?.value || '',
            temperature: parseFloat(document.getElementById('ai-temperature')?.value || '0.7'),
            max_tokens: 4096
        },
        search: {
            provider: document.getElementById('search-provider')?.value || ''
        }
    };
    if (provider === 'ollama') {
        data.llm.base_url = document.getElementById('ollama-url')?.value || 'http://localhost:11434';
    }
    // Save API key to .env via the save-env endpoint
    if (apiKey && !apiKey.includes('****')) {
        const envKeyMap = {
            anthropic: 'ANTHROPIC_API_KEY', openai: 'OPENAI_API_KEY', gemini: 'GEMINI_API_KEY',
            zhipu: 'ZHIPU_API_KEY', dashscope: 'DASHSCOPE_API_KEY'
        };
        const envKey = envKeyMap[provider];
        if (envKey) await postJSON('/api/save-env', { [envKey]: apiKey });
    }
    const result = await postJSON('/api/save-ai', data);
    showStatus('ai-status', result.ok ? 'Saved!' : 'Error: ' + result.error, result.ok);
}

async function testAiModel() {
    const btn = event.target;
    btn.textContent = 'Testing...';
    btn.disabled = true;
    const data = {
        provider: document.getElementById('ai-provider')?.value,
        model: document.getElementById('ai-model')?.value,
        temperature: parseFloat(document.getElementById('ai-temperature')?.value || '0.7'),
        api_key: document.getElementById('ai-api-key')?.value || ''
    };
    if (data.provider === 'ollama') {
        data.base_url = document.getElementById('ollama-url')?.value;
    }
    const result = await postJSON('/api/test-ai', data);
    showStatus('ai-test-status', result.ok ? 'Connected!' : 'Failed: ' + (result.error || 'Check API key'), result.ok);
    btn.textContent = 'Test Connection';
    btn.disabled = false;
}

// Load AI config on page load
async function loadAiConfig() {
    try {
        const resp = await fetch('/api/ai-config');
        const data = await resp.json();
        if (data.llm) {
            const providerEl = document.getElementById('ai-provider');
            if (providerEl) { providerEl.value = data.llm.provider || 'anthropic'; onProviderChange(); }
            const modelEl = document.getElementById('ai-model');
            if (modelEl && data.llm.model) modelEl.value = data.llm.model;
            const tempEl = document.getElementById('ai-temperature');
            if (tempEl && data.llm.temperature != null) {
                tempEl.value = data.llm.temperature;
                document.getElementById('temp-val').textContent = data.llm.temperature;
            }
        }
        if (data.search) {
            const searchEl = document.getElementById('search-provider');
            if (searchEl) searchEl.value = data.search.provider || '';
        }
    } catch(e) {}
}

// Init
document.addEventListener('DOMContentLoaded', () => {
    recalcTotal();
    onProviderChange();
    loadAiConfig();
});
