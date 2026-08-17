// ---------------------------------------------------------------------------
// Kids Crossword Fun
// Puzzle grids are small hand-built "comb" crosswords: one across "spine"
// word on row 0, with short down words hanging from some of its letters.
// `null` in a grid row means a black (blocked) square.
// ---------------------------------------------------------------------------

const PUZZLES = [
  {
    id: 'jungle',
    title: 'Jungle Friends',
    emoji: '🐵',
    difficulty: 'easy',
    grid: [
      ['M', 'O', 'N', 'K', 'E', 'Y'],
      ['O', 'W', 'U', 'I', 'G', null],
      ['O', 'L', 'T', 'T', 'G', null],
    ],
    words: [
      { answer: 'MONKEY', row: 0, col: 0, dir: 'across', clue: 'A silly animal that loves bananas 🍌' },
      { answer: 'MOO', row: 0, col: 0, dir: 'down', clue: 'The sound a cow makes' },
      { answer: 'OWL', row: 0, col: 1, dir: 'down', clue: "A bird that says “who, who” at night" },
      { answer: 'NUT', row: 0, col: 2, dir: 'down', clue: 'A squirrel loves to eat this' },
      { answer: 'KIT', row: 0, col: 3, dir: 'down', clue: 'A baby fox is called a ___' },
      { answer: 'EGG', row: 0, col: 4, dir: 'down', clue: 'A hen lays this' },
    ],
  },
  {
    id: 'ocean',
    title: 'Ocean Adventure',
    emoji: '🐬',
    difficulty: 'medium',
    grid: [
      ['D', 'O', 'L', 'P', 'H', 'I', 'N'],
      ['E', 'A', null, 'E', 'A', 'C', 'A'],
      ['N', 'R', null, 'N', 'T', 'E', 'P'],
    ],
    words: [
      { answer: 'DOLPHIN', row: 0, col: 0, dir: 'across', clue: 'A smart, friendly animal that jumps out of the ocean 🐬' },
      { answer: 'DEN', row: 0, col: 0, dir: 'down', clue: "A fox or bear's cozy home" },
      { answer: 'OAR', row: 0, col: 1, dir: 'down', clue: 'You use this to row a boat' },
      { answer: 'PEN', row: 0, col: 3, dir: 'down', clue: 'You use this to write' },
      { answer: 'HAT', row: 0, col: 4, dir: 'down', clue: 'You wear this on your head' },
      { answer: 'ICE', row: 0, col: 5, dir: 'down', clue: 'Frozen water' },
      { answer: 'NAP', row: 0, col: 6, dir: 'down', clue: 'A short sleep in the afternoon' },
    ],
  },
  {
    id: 'rainbow',
    title: 'Rainbow Colors',
    emoji: '🌈',
    difficulty: 'medium',
    grid: [
      ['R', 'A', 'I', 'N', 'B', 'O', 'W'],
      ['U', 'N', 'C', 'E', 'U', 'W', 'E'],
      ['G', 'T', 'E', 'T', 'S', 'L', 'B'],
    ],
    words: [
      { answer: 'RAINBOW', row: 0, col: 0, dir: 'across', clue: 'Colorful arc that appears in the sky after it rains 🌈' },
      { answer: 'RUG', row: 0, col: 0, dir: 'down', clue: 'A soft mat on the floor' },
      { answer: 'ANT', row: 0, col: 1, dir: 'down', clue: 'A tiny bug that lives with many others in a colony' },
      { answer: 'ICE', row: 0, col: 2, dir: 'down', clue: 'Frozen water, cold and slippery' },
      { answer: 'NET', row: 0, col: 3, dir: 'down', clue: 'You use this to catch butterflies or fish' },
      { answer: 'BUS', row: 0, col: 4, dir: 'down', clue: 'A big yellow vehicle that takes kids to school' },
      { answer: 'OWL', row: 0, col: 5, dir: 'down', clue: 'A wise bird that hoots at night' },
      { answer: 'WEB', row: 0, col: 6, dir: 'down', clue: 'A spider spins this' },
    ],
  },
  {
    id: 'farm',
    title: 'Farm Friends',
    emoji: '🐔',
    difficulty: 'medium',
    grid: [
      ['C', 'H', 'I', 'C', 'K', 'E', 'N'],
      ['O', 'E', 'N', 'A', 'I', 'G', 'A'],
      ['W', 'N', 'K', 'T', 'D', 'G', 'P'],
    ],
    words: [
      { answer: 'CHICKEN', row: 0, col: 0, dir: 'across', clue: 'A farm bird that lays eggs and says cluck-cluck 🐔' },
      { answer: 'COW', row: 0, col: 0, dir: 'down', clue: 'A farm animal that gives us milk' },
      { answer: 'HEN', row: 0, col: 1, dir: 'down', clue: 'A female chicken' },
      { answer: 'INK', row: 0, col: 2, dir: 'down', clue: 'You put this in a pen to write' },
      { answer: 'CAT', row: 0, col: 3, dir: 'down', clue: 'A furry pet that says meow' },
      { answer: 'KID', row: 0, col: 4, dir: 'down', clue: 'A baby goat' },
      { answer: 'EGG', row: 0, col: 5, dir: 'down', clue: 'Chickens lay this' },
      { answer: 'NAP', row: 0, col: 6, dir: 'down', clue: 'A short sleep' },
    ],
  },
];

