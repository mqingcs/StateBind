const $ = (id) => document.getElementById(id);
const COLORS = { axis: '#d2b36d', target: '#ff756f', low: '#6f9cff', high: '#43c4bd' };
const HINTS = {
  axis: '轴线：沿实际读数方向点击两个相距较远的点。',
  target: '真实状态：区间点两端；单点在同处点两次；长度题点物体起点与终点。',
  low: '低值刻度：点击目标附近较低数值的最小刻度线中心。',
  high: '高值刻度：点击与低值点相邻、数值更高的最小刻度线中心。'
};

let state = { tasks: [], annotations: {} };
let index = 0;
let tool = 'axis';
let geometry = blankGeometry();
let history = [];
let zoom = 1;
let image = new Image();
let startedAt = Date.now();
let dirty = false;

function blankGeometry() {
  return { axis: [], target: [], low: null, high: null };
}

function currentTask() { return state.tasks[index]; }
function clone(value) { return JSON.parse(JSON.stringify(value)); }

function annotationToGeometry(annotation) {
  if (!annotation || !annotation.include) return blankGeometry();
  return {
    axis: [annotation.axis_start_xy, annotation.axis_end_xy].map(clone),
    target: (annotation.target_state_interval_raw_xy || []).map(clone),
    low: clone(annotation.low_value_tick_raw_xy),
    high: clone(annotation.high_value_tick_raw_xy)
  };
}

function setTool(next) {
  tool = next;
  document.querySelectorAll('.tool').forEach((button) => button.classList.toggle('active', button.dataset.tool === tool));
  $('toolHint').textContent = HINTS[tool];
}

function setSegment(group, value) {
  document.querySelectorAll(`#${group} button`).forEach((button) => button.classList.toggle('active', button.dataset.value === value));
  if (group === 'visibilityGroup') $('excludeReason').classList.toggle('visible', value === 'exclude');
}

function selectedValue(group) {
  return document.querySelector(`#${group} button.active`)?.dataset.value || '';
}

function updateProgress() {
  const done = Object.keys(state.annotations).length;
  $('progressCount').textContent = `${done} / ${state.tasks.length}`;
  $('progressBar').style.width = `${100 * done / state.tasks.length}%`;
}

function renderTaskList() {
  const list = $('taskList');
  list.textContent = '';
  state.tasks.forEach((task, taskIndex) => {
    const saved = state.annotations[task.review_id];
    const button = document.createElement('button');
    button.type = 'button';
    button.className = `task-item${taskIndex === index ? ' active' : ''}${saved ? (saved.visibility === 'exclude' ? ' excluded' : ' saved') : ''}`;
    button.innerHTML = `<span class="task-number">${String(taskIndex + 1).padStart(2, '0')}</span><span class="task-title">${task.question}</span><i class="task-status"></i>`;
    button.addEventListener('click', () => loadTask(taskIndex));
    list.appendChild(button);
  });
  list.querySelector('.active')?.scrollIntoView({ block: 'nearest' });
  updateProgress();
}

function loadForm(annotation) {
  const prefill = currentTask()?.prefill || {};
  $('minorTick').value = annotation?.minor_tick_value ?? prefill.minor_tick_value ?? '';
  $('unit').value = annotation?.unit ?? prefill.unit ?? '';
  $('branch').value = annotation?.scale_branch ?? prefill.scale_branch ?? '';
  $('notes').value = annotation?.notes ?? '';
  $('excludeReason').value = annotation?.exclude_reason ?? '';
  setSegment('ruleGroup', annotation?.target_rule ?? prefill.target_rule ?? '');
  setSegment('visibilityGroup', annotation?.visibility ?? '');
}

