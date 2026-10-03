const $ = id => document.getElementById(id);
let files = [];
let selectedFileIndex = null;
let folderPickerOpen = false;

async function api(url, options = {}) {
  const response = await fetch(url, {headers: {'Content-Type': 'application/json'}, ...options});
  const data = await response.json();
  if (!response.ok) throw Error(data.error || 'Request failed');
  return data;
}

async function scan() {
  try {
    const data = await api('/api/scan-folder', {method: 'POST', body: JSON.stringify({folder: $('folder').value})});
    files = data.files;
    selectedFileIndex = null;
    $('scan-status').textContent = `${files.length} PDF(s) found`;
    renderFiles();
    files.forEach((_, index) => { loadToc(index).catch(() => {}); });
  } catch (error) {
    $('scan-status').textContent = error.message;
  }
}

async function selectFolder(button, inputId, title) {
  if (folderPickerOpen) return;
  folderPickerOpen = true;
  const buttons = document.querySelectorAll('.folder-picker button');
  buttons.forEach(folderButton => { folderButton.disabled = true; });
  try {
    const data = await api('/api/select-folder', {method: 'POST', body: JSON.stringify({initial: $(inputId).value, title})});
    if (data.folder) $(inputId).value = data.folder;
  } catch (error) {
    alert(error.message);
  } finally {
    folderPickerOpen = false;
    buttons.forEach(folderButton => { folderButton.disabled = false; });
  }
}

function chapterOptions(index) {
  const toc = files[index].toc;
  if (!toc) return '<option value="">Loading chapters…</option>';
  if (!toc.length) return '<option value="">No embedded chapters available</option>';
  return '<option value="">Select a chapter…</option>' + toc.map(entry =>
    `<option value="${h(entry.title)}">${'\u00a0\u00a0'.repeat(Math.max(0, entry.level - 1))}${h(entry.title)} — P. ${entry.page}</option>`
  ).join('');
}

function tableOfContentsRows(toc) {
  return toc.map(entry => `<div class="toc-row" style="padding:.35rem .55rem .35rem ${.55 + Math.max(0, entry.level - 1) * 1.25}rem"><span class="toc-title">${h(entry.title)}</span><span class="toc-page">P. ${entry.page}</span></div>`).join('');
}

function renderFiles() {
  if (!files.length) {
    $('files').innerHTML = 'No PDFs found.';
    return;
  }

  const selectedFile = selectedFileIndex === null ? null : files[selectedFileIndex];
  const picker = `<label>PDF to configure<select id="pdf-selector" onchange="selectFile(this.value)">
    <option value="">Choose a PDF…</option>
    ${files.map((file, index) => `<option value="${index}" ${index === selectedFileIndex ? 'selected' : ''}>${h(file.name)} (${Math.round(file.size / 1024)} KB)</option>`).join('')}
  </select></label>`;

  $('files').innerHTML = picker + (selectedFile ? renderFile(selectedFile, selectedFileIndex) : '<p class="muted">Choose a PDF to configure its transcription.</p>');
}

function selectFile(value) {
  selectedFileIndex = value === '' ? null : Number(value);
  if (!Number.isInteger(selectedFileIndex) || !files[selectedFileIndex]) selectedFileIndex = null;
  renderFiles();
}

function renderFile(file, index) {
  return `<div class="pdf">
    <strong>${h(file.name)}</strong> <span class="muted">${Math.round(file.size / 1024)} KB</span>
    <button onclick="inspect(${index})">Inspect Table of Contents</button><div id="toc-${index}"></div>
    <div class="grid">
      <label>Mode<select id="mode-${index}" onchange="toggleMode(${index})"><option value="pages">Page range</option><option value="chapter">Chapter</option></select></label>
      <label id="range-${index}">Pages<input id="pages-${index}" placeholder="1-10"></label>
      <label id="chapter-${index}" style="display:none">Chapter<select id="query-${index}" ${file.toc && file.toc.length ? '' : 'disabled'}>${chapterOptions(index)}</select></label>
    </div>
    <label class="option-row"><span>Disable formula OCR <span class="muted">— skip recognition of equations and keep formula images for review.</span></span><input type="checkbox" id="noocr-${index}" checked></label>
    <label class="option-row"><span>Allow scanned pages <span class="muted">— continue when pages are images; they are saved for manual transcription rather than automatically OCRed.</span></span><input type="checkbox" id="allow-${index}"></label>
    <label class="option-row"><span>Prose mode <span class="muted">— for novels and text-heavy books: skip formula OCR and replace figures with page-referenced notes.</span></span><input type="checkbox" id="prose-${index}"></label>
    <button onclick="queueJob(${index})">Queue this PDF</button> <span id="msg-${index}" class="muted"></span>
  </div>`;
}