const STORAGE_KEY = 'kids-crossword-completed';

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
let currentPuzzle = null;
let cellMeta = null;      // [r][c] -> null | { solution, number, acrossEntry, downEntry }
let entries = [];         // list of { number, dir, row, col, cells:[{r,c}], answer, clue }
let inputEls = null;      // [r][c] -> input element or null
let activeCell = null;    // { r, c }
let activeDir = 'across';
let timerHandle = null;
let secondsElapsed = 0;
let hasWon = false;

// ---------------------------------------------------------------------------
// Elements
// ---------------------------------------------------------------------------
const pickerScreen = document.getElementById('pickerScreen');
const gameScreen = document.getElementById('gameScreen');
const puzzleGridEl = document.getElementById('puzzleGrid');
const crosswordGridEl = document.getElementById('crosswordGrid');
const acrossCluesEl = document.getElementById('acrossClues');
const downCluesEl = document.getElementById('downClues');
const gameTitleEl = document.getElementById('gameTitle');
const feedbackMsgEl = document.getElementById('feedbackMsg');
const statsBarEl = document.getElementById('statsBar');
const timerDisplayEl = document.getElementById('timerDisplay');
const scoreDisplayEl = document.getElementById('scoreDisplay');
const dirLabelEl = document.getElementById('dirLabel');
const winModal = document.getElementById('winModal');
const winMsgEl = document.getElementById('winMsg');

// ---------------------------------------------------------------------------
// Completed puzzles (localStorage)
// ---------------------------------------------------------------------------
function getCompleted() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY)) || [];
  } catch (e) {
    return [];
  }
}
function markCompleted(id) {
  const done = new Set(getCompleted());
  done.add(id);
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify([...done]));
  } catch (e) { /* ignore */ }
}

// ---------------------------------------------------------------------------
// Puzzle picker screen
// ---------------------------------------------------------------------------
function renderPicker() {
  const completed = new Set(getCompleted());
  puzzleGridEl.innerHTML = '';
  PUZZLES.forEach((p) => {
    const card = document.createElement('button');
    card.className = 'puzzle-card';
    card.setAttribute('aria-label', `Play ${p.title}`);
    const isDone = completed.has(p.id);
    card.innerHTML = `
      <span class="card-emoji">${p.emoji}</span>
      <h3>${p.title}</h3>
      <div class="card-meta">${p.words.length} words</div>
      <span class="badge ${p.difficulty}">${p.difficulty === 'easy' ? 'Easy' : 'Medium'}</span>
      ${isDone ? '<span class="badge done">✔ Done</span>' : ''}
    `;
    card.addEventListener('click', () => loadPuzzle(p.id));
    puzzleGridEl.appendChild(card);
  });
}

function showPicker() {
  stopTimer();
  gameScreen.classList.add('hidden');
  statsBarEl.classList.add('hidden');
  pickerScreen.classList.remove('hidden');
  renderPicker();
}