function loadTask(nextIndex) {
  index = (nextIndex + state.tasks.length) % state.tasks.length;
  const task = currentTask();
  const annotation = state.annotations[task.review_id];
  geometry = annotationToGeometry(annotation);
  history = [];
  dirty = false;
  startedAt = Date.now();
  loadForm(annotation);
  $('sampleIndex').textContent = task.review_id.toUpperCase().replace('_', '—');
  $('question').textContent = task.question;
  $('autosaveState').textContent = annotation ? '已从本地结果恢复' : '尚未保存';
  $('error').textContent = '';
  $('loading').style.display = 'flex';
  image = new Image();
  image.onload = () => {
    const canvas = $('canvas');
    canvas.width = image.naturalWidth;
    canvas.height = image.naturalHeight;
    zoomFit();
    draw();
    $('loading').style.display = 'none';
  };
  image.src = `${task.image_url}?v=${Date.now()}`;
  renderTaskList();
  updateSteps();
}

function updateSteps() {
  $('stepAxis').classList.toggle('done', geometry.axis.length === 2);
  $('stepTarget').classList.toggle('done', geometry.target.length === 2);
  $('stepLow').classList.toggle('done', !!geometry.low);
  $('stepHigh').classList.toggle('done', !!geometry.high);
}

function drawPoint(context, point, color, radius = 4.2) {
  if (!point) return;
  context.beginPath();
  context.arc(point[0], point[1], radius, 0, Math.PI * 2);
  context.fillStyle = color;
  context.fill();
  context.strokeStyle = 'rgba(10,12,13,.88)';
  context.lineWidth = 1.4;
  context.stroke();
}

function drawPair(context, points, color, lineWidth = 2) {
  if (points.length === 2) {
    context.beginPath();
    context.moveTo(points[0][0], points[0][1]);
    context.lineTo(points[1][0], points[1][1]);
    context.strokeStyle = color;
    context.lineWidth = lineWidth;
    context.stroke();
  }
  points.forEach((point) => drawPoint(context, point, color));
}

function draw() {
  if (!image.complete || !image.naturalWidth) return;
  const canvas = $('canvas');
  const context = canvas.getContext('2d');
  context.clearRect(0, 0, canvas.width, canvas.height);
  context.drawImage(image, 0, 0);
  drawPair(context, geometry.axis, COLORS.axis, 1.6);
  drawPair(context, geometry.target, COLORS.target, 2.2);
  drawPoint(context, geometry.low, COLORS.low);
  drawPoint(context, geometry.high, COLORS.high);
  updateSteps();
}

function canvasPoint(event) {
  const canvas = $('canvas');
  const box = canvas.getBoundingClientRect();
  return [
    (event.clientX - box.left) * canvas.width / box.width,
    (event.clientY - box.top) * canvas.height / box.height
  ];
}

function applyPoint(event) {
  const point = canvasPoint(event);
  history.push(clone(geometry));
  if (tool === 'axis' || tool === 'target') {
    const key = tool;
    if (geometry[key].length < 2) geometry[key].push(point);
    else {
      const distances = geometry[key].map((item) => Math.hypot(item[0] - point[0], item[1] - point[1]));
      geometry[key][distances[0] <= distances[1] ? 0 : 1] = point;
    }
  } else geometry[tool] = point;
  dirty = true;
  $('autosaveState').textContent = '本张有未保存修改';
  draw();
}

function undo() {
  if (!history.length) return;
  geometry = history.pop();
  dirty = true;
  $('autosaveState').textContent = '已撤销，尚未保存';
  draw();
}

function clearGeometry() {
  history.push(clone(geometry));
  geometry = blankGeometry();
  dirty = true;
  $('autosaveState').textContent = '坐标已清空，尚未保存';
  draw();
}

function applyZoom() {
  const canvas = $('canvas');
  canvas.style.width = `${Math.round(image.naturalWidth * zoom)}px`;
  canvas.style.height = `${Math.round(image.naturalHeight * zoom)}px`;
  $('zoomFit').textContent = `${Math.round(zoom * 100)}%`;
}

function zoomFit() {
  const stage = $('imageStage');
  const availableWidth = Math.max(320, stage.clientWidth - 48);
  const availableHeight = Math.max(240, stage.clientHeight - 48);
  zoom = Math.min(1, availableWidth / image.naturalWidth, availableHeight / image.naturalHeight);
  applyZoom();
}