function updateChapterMenu(index) {
  const menu = $('query-' + index);
  if (!menu) return;
  const selected = menu.value;
  menu.innerHTML = chapterOptions(index);
  menu.disabled = !files[index].toc || !files[index].toc.length;
  if ([...menu.options].some(option => option.value === selected)) menu.value = selected;
}

function toggleMode(index) {
  const chapterMode = $('mode-' + index).value === 'chapter';
  $('range-' + index).style.display = chapterMode ? 'none' : '';
  $('chapter-' + index).style.display = chapterMode ? '' : 'none';
}

async function loadToc(index) {
  try {
    const data = await api(`/api/pdf/toc?path=${encodeURIComponent(files[index].path)}&folder=${encodeURIComponent($('folder').value)}`);
    files[index].toc = data.toc;
    files[index].pageCount = data.page_count;
    updateChapterMenu(index);
    return data;
  } catch (error) {
    files[index].toc = [];
    updateChapterMenu(index);
    throw error;
  }
}

async function inspect(index) {
  try {
    const data = files[index].toc ? {toc: files[index].toc, page_count: files[index].pageCount} : await loadToc(index);
    $('toc-' + index).innerHTML = data.toc.length
      ? '<details open><summary>Table of Contents (' + data.page_count + ' pages)</summary><div class="toc-list">' + tableOfContentsRows(data.toc) + '</div></details>'
      : '<span class="muted">No embedded Table of Contents; use pages.</span>';
  } catch (error) {
    $('toc-' + index).textContent = error.message;
  }
}

async function queueJob(index) {
  try {
    const mode = $('mode-' + index).value;
    const range = ($('pages-' + index).value || '').match(/^(\d+)-(\d+)$/);
    const payload = {input_root: $('folder').value, output_root: $('output').value, source_pdf: files[index].path, selection_type: mode, chapter_query: $('query-' + index).value, page_start: range && range[1], page_end: range && range[2], no_formula_ocr: $('noocr-' + index).checked, allow_scanned: $('allow-' + index).checked, prose: $('prose-' + index).checked};
    await api('/api/jobs', {method: 'POST', body: JSON.stringify(payload)});
    $('msg-' + index).textContent = 'Queued';
    loadJobs();
  } catch (error) {
    $('msg-' + index).textContent = error.message;
  }
}
function jobState(status) {
  return {
    queued: {icon: '&#9654;', label: 'Queued — not started', className: 'queued'},
    running: {icon: '&#9654;', label: 'Transcribing', className: 'running'},
    completed: {icon: '&#10003;', label: 'Completed', className: 'completed'},
    failed: {icon: '!', label: 'Needs attention', className: 'failed'}
  }[status] || {icon: '?', label: status, className: 'failed'};
}

function formatDate(value) {
  return value ? new Intl.DateTimeFormat(undefined, {dateStyle: 'medium', timeStyle: 'medium'}).format(new Date(value)) : '—';
}

function transcriptionDuration(job) {
  if (!job.started_at) return 'Not started';
  const seconds = Math.max(0, Math.floor(((job.finished_at ? new Date(job.finished_at) : new Date()) - new Date(job.started_at)) / 1000));
  const hours = Math.floor(seconds / 3600), minutes = Math.floor((seconds % 3600) / 60), remainingSeconds = seconds % 60;
  const text = [hours && `${hours}h`, minutes && `${minutes}m`, `${remainingSeconds}s`].filter(Boolean).join(' ');
  return job.finished_at ? `Took ${text}` : `Running for ${text}`;
}

function jobSelection(job) {
  return job.selection_type === 'chapter' ? `Chapter: ${job.chapter_query}` : `Pages: ${job.page_start}-${job.page_end}`;
}