// ---------------------------------------------------------------------------
// Build puzzle data structures (numbering, entries) from a grid definition
// ---------------------------------------------------------------------------
function buildPuzzle(puzzle) {
  const grid = puzzle.grid;
  const rows = grid.length;
  const cols = grid[0].length;

  const meta = grid.map((row) =>
    row.map((ch) => (ch === null ? null : { solution: ch, number: null, acrossEntry: null, downEntry: null }))
  );

  // Build entries directly from the puzzle's explicit word list rather than
  // scanning the grid for word boundaries. Scanning would also pick up
  // incidental (unclued) letter runs in the filler rows below the spine
  // word, which aren't real answers.
  const builtEntries = puzzle.words.map((w) => {
    const cells = [];
    for (let i = 0; i < w.answer.length; i++) {
      const r = w.row + (w.dir === 'down' ? i : 0);
      const c = w.col + (w.dir === 'across' ? i : 0);
      cells.push({ r, c });
    }
    return { number: null, dir: w.dir, row: w.row, col: w.col, cells, answer: w.answer, clue: w.clue };
  });

  // Number cells in standard reading order (top-to-bottom, left-to-right);
  // an across and down entry that share a start cell share one number.
  const startKeys = [...new Set(builtEntries.map((e) => `${e.row},${e.col}`))].sort((a, b) => {
    const [ar, ac] = a.split(',').map(Number);
    const [br, bc] = b.split(',').map(Number);
    return ar - br || ac - bc;
  });
  const numberByKey = new Map(startKeys.map((key, i) => [key, i + 1]));

  builtEntries.forEach((entry) => {
    entry.number = numberByKey.get(`${entry.row},${entry.col}`);
    meta[entry.row][entry.col].number = entry.number;
    entry.cells.forEach(({ r, c }) => {
      if (entry.dir === 'across') meta[r][c].acrossEntry = entry;
      else meta[r][c].downEntry = entry;
    });
  });

  return { rows, cols, meta, entries: builtEntries };
}

// ---------------------------------------------------------------------------
// Load & render a puzzle into the game screen
// ---------------------------------------------------------------------------
function loadPuzzle(id) {
  const puzzle = PUZZLES.find((p) => p.id === id);
  if (!puzzle) return;
  currentPuzzle = puzzle;

  const built = buildPuzzle(puzzle);
  cellMeta = built.meta;
  entries = built.entries;
  hasWon = false;
  secondsElapsed = 0;

  pickerScreen.classList.add('hidden');
  gameScreen.classList.remove('hidden');
  statsBarEl.classList.remove('hidden');
  gameTitleEl.textContent = `${puzzle.emoji} ${puzzle.title}`;
  feedbackMsgEl.textContent = '';
  winModal.classList.add('hidden');

  renderGrid(built.rows, built.cols);
  renderClues();

  activeDir = 'across';
  const firstEntry = entries.find((e) => e.dir === 'across') || entries[0];
  if (firstEntry) setActiveEntry(firstEntry, true);

  updateScore();
  startTimer();
}

function renderGrid(rows, cols) {
  crosswordGridEl.innerHTML = '';
  crosswordGridEl.style.gridTemplateColumns = `repeat(${cols}, auto)`;
  inputEls = Array.from({ length: rows }, () => new Array(cols).fill(null));

  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const cellDiv = document.createElement('div');
      const meta = cellMeta[r][c];

      if (meta === null) {
        cellDiv.className = 'cw-cell black';
        crosswordGridEl.appendChild(cellDiv);
        continue;
      }

      cellDiv.className = 'cw-cell';

      if (meta.number) {
        const numSpan = document.createElement('span');
        numSpan.className = 'cw-num';
        numSpan.textContent = meta.number;
        cellDiv.appendChild(numSpan);
      }

      const input = document.createElement('input');
      input.type = 'text';
      input.maxLength = 1;
      input.autocomplete = 'off';
      input.autocapitalize = 'characters';
      input.spellcheck = false;
      input.inputMode = 'text';
      input.dataset.r = r;
      input.dataset.c = c;
      input.id = `cell-${r}-${c}`;
      input.setAttribute('aria-label', `Row ${r + 1}, column ${c + 1}`);

      input.addEventListener('focus', () => onCellFocus(r, c));
      input.addEventListener('click', () => onCellClick(r, c));
      input.addEventListener('input', (e) => onCellInput(e, r, c));
      input.addEventListener('keydown', (e) => onCellKeydown(e, r, c));

      cellDiv.appendChild(input);
      inputEls[r][c] = input;
      crosswordGridEl.appendChild(cellDiv);
    }
  }
}

