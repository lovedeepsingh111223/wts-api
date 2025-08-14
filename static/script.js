let stepIndex = 0;

function addFunnelStep() {
  const container = document.getElementById('funnelSteps');
  const div = document.createElement('div');
  div.className = 'step-box';
  div.innerHTML = `
    <h4>Step ${stepIndex + 1}</h4>
    <label>Message:</label>
    <textarea id="step-msg-${stepIndex}"></textarea>
    <label>Delay (in seconds):</label>
    <input type="number" id="step-delay-${stepIndex}" value="5" />
  `;
  container.appendChild(div);
  stepIndex++;
}

function saveFunnel() {
  const keyword = document.getElementById('triggerKeyword').value.trim().toLowerCase();
  if (!keyword) return alert("❌ Please enter a trigger keyword");

  const steps = [];
  for (let i = 0; i < stepIndex; i++) {
    const msg = document.getElementById(`step-msg-${i}`).value;
    const delay = parseInt(document.getElementById(`step-delay-${i}`).value || '5');
    if (msg) steps.push({ message: msg, delay });
  }

  if (steps.length === 0) return alert("❌ Add at least one message step");

  fetch('/save-funnel', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ keyword, steps })
  })
    .then(res => res.text())
    .then(alert)
    .then(() => location.reload());
}

function sendTestMessage() {
  const number = document.getElementById('testNumber').value.trim();
  const message = document.getElementById('testMessage').value.trim();
  if (!number || !message) return alert("❌ Number or message missing");

  fetch(`/send-message?number=${number}&message=${encodeURIComponent(message)}`)
    .then(res => res.text())
    .then(alert);
}

function fetchFunnels() {
  fetch('/funnels')
    .then(res => res.json())
    .then(data => {
      const ul = document.getElementById('savedFunnels');
      ul.innerHTML = '';
      for (let keyword in data) {
        const li = document.createElement('li');
        li.innerHTML = `
          <b>${keyword}</b> - ${data[keyword].length} step(s)
          <button onclick="deleteFunnel('${keyword}')">🗑️ Delete</button>
        `;
        ul.appendChild(li);
      }
    });
}

function deleteFunnel(keyword) {
  if (!confirm(`Delete funnel: "${keyword}"?`)) return;

  fetch(`/delete-funnel?keyword=${keyword}`, { method: 'DELETE' })
    .then(res => res.text())
    .then(alert)
    .then(fetchFunnels);
}

function fetchLogs() {
  fetch('/logs')
    .then(res => res.text())
    .then(data => {
      document.getElementById('logPanel').textContent = data || 'No logs yet.';
    });
}

function fetchTemplates() {
  fetch('/templates')
    .then(res => res.json())
    .then(templates => {
      const dropdown = document.getElementById('templateDropdown');
      dropdown.innerHTML = `<option value="">Select a template</option>`;
      templates.forEach(name => {
        const option = document.createElement('option');
        option.value = name;
        option.textContent = name;
        dropdown.appendChild(option);
      });
    });
}

addFunnelStep();
fetchFunnels();
fetchLogs();
fetchTemplates();