function jobCard(job) {
  const state = jobState(job.status);
  const fileName = job.source_pdf.split(/[\\/]/).pop();
  return `<article class="job">
    <span class="job-status ${state.className}" role="img" aria-label="${h(state.label)}" title="${h(state.label)}">${state.icon}</span>
    <div class="job-body">
      <div class="job-heading" style="display:flex;justify-content:space-between;gap:.75rem;flex-wrap:wrap"><strong>${h(fileName)}</strong><span class="job-selection">${h(jobSelection(job))}</span></div>
      <div class="job-meta"><span>${h(state.label)}</span><span>Added ${formatDate(job.created_at)}</span>${job.started_at ? `<span>Started ${formatDate(job.started_at)}</span>` : ''}${job.finished_at ? `<span>Finished ${formatDate(job.finished_at)}</span>` : ''}<span>${transcriptionDuration(job)}</span></div>
      ${job.error ? `<div class="job-error">${h(job.error)}</div>` : ''}
      <div class="job-actions">${job.status === 'queued' ? `<button class="secondary" onclick="runJob('${job.id}')">Run job</button>` : ''}${job.status === 'completed' ? `<button class="secondary" onclick="openOutput('${job.id}')">Open output folder</button><button class="secondary" onclick="review('${job.id}')">Review</button>` : ''}<button class="icon-button danger" onclick="deleteJob('${job.id}')" title="Remove job from the queue (keeps output files)" aria-label="Remove job from the queue">&#128465;</button></div>
      <div id="log-${job.id}"></div>
    </div>
  </article>`;
}

async function openOutput(id) {
  try {
    await api('/api/jobs/' + id + '/open-output', {method: 'POST'});
  } catch (error) {
    alert(error.message);
  }
}

async function runJob(id) {
  try {
    await api('/api/jobs/' + id + '/start', {method: 'POST'});
    loadJobs();
  } catch (error) {
    alert(error.message);
  }
}

async function deleteJob(id) {
  if (!confirm('Remove this job from the queue? If it is running, transcription will stop. Generated output files will be kept.')) return;
  try {
    await api('/api/jobs/' + id, {method: 'DELETE'});
    loadJobs();
  } catch (error) {
    alert(error.message);
  }
}

async function loadJobs() {
  const jobs = await api('/api/jobs');
  jobs.sort((left, right) => new Date(right.created_at) - new Date(left.created_at));
  $('jobs').innerHTML = jobs.length ? `<div class="job-list-header" style="display:grid;grid-template-columns:2rem 1fr;gap:.75rem;padding:.25rem 0;color:#647484;font-size:.9rem;font-weight:700"><span>Status</span><span>Job</span></div><div class="job-list">${jobs.map(jobCard).join('')}</div>` : 'No jobs queued.';
  jobs.filter(job => ['queued', 'running'].includes(job.status)).forEach(job => listen(job.id));
}
function listen(id){if(window['seen-'+id])return;window['seen-'+id]=1;const es=new EventSource('/api/jobs/'+id+'/events');es.onmessage=e=>{const x=JSON.parse(e.data),el=$('log-'+id);if(el)el.innerHTML='<pre>'+h((el.textContent+'\n'+x.message).trim())+'</pre>';if(['completed','failed'].includes(x.kind)){es.close();loadJobs()}}}
async function review(id){const d=await api('/api/jobs/'+id+'/markdown'),m=await api('/api/jobs/'+id+'/manifest'),w=open('','_blank'),refs=m.pending_image_refs||[];w.document.write(`<title>Review</title><h1>Manifest</h1><pre>${h(JSON.stringify(m,null,2))}</pre><h2>Pending image references</h2>${refs.length?refs.map((r,i)=>`<div><code>${h(r)}</code><textarea id="r${i}" rows="3" cols="80" placeholder="LaTeX or a faithful figure description"></textarea><button onclick="save(${i})">Replace</button></div>`).join(''):'<p>None.</p>'}<button onclick="finish()">Finalize</button><h2>Markdown</h2><pre>${h(d.markdown)}</pre><script>const refs=${JSON.stringify(refs)};async function save(i){const replacement=document.getElementById('r'+i).value;const r=await fetch('/api/jobs/${id}/placeholder',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({image_ref:'![]('+refs[i]+')',replacement})});alert(r.ok?'Saved':'Failed to save')}async function finish(){const r=await fetch('/api/jobs/${id}/finalize',{method:'POST'});alert(r.ok?'Finalized':'Resolve every image reference first')}</script>`)}
function h(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
$('scan').onclick=scan;$('start').onclick=async()=>{await api('/api/jobs/start',{method:'POST'});loadJobs()};loadJobs();