function renderClues() {
  acrossCluesEl.innerHTML = '';
  downCluesEl.innerHTML = '';

  const across = entries.filter((e) => e.dir === 'across').sort((a, b) => a.number - b.number);
  const down = entries.filter((e) => e.dir === 'down').sort((a, b) => a.number - b.number);

  const makeLi = (entry) => {
    const li = document.createElement('li');
    const btn = document.createElement('button');
    btn.dataset.number = entry.number;
    btn.dataset.dir = entry.dir;
    btn.innerHTML = `<span class="clue-num">${entry.number}.</span>${entry.clue}`;
    btn.addEventListener('click', () => setActiveEntry(entry, true));
    li.appendChild(btn);
    return li;
  };

  across.forEach((e) => acrossCluesEl.appendChild(makeLi(e)));
  down.forEach((e) => downCluesEl.appendChild(makeLi(e)));
}

// ---------------------------------------------------------------------------
// Selection / highlighting
// ---------------------------------------------------------------------------
function setActiveEntry(entry, focusFirstEmpty) {
  activeDir = entry.dir;
  let target = entry.cells[0];
  if (focusFirstEmpty) {
    const empty = entry.cells.find(({ r, c }) => !inputEls[r][c].value);
    if (empty) target = empty;
  }
  activeCell = target;
  inputEls[target.r][target.c].focus();
  updateHighlighting();
}

function onCellFocus(r, c) {
  const meta = cellMeta[r][c];
  // Keep current direction if this cell supports it, otherwise switch.
  if (activeDir === 'across' && !meta.acrossEntry) activeDir = 'down';
  if (activeDir === 'down' && !meta.downEntry) activeDir = 'across';
  activeCell = { r, c };
  updateHighlighting();
}

function onCellClick(r, c) {
  const meta = cellMeta[r][c];
  const sameCell = activeCell && activeCell.r === r && activeCell.c === c;
  if (sameCell && meta.acrossEntry && meta.downEntry) {
    activeDir = activeDir === 'across' ? 'down' : 'across';
    updateHighlighting();
  }
}

function updateHighlighting() {
  dirLabelEl.textContent = activeDir === 'across' ? 'Across' : 'Down';

  // Clear all highlight classes.
  inputEls.forEach((row) =>
    row.forEach((input) => {
      if (input) {
        input.classList.remove('in-word', 'active-cell');
      }
    })
  );
  document.querySelectorAll('.clue-list li button').forEach((b) => b.classList.remove('active'));

  if (!activeCell) return;
  const meta = cellMeta[activeCell.r][activeCell.c];
  const entry = activeDir === 'across' ? meta.acrossEntry : meta.downEntry || meta.acrossEntry;
  if (!entry) return;
  activeDir = entry.dir;

  entry.cells.forEach(({ r, c }) => inputEls[r][c].classList.add('in-word'));
  inputEls[activeCell.r][activeCell.c].classList.add('active-cell');

  const btn = document.querySelector(`.clue-list li button[data-number="${entry.number}"][data-dir="${entry.dir}"]`);
  if (btn) {
    btn.classList.add('active');
    btn.scrollIntoView({ block: 'nearest' });
  }
}

// ---------------------------------------------------------------------------
// Typing & navigation
// ---------------------------------------------------------------------------
function onCellInput(e, r, c) {
  const raw = e.target.value.toUpperCase().replace(/[^A-Z]/g, '');
  e.target.value = raw.slice(-1);
  e.target.classList.remove('correct', 'incorrect', 'revealed');

  if (e.target.value) {
    moveToNextCell(r, c);
  }
  updateScore();
  checkWin();
}

function getEntryForActiveDir(r, c) {
  const meta = cellMeta[r][c];
  return activeDir === 'across' ? meta.acrossEntry : meta.downEntry;
}

function moveToNextCell(r, c) {
  const entry = getEntryForActiveDir(r, c);
  if (!entry) return;
  const idx = entry.cells.findIndex((p) => p.r === r && p.c === c);
  if (idx >= 0 && idx < entry.cells.length - 1) {
    const next = entry.cells[idx + 1];
    activeCell = next;
    inputEls[next.r][next.c].focus();
    updateHighlighting();
  }
}