function changeZoom(multiplier) {
  zoom = Math.max(.25, Math.min(3, zoom * multiplier));
  applyZoom();
}

function payload() {
  return {
    review_id: currentTask().review_id,
    axis_xy: geometry.axis,
    target_state_interval_xy: geometry.target,
    low_value_tick_xy: geometry.low,
    high_value_tick_xy: geometry.high,
    minor_tick_value: $('minorTick').value,
    unit: $('unit').value,
    scale_branch: $('branch').value,
    target_rule: selectedValue('ruleGroup'),
    visibility: selectedValue('visibilityGroup'),
    exclude_reason: $('excludeReason').value,
    notes: $('notes').value,
    active_seconds: (Date.now() - startedAt) / 1000
  };
}

async function save() {
  $('error').textContent = '';
  $('save').disabled = true;
  try {
    const response = await fetch('/api/annotation', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload())
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || '保存失败');
    state.annotations[currentTask().review_id] = result.annotation;
    dirty = false;
    $('autosaveState').textContent = '已原子保存';
    renderTaskList();
    const nextPending = state.tasks.findIndex((task, taskIndex) => taskIndex > index && !state.annotations[task.review_id]);
    loadTask(nextPending >= 0 ? nextPending : index + 1);
  } catch (error) {
    $('error').textContent = error.message;
  } finally {
    $('save').disabled = false;
  }
}

async function deleteSaved() {
  const reviewId = currentTask().review_id;
  if (!state.annotations[reviewId]) return;
  const response = await fetch('/api/annotation/delete', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ review_id: reviewId })
  });
  if (!response.ok) return;
  delete state.annotations[reviewId];
  loadTask(index);
}

function firstPending() {
  const pending = state.tasks.findIndex((task) => !state.annotations[task.review_id]);
  loadTask(pending >= 0 ? pending : 0);
}

document.querySelectorAll('.tool').forEach((button) => button.addEventListener('click', () => setTool(button.dataset.tool)));
document.querySelectorAll('#ruleGroup button, #visibilityGroup button').forEach((button) => button.addEventListener('click', () => {
  setSegment(button.parentElement.id, button.dataset.value);
  dirty = true;
}));
$('canvas').addEventListener('click', applyPoint);
$('undo').addEventListener('click', undo);
$('clearPoints').addEventListener('click', clearGeometry);
$('zoomOut').addEventListener('click', () => changeZoom(.82));
$('zoomIn').addEventListener('click', () => changeZoom(1.22));
$('zoomFit').addEventListener('click', zoomFit);
$('previous').addEventListener('click', () => loadTask(index - 1));
$('next').addEventListener('click', () => loadTask(index + 1));
$('jumpPending').addEventListener('click', firstPending);
$('save').addEventListener('click', save);
$('deleteAnnotation').addEventListener('click', deleteSaved);
document.querySelectorAll('input, textarea').forEach((input) => input.addEventListener('input', () => {
  dirty = true;
  $('autosaveState').textContent = '本张有未保存修改';
}));

window.addEventListener('keydown', (event) => {
  if (['INPUT', 'TEXTAREA'].includes(document.activeElement.tagName)) {
    if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') { event.preventDefault(); save(); }
    return;
  }
  if (['1', '2', '3', '4'].includes(event.key)) setTool(['axis', 'target', 'low', 'high'][Number(event.key) - 1]);
  if (event.key.toLowerCase() === 'z') undo();
  if (event.key === '[') loadTask(index - 1);
  if (event.key === ']') loadTask(index + 1);
  if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') { event.preventDefault(); save(); }
});

window.addEventListener('beforeunload', (event) => {
  if (!dirty) return;
  event.preventDefault();
  event.returnValue = '';
});

fetch('/api/state')
  .then((response) => response.json())
  .then((result) => {
    state = result;
    const first = state.tasks.findIndex((task) => !state.annotations[task.review_id]);
    loadTask(first >= 0 ? first : 0);
  })
  .catch((error) => { $('error').textContent = `无法加载任务：${error.message}`; });