function moveToPrevCell(r, c) {
  const entry = getEntryForActiveDir(r, c);
  if (!entry) return;
  const idx = entry.cells.findIndex((p) => p.r === r && p.c === c);
  if (idx > 0) {
    const prev = entry.cells[idx - 1];
    activeCell = prev;
    inputEls[prev.r][prev.c].focus();
    updateHighlighting();
  }
}

function moveDirectional(r, c, dr, dc) {
  const rows = cellMeta.length;
  const cols = cellMeta[0].length;
  let nr = r + dr;
  let nc = c + dc;
  while (nr >= 0 && nr < rows && nc >= 0 && nc < cols) {
    if (cellMeta[nr][nc] !== null) {
      activeDir = dr !== 0 ? 'down' : 'across';
      activeCell = { r: nr, c: nc };
      inputEls[nr][nc].focus();
      updateHighlighting();
      return;
    }
    nr += dr;
    nc += dc;
  }
}

function onCellKeydown(e, r, c) {
  switch (e.key) {
    case 'ArrowRight':
      e.preventDefault();
      moveDirectional(r, c, 0, 1);
      break;
    case 'ArrowLeft':
      e.preventDefault();
      moveDirectional(r, c, 0, -1);
      break;
    case 'ArrowDown':
      e.preventDefault();
      moveDirectional(r, c, 1, 0);
      break;
    case 'ArrowUp':
      e.preventDefault();
      moveDirectional(r, c, -1, 0);
      break;
    case 'Backspace':
      if (!e.target.value) {
        e.preventDefault();
        moveToPrevCell(r, c);
        const prevEntry = getEntryForActiveDir(activeCell.r, activeCell.c);
        if (prevEntry) {
          inputEls[activeCell.r][activeCell.c].value = '';
          inputEls[activeCell.r][activeCell.c].classList.remove('correct', 'incorrect', 'revealed');
        }
      }
      break;
    case ' ':
      e.preventDefault();
      onCellClick(r, c);
      break;
    default:
      break;
  }
}

// ---------------------------------------------------------------------------
// Check / Hint / Reveal / Clear
// ---------------------------------------------------------------------------
function checkPuzzle() {
  let filled = 0;
  let correct = 0;
  let attempted = 0;

  cellMeta.forEach((row, r) =>
    row.forEach((meta, c) => {
      if (!meta) return;
      const input = inputEls[r][c];
      if (!input.value) return;
      attempted++;
      if (input.value === meta.solution) {
        input.classList.add('correct');
        input.classList.remove('incorrect');
        correct++;
      } else {
        input.classList.add('incorrect');
        input.classList.remove('correct');
      }
    })
  );

  updateClueSolvedStates();

  if (attempted === 0) {
    feedbackMsgEl.textContent = 'Type some letters first, then press Check! ✏️';
  } else if (correct === attempted) {
    feedbackMsgEl.textContent = `Nice! All ${correct} filled letters are correct. Keep going! 🌟`;
  } else {
    feedbackMsgEl.textContent = `${correct} out of ${attempted} letters are correct so far. You can do it! 💪`;
  }
  checkWin();
}

function updateClueSolvedStates() {
  entries.forEach((entry) => {
    const solved = entry.cells.every(({ r, c }) => inputEls[r][c].value === cellMeta[r][c].solution);
    const btn = document.querySelector(`.clue-list li button[data-number="${entry.number}"][data-dir="${entry.dir}"]`);
    if (btn) btn.classList.toggle('solved', solved);
  });
}

function revealLetter() {
  if (!activeCell) return;
  const { r, c } = activeCell;
  const meta = cellMeta[r][c];
  const input = inputEls[r][c];
  input.value = meta.solution;
  input.classList.remove('incorrect', 'correct');
  input.classList.add('revealed');
  updateScore();
  updateClueSolvedStates();
  moveToNextCell(r, c);
  checkWin();
}

function revealWord() {
  if (!activeCell) return;
  const entry = getEntryForActiveDir(activeCell.r, activeCell.c);
  if (!entry) return;
  entry.cells.forEach(({ r, c }) => {
    const input = inputEls[r][c];
    input.value = cellMeta[r][c].solution;
    input.classList.remove('incorrect', 'correct');
    input.classList.add('revealed');
  });
  updateScore();
  updateClueSolvedStates();
  checkWin();
}

function clearGrid() {
  if (!window.confirm('Clear all your answers and start this puzzle over?')) return;
  inputEls.forEach((row) =>
    row.forEach((input) => {
      if (input) {
        input.value = '';
        input.classList.remove('correct', 'incorrect', 'revealed', 'in-word', 'active-cell');
      }
    })
  );
  document.querySelectorAll('.clue-list li button').forEach((b) => b.classList.remove('solved', 'active'));
  feedbackMsgEl.textContent = '';
  secondsElapsed = 0;
  hasWon = false;
  updateScore();
  const firstEntry = entries.find((e) => e.dir === 'across') || entries[0];
  if (firstEntry) setActiveEntry(firstEntry, true);
  startTimer();
}

// ---------------------------------------------------------------------------
// Score / timer / win
// ---------------------------------------------------------------------------
function updateScore() {
  let total = 0;
  let correct = 0;
  cellMeta.forEach((row, r) =>
    row.forEach((meta, c) => {
      if (!meta) return;
      total++;
      if (inputEls[r][c].value === meta.solution) correct++;
    })
  );
  const pct = total ? Math.round((correct / total) * 100) : 0;
  scoreDisplayEl.textContent = `${pct}%`;
}

function startTimer() {
  stopTimer();
  updateTimerDisplay();
  timerHandle = setInterval(() => {
    secondsElapsed++;
    updateTimerDisplay();
  }, 1000);
}
function stopTimer() {
  if (timerHandle) clearInterval(timerHandle);
  timerHandle = null;
}
function updateTimerDisplay() {
  const m = Math.floor(secondsElapsed / 60);
  const s = secondsElapsed % 60;
  timerDisplayEl.textContent = `${m}:${s.toString().padStart(2, '0')}`;
}

function checkWin() {
  if (hasWon || !cellMeta) return;
  let allCorrect = true;
  for (let r = 0; r < cellMeta.length; r++) {
    for (let c = 0; c < cellMeta[r].length; c++) {
      const meta = cellMeta[r][c];
      if (!meta) continue;
      if (inputEls[r][c].value !== meta.solution) {
        allCorrect = false;
      }
    }
  }
  if (allCorrect) {
    hasWon = true;
    stopTimer();
    markCompleted(currentPuzzle.id);
    updateClueSolvedStates();
    celebrate();
  }
}

function celebrate() {
  winMsgEl.textContent = `You solved "${currentPuzzle.title}" in ${timerDisplayEl.textContent}. Amazing work! 🎉`;
  winModal.classList.remove('hidden');
}

// ---------------------------------------------------------------------------
// Wiring
// ---------------------------------------------------------------------------
document.getElementById('homeBtn').addEventListener('click', showPicker);
document.getElementById('backBtn').addEventListener('click', showPicker);
document.getElementById('checkBtn').addEventListener('click', checkPuzzle);
document.getElementById('hintBtn').addEventListener('click', revealLetter);
document.getElementById('revealWordBtn').addEventListener('click', revealWord);
document.getElementById('clearBtn').addEventListener('click', clearGrid);
document.getElementById('dirToggleBtn').addEventListener('click', () => {
  if (!activeCell) return;
  onCellClick(activeCell.r, activeCell.c);
  // Force toggle even if only one direction was available at that cell.
  const meta = cellMeta[activeCell.r][activeCell.c];
  if (meta.acrossEntry && meta.downEntry) return; // already toggled above
  activeDir = activeDir === 'across' ? 'down' : 'across';
  const entry = activeDir === 'across' ? meta.acrossEntry : meta.downEntry;
  if (entry) setActiveEntry(entry, false);
});

document.getElementById('playAgainBtn').addEventListener('click', () => {
  winModal.classList.add('hidden');
  clearGrid();
});
document.getElementById('nextPuzzleBtn').addEventListener('click', () => {
  winModal.classList.add('hidden');
  const idx = PUZZLES.findIndex((p) => p.id === currentPuzzle.id);
  const next = PUZZLES[(idx + 1) % PUZZLES.length];
  loadPuzzle(next.id);
});
winModal.addEventListener('click', (e) => {
  if (e.target === winModal) winModal.classList.add('hidden');
});

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------
showPicker();
