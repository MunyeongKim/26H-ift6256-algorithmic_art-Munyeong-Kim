const GRID_COLS = 10;
const MAX_PLAYERS = 2;
const BYTE_WIDTH = 8;
const CHUNK_COLS = 4;
const CHUNK_ROWS = 2;
const BYTES_PER_ROW = Math.max(1, Math.floor(GRID_COLS / CHUNK_COLS));
const PREVIEW_WRAP_COLS = 10;
const SIM_ROWS = 24;
const FALL_STEPS_PER_FRAME = 0.03125;
const MAX_SPAWNS_PER_FRAME = 1;
const LIVE_APPLY_DEBOUNCE_MS = 120;
const WHISPER_INFERENCE_PATH = "/inference";
const MIC_CHUNK_MS = 2000;
const MIC_MAX_QUEUE = 6;
const MIC_TARGET_SAMPLE_RATE = 16000;
const MIC_PROCESSOR_BUFFER_SIZE = 4096;
const HOLD_REPEAT_INITIAL_MS = 170;
const HOLD_REPEAT_INTERVAL_MS = 60;
const FIXED_STAGE_ASPECT = 4 / 3;
const GAME_PIXELATE_FACTOR = 2;
const PLAYER_PALETTES = [
  {
    block: [72, 104, 176],
    ghost: [72, 104, 176, 90],
    border: [20, 36, 72]
  },
  {
    block: [176, 88, 88],
    ghost: [176, 88, 88, 90],
    border: [74, 20, 20]
  }
];
const PREVIEW_PLAYER_PALETTES = [
  {
    active: [38, 106, 244],
    activeStroke: [24, 66, 154],
    settled: [142, 156, 178],
    settledStroke: [94, 108, 130],
    queued: [192, 206, 228],
    queuedStroke: [140, 156, 181]
  },
  {
    active: [232, 68, 76],
    activeStroke: [148, 39, 47],
    settled: [182, 144, 148],
    settledStroke: [133, 98, 102],
    queued: [226, 196, 200],
    queuedStroke: [181, 149, 153]
  }
];
const PREVIEW_NEUTRAL = {
  empty: [236, 236, 236],
  unset: [190, 190, 190],
  done: [116, 116, 116],
  baseBit: [180, 180, 180],
  candidateBit: [154, 154, 154],
  selectedBit: [128, 128, 128],
  mixed: [136, 136, 136],
  mixedStroke: [95, 95, 95],
  laneFill: [246, 246, 246],
  laneStroke: [220, 220, 220]
};
const OWNER_NONE = -1;
const OWNER_MIXED = -2;
const BIT_ROLE_BASE = 0;
const BIT_ROLE_CANDIDATE = 1;
const BIT_ROLE_SELECTED = 2;
const PREVIEW_BLOCK_SCALE = 4;
const PIXEL_FONT_NAME = "Press Start 2P";
const PIXEL_TEXT_STRETCH_Y = 1.18;
const CHUNK_NEIGHBORS = [
  [-1, 0],
  [1, 0],
  [0, -1],
  [0, 1]
];

const BIT_BYTES = `
11101100
10011011
 10010000 11101101 10010101 10011000 11101011 10101001 10110100 00101100 00100000 11101011
10101100 10001000 11101010 10110000 10000000 00100000 11101100 10011110 10001010 11101100 10100011 10111100
00100000 11101100 10010011 10111000 11101011 10001010 10010100 00100000 11101101 10011001 10011000 11101010
10110010 10111101 00101000 11101100 10011000 10001000 00111010 00100000 01001010 01010011 00101111 11101101
10001100 10001100 11101100 10011101 10110100 11101100 10001101 10101100 00101111 11101101 10000100 10110000
11101101 10101111 10101101 00101001 00100000 11101010 10111000 10110000 11101100 10100100 10000000 11101100
10011100 10111100 11101011 10100001 10011100 00100000 00101010 00101010 11100010 10000000 10011100 11101100
10011101 10110100 00100000 11101010 10111000 10000000 11101100 10011000 10000000 00100000 11101010 10111000
10101100 10011100 00100000 11101100 10001011 10100100 11101100 10100000 10011100 00100000 11101011 10101100
10110100 11101100 10011101 10110100 11101101 10001010 10111000 11101100 10100101 10111100 00100000 11101011
10100000 10010100 11101011 10100001 10011100 00100000 11101100 10110110 10001100 11101100 10100000 10000101
11101101 10010101 10101000 00100000 11101011 10110011 10110100 11101011 10001010 10010100 00100000 11101101
10010111 10101000 11101101 10011010 10010100 11101011 10100010 10010100 00100000 11101011 10110000 10101001
11101101 10011001 10011001 00100000 11101100 10011000 10001000 11101100 10001011 10000011 11101011 10100001
10011100 00100000 11101011 10110011 10110100 11101100 10010111 10101100 11101100 10100100 10000100 11101010
10110010 10111000 00101110
`;

const LOREM_IPSUM_TEXT = "";

let sim = null;
let defaultByteGroups = [];
let activeByteGroups = [];
let activeByteMeta = [];
let activeSourceText = "";
let sourceLabel = "default bit stream";
let sourceTextChars = 0;
let ui = null;
let paused = true;
let playerMode = 2;
let sharedPieceTemplates = [];
let sharedTemplateIndex = 0;
let runtimeTogglePromise = null;
let hasStartedAtLeastOnce = false;
let stageCanvasEl = null;
let stageViewport = { x: 0, y: 0, w: 1, h: 1 };
let stageDesignSize = { w: 1, h: 1 };
let gamePixelBuffer = null;
let previewBitRoleCache = { byteGroups: null, pieceTemplates: null, value: null };
const holdRepeatState = {
  p1Left: { held: false, nextAt: 0 },
  p1Right: { held: false, nextAt: 0 },
  p1SoftDrop: { held: false, nextAt: 0 },
  p2Left: { held: false, nextAt: 0 },
  p2Right: { held: false, nextAt: 0 },
  p2SoftDrop: { held: false, nextAt: 0 }
};

function computeStageViewport(winW, winH) {
  const safeW = Math.max(1, Math.floor(winW));
  const safeH = Math.max(1, Math.floor(winH));

  let stageW = safeW;
  let stageH = Math.floor(stageW / FIXED_STAGE_ASPECT);
  if (stageH > safeH) {
    stageH = safeH;
    stageW = Math.floor(stageH * FIXED_STAGE_ASPECT);
  }

  const x = Math.floor((safeW - stageW) * 0.5);
  const y = Math.floor((safeH - stageH) * 0.5);
  return { x, y, w: stageW, h: stageH };
}

function updateControlDockPosition() {
  const dock = document.getElementById("controlDock");
  if (!dock) return;
}

function applyStageViewport() {
  stageViewport = computeStageViewport(windowWidth, windowHeight);

  if (stageCanvasEl) {
    stageCanvasEl.style("position", "fixed");
    stageCanvasEl.style("left", `${stageViewport.x}px`);
    stageCanvasEl.style("top", `${stageViewport.y}px`);
    stageCanvasEl.style("width", `${stageViewport.w}px`);
    stageCanvasEl.style("height", `${stageViewport.h}px`);
    stageCanvasEl.style("z-index", "1");
  }

  updateControlDockPosition();
}

function setup() {
  stageViewport = computeStageViewport(windowWidth, windowHeight);
  stageDesignSize = { w: stageViewport.w, h: stageViewport.h };
  stageCanvasEl = createCanvas(stageDesignSize.w, stageDesignSize.h);
  applyStageViewport();
  textFont("Georgia");
  defaultByteGroups = parseByteGroups(BIT_BYTES);
  setupConverterUI();
  applyTextSource(LOREM_IPSUM_TEXT, true);
  setPaused(true);
}

function draw() {
  drawSky();
  updateSimulationFrame();
  drawSimulationBoard();
  drawHud();
}

function windowResized() {
  applyStageViewport();

  if (!sim) return;
  const nextCols = getPreviewPanelConfig().cols;
  if (sim.wrapCols !== nextCols) {
    initializeSimulation();
  }
}

function keyPressed(event) {
  const p1 = 0;
  const p2 = 1;
  const isRepeat = event && event.repeat === true;

  if (key === "r" || key === "R") {
    if (sim && sim.stalled) {
      clearTranscriptSource(false);
    }
    initializeSimulation();
    // Keep current run/stop state on reset.
    updatePauseButtons();
    return false;
  }

  const isEnterToggle = keyCode === ENTER || keyCode === RETURN;
  const isSpaceToggle = key === " " || (event && event.code === "Space");
  if (isEnterToggle || isSpaceToggle) {
    if (isRepeat) return false;
    toggleRuntimeActive();
    return false;
  }

  if (key === "1") {
    if (isRepeat) return false;
    setPlayerMode(1);
    return false;
  }

  if (key === "2") {
    if (isRepeat) return false;
    setPlayerMode(2);
    return false;
  }

  // Player 1 controls: A/D move, Q/E turn, S soft-drop, F hard-drop.
  if (key === "a" || key === "A") {
    if (isRepeat) return false;
    handlePlayerControl(p1, () => moveActivePieceHorizontalForOwner(p1, -1));
    return false;
  }
  if (key === "d" || key === "D") {
    if (isRepeat) return false;
    handlePlayerControl(p1, () => moveActivePieceHorizontalForOwner(p1, 1));
    return false;
  }
  if (key === "q" || key === "Q") {
    handlePlayerControl(p1, () => attemptRotateActivePieceForOwner(p1, false));
    return false;
  }
  if (key === "e" || key === "E") {
    handlePlayerControl(p1, () => attemptRotateActivePieceForOwner(p1, true));
    return false;
  }
  if (key === "s" || key === "S") {
    if (isRepeat) return false;
    handlePlayerControl(p1, () => softDropActivePieceForOwner(p1));
    return false;
  }
  if (key === "f" || key === "F") {
    if (isRepeat) return false;
    handlePlayerControl(p1, () => hardDropActivePieceForOwner(p1));
    return false;
  }

  if (playerMode === 2) {
    // Player 2 controls: J/L move, U/O turn, K soft-drop, ; hard-drop.
    if (key === "j" || key === "J") {
      if (isRepeat) return false;
      handlePlayerControl(p2, () => moveActivePieceHorizontalForOwner(p2, -1));
      return false;
    }

    if (key === "l" || key === "L") {
      if (isRepeat) return false;
      handlePlayerControl(p2, () => moveActivePieceHorizontalForOwner(p2, 1));
      return false;
    }

    if (key === "u" || key === "U") {
      handlePlayerControl(p2, () => attemptRotateActivePieceForOwner(p2, false));
      return false;
    }

    if (key === "o" || key === "O") {
      handlePlayerControl(p2, () => attemptRotateActivePieceForOwner(p2, true));
      return false;
    }

    if (key === "k" || key === "K") {
      if (isRepeat) return false;
      handlePlayerControl(p2, () => softDropActivePieceForOwner(p2));
      return false;
    }

    if (key === ";" || key === ":") {
      if (isRepeat) return false;
      handlePlayerControl(p2, () => hardDropActivePieceForOwner(p2));
      return false;
    }
  }
}

function getPreviewPanelConfig() {
  const panelW = min(width - 20, max(320, floor(width * 0.46)));
  const tileStrideY = max(16, floor(panelW * 0.05));
  const footerH = max(42, floor(panelW * 0.12));
  const previewLaneW = max(44, floor(panelW * 0.12));
  const cols = PREVIEW_WRAP_COLS;

  return {
    panelW,
    tileStrideY,
    footerH,
    previewLaneW,
    cols
  };
}

function createSimulation(wrapCols) {
  const byteGroups = activeByteGroups.slice();
  const cells = Array.from({ length: SIM_ROWS }, () => Array(GRID_COLS).fill(null));
  const playerCount = getPlayerCount();

  return {
    playerCount,
    frame: 0,
    cells,
    sourceRows: ceil(byteGroups.length / BYTES_PER_ROW) * CHUNK_ROWS,
    sourceBytes: byteGroups.length,
    sourceChars: sourceTextChars,
    sourceLabel,
    byteGroups: byteGroups.slice(),
    byteMeta: activeByteMeta.slice(),
    sourceText: activeSourceText,
    totalBlackBits: 0,
    pieces: [],
    waiting: [],
    spawnedPieces: 0,
    occupiedCells: 0,
    settledPieces: 0,
    linesCleared: 0,
    clearEvents: 0,
    stalled: false,
    fallProgress: 0,
    nextQueueOwner: 0,
    wrapCols,
    playerStats: Array.from({ length: playerCount }, () => ({
      spawned: 0,
      settled: 0
    }))
  };
}

function getPlayerCount() {
  return playerMode === 1 ? 1 : MAX_PLAYERS;
}

function getPlayerPalette(playerIndex) {
  return PLAYER_PALETTES[playerIndex % PLAYER_PALETTES.length];
}

function drawPixelText(textValue, x, y, size, alignX, alignY) {
  push();
  textFont(PIXEL_FONT_NAME);
  textSize(size);
  textAlign(alignX, alignY);
  translate(x, y);
  scale(1, PIXEL_TEXT_STRETCH_Y);
  text(textValue, 0, 0);
  pop();
}

function getPreviewPalette(playerIndex) {
  const idx = ((playerIndex % PREVIEW_PLAYER_PALETTES.length) + PREVIEW_PLAYER_PALETTES.length) % PREVIEW_PLAYER_PALETTES.length;
  return PREVIEW_PLAYER_PALETTES[idx];
}

function createPieceFromTemplate(template, pieceId, owner) {
  return {
    id: pieceId,
    owner,
    byteIndex: template.byteIndex,
    byteBits: template.byteBits,
    byteMinRow: template.byteMinRow,
    byteMinCol: template.byteMinCol,
    sourceRow: template.sourceRow,
    sourceCol: template.sourceCol,
    offsets: template.offsets.map((offset) => ({ row: offset.row, col: offset.col })),
    row: 0,
    col: template.sourceCol,
    active: false,
    settled: false
  };
}

function hasActivePieceForOwner(owner) {
  if (!sim) return false;
  for (let i = 0; i < sim.pieces.length; i += 1) {
    const piece = sim.pieces[i];
    if (piece.active && piece.owner === owner) return true;
  }
  return false;
}

function getActivePieceForOwner(owner) {
  if (!sim) return null;
  for (let i = 0; i < sim.pieces.length; i += 1) {
    const piece = sim.pieces[i];
    if (piece.active && piece.owner === owner) return piece;
  }
  return null;
}

function hasWaitingPieceForOwner(owner) {
  if (!sim) return false;
  for (let i = 0; i < sim.waiting.length; i += 1) {
    const pieceId = sim.waiting[i];
    const piece = sim.pieces[pieceId];
    if (piece && piece.owner === owner) return true;
  }
  return false;
}

function assignNextSharedPieceToOwner(owner) {
  if (!sim) return false;
  if (sharedTemplateIndex >= sharedPieceTemplates.length) return false;

  const template = sharedPieceTemplates[sharedTemplateIndex];
  sharedTemplateIndex += 1;

  const piece = createPieceFromTemplate(template, sim.pieces.length, owner);
  sim.pieces.push(piece);
  sim.waiting.push(piece.id);
  sim.totalBlackBits += piece.offsets.length;
  return true;
}

function ensureOwnerHasQueuedPiece(owner) {
  if (!sim || sim.stalled) return false;
  if (hasActivePieceForOwner(owner)) return false;
  if (hasWaitingPieceForOwner(owner)) return false;
  return assignNextSharedPieceToOwner(owner);
}

function ensureAllOwnersHaveQueuedPieces() {
  if (!sim) return;
  const playerCount = sim.playerCount;
  if (!Number.isInteger(playerCount) || playerCount <= 0) return;

  const startOwner = Number.isInteger(sim.nextQueueOwner)
    ? ((sim.nextQueueOwner % playerCount) + playerCount) % playerCount
    : 0;
  let assignedCount = 0;

  for (let offset = 0; offset < playerCount; offset += 1) {
    const owner = (startOwner + offset) % playerCount;
    if (ensureOwnerHasQueuedPiece(owner)) assignedCount += 1;
  }

  if (assignedCount > 0) {
    sim.nextQueueOwner = (startOwner + assignedCount) % playerCount;
  }
}

function initializeSimulation() {
  const byteGroups = activeByteGroups.slice();
  const wrapCols = getPreviewPanelConfig().cols;
  sharedPieceTemplates = buildPieceTemplatesFromByteGroups(byteGroups, activeByteMeta, wrapCols);
  sharedTemplateIndex = 0;

  sim = createSimulation(wrapCols);

  let initialAssignedCount = 0;
  for (let owner = 0; owner < sim.playerCount; owner += 1) {
    if (assignNextSharedPieceToOwner(owner)) initialAssignedCount += 1;
  }
  if (sim.playerCount > 0) {
    sim.nextQueueOwner = initialAssignedCount % sim.playerCount;
  }
  spawnWaitingPieces();
  sim.occupiedCells = countOccupiedCells();
  sim.settledPieces = countSettledPieces();
}

function setPaused(nextPaused) {
  paused = nextPaused;
  if (paused) {
    resetHoldRepeatState();
  }
  updatePauseButtons();
}

function isMicCurrentlyRunning() {
  return Boolean(ui && typeof ui.isMicRunning === "function" && ui.isMicRunning());
}

async function setRuntimeActive(shouldRun) {
  if (shouldRun) {
    if (ui && typeof ui.startMicCapture === "function") {
      const micStarted = await ui.startMicCapture();
      if (!micStarted) {
        setPaused(true);
        return false;
      }
    }
    hasStartedAtLeastOnce = true;
    setPaused(false);
    return true;
  }

  setPaused(true);
  if (ui && typeof ui.stopMicCapture === "function" && isMicCurrentlyRunning()) {
    await ui.stopMicCapture("Mic: stopped", true);
  }
  return true;
}

function requestRuntimeActive(shouldRun) {
  if (runtimeTogglePromise) return runtimeTogglePromise;
  runtimeTogglePromise = setRuntimeActive(shouldRun).finally(() => {
    runtimeTogglePromise = null;
  });
  return runtimeTogglePromise;
}

function toggleRuntimeActive() {
  const shouldRun = paused || !isMicCurrentlyRunning();
  return requestRuntimeActive(shouldRun);
}

function setPlayerMode(mode) {
  const nextMode = mode === 1 ? 1 : 2;
  if (playerMode === nextMode) return;
  const wasPaused = paused;
  playerMode = nextMode;
  updateModeButtons();
  initializeSimulation();
  setPaused(wasPaused);
}

function updatePauseButtons() {
  if (!ui) return;
  if (ui.startBtn) ui.startBtn.disabled = !paused;
  if (ui.pauseBtn) ui.pauseBtn.disabled = paused;
}

function updateModeButtons() {
  if (!ui) return;
  if (ui.mode1Btn) ui.mode1Btn.disabled = playerMode === 1;
  if (ui.mode2Btn) ui.mode2Btn.disabled = playerMode === 2;
}

function handlePlayerControl(playerIndex, action) {
  if (paused) return false;
  if (!sim || playerIndex < 0 || playerIndex >= sim.playerCount) return false;
  return action();
}

function resetHoldRepeatState() {
  const states = Object.values(holdRepeatState);
  for (let i = 0; i < states.length; i += 1) {
    states[i].held = false;
    states[i].nextAt = 0;
  }
}

function stepHoldRepeat(state, isDown, action, nowMs) {
  if (!isDown) {
    state.held = false;
    state.nextAt = 0;
    return;
  }

  if (!state.held) {
    state.held = true;
    state.nextAt = nowMs + HOLD_REPEAT_INITIAL_MS;
    return;
  }

  if (nowMs < state.nextAt) return;
  action();
  state.nextAt = nowMs + HOLD_REPEAT_INTERVAL_MS;
}

function processHeldControls() {
  if (!sim || paused) {
    resetHoldRepeatState();
    return;
  }

  const nowMs = millis();
  const p1 = 0;
  const p2 = 1;

  stepHoldRepeat(
    holdRepeatState.p1Left,
    keyIsDown(65),
    () => handlePlayerControl(p1, () => moveActivePieceHorizontalForOwner(p1, -1)),
    nowMs
  );
  stepHoldRepeat(
    holdRepeatState.p1Right,
    keyIsDown(68),
    () => handlePlayerControl(p1, () => moveActivePieceHorizontalForOwner(p1, 1)),
    nowMs
  );
  stepHoldRepeat(
    holdRepeatState.p1SoftDrop,
    keyIsDown(83),
    () => handlePlayerControl(p1, () => softDropActivePieceForOwner(p1)),
    nowMs
  );

  if (playerMode === 2 && sim.playerCount > 1) {
    stepHoldRepeat(
      holdRepeatState.p2Left,
      keyIsDown(74),
      () => handlePlayerControl(p2, () => moveActivePieceHorizontalForOwner(p2, -1)),
      nowMs
    );
    stepHoldRepeat(
      holdRepeatState.p2Right,
      keyIsDown(76),
      () => handlePlayerControl(p2, () => moveActivePieceHorizontalForOwner(p2, 1)),
      nowMs
    );
    stepHoldRepeat(
      holdRepeatState.p2SoftDrop,
      keyIsDown(75),
      () => handlePlayerControl(p2, () => softDropActivePieceForOwner(p2)),
      nowMs
    );
    return;
  }

  holdRepeatState.p2Left.held = false;
  holdRepeatState.p2Left.nextAt = 0;
  holdRepeatState.p2Right.held = false;
  holdRepeatState.p2Right.nextAt = 0;
  holdRepeatState.p2SoftDrop.held = false;
  holdRepeatState.p2SoftDrop.nextAt = 0;
}

function updateSimulationFrame() {
  processHeldControls();
  if (paused || !sim) return;
  updateSimulation();
}

function getBoardLayout() {
  const topInset = max(96, floor(height * 0.14));
  const bottomInset = max(8, floor(height * 0.015));
  const usableHeight = max(SIM_ROWS, height - topInset - bottomInset);
  const cellByHeight = floor(usableHeight / SIM_ROWS);
  const panelW = getPreviewPanelConfig().panelW;
  const sideGap = 20;
  const leftRegionW = max(120, width - panelW - sideGap * 2);
  const cellByWidth = floor(leftRegionW / GRID_COLS);
  const cell = max(2, min(cellByWidth, cellByHeight));
  const boardW = GRID_COLS * cell;
  const boardH = SIM_ROWS * cell;
  const x0 = sideGap + floor((leftRegionW - boardW) * 0.5);
  const y0 = max(0, height - bottomInset - boardH);
  return { cell, boardW, boardH, x0, y0 };
}

function getGameRenderBounds(layout) {
  const cell = layout.cell;
  const railW = max(3, floor(cell * 0.22));
  const gutterW = max(4, floor(cell * 0.34));
  const shellPad = max(4, floor(cell * 0.38));

  const rawX = floor(layout.x0 - railW - gutterW - shellPad);
  const rawY = floor(layout.y0 - shellPad);
  const rawW = ceil(layout.boardW + (railW + gutterW + shellPad) * 2);
  const rawH = ceil(layout.boardH + shellPad * 2);

  const x = max(0, rawX);
  const y = max(0, rawY);
  const w = max(1, min(width - x, rawW - max(0, x - rawX)));
  const h = max(1, min(height - y, rawH - max(0, y - rawY)));
  return { x, y, w, h };
}

function applyGamePixelation(layout) {
  if (GAME_PIXELATE_FACTOR <= 1) return;

  const bounds = getGameRenderBounds(layout);
  if (bounds.w <= 1 || bounds.h <= 1) return;

  const smallW = max(1, floor(bounds.w / GAME_PIXELATE_FACTOR));
  const smallH = max(1, floor(bounds.h / GAME_PIXELATE_FACTOR));
  if (!gamePixelBuffer || gamePixelBuffer.width !== smallW || gamePixelBuffer.height !== smallH) {
    gamePixelBuffer = createGraphics(smallW, smallH);
    gamePixelBuffer.pixelDensity(1);
    gamePixelBuffer.noSmooth();
  }

  const snap = get(bounds.x, bounds.y, bounds.w, bounds.h);
  gamePixelBuffer.clear();
  const prevBufferSmooth = gamePixelBuffer.drawingContext.imageSmoothingEnabled;
  gamePixelBuffer.drawingContext.imageSmoothingEnabled = false;
  gamePixelBuffer.image(snap, 0, 0, smallW, smallH);
  gamePixelBuffer.drawingContext.imageSmoothingEnabled = prevBufferSmooth;

  const prevMainSmooth = drawingContext.imageSmoothingEnabled;
  drawingContext.imageSmoothingEnabled = false;
  image(gamePixelBuffer, bounds.x, bounds.y, bounds.w, bounds.h);
  drawingContext.imageSmoothingEnabled = prevMainSmooth;
}

function drawSimulationBoard() {
  if (!sim) return;
  const layout = getBoardLayout();
  drawSimulation(layout.x0, layout.y0, layout.cell);
  applyGamePixelation(layout);
}

function parseByteGroups(byteText) {
  return byteText.trim().split(/\s+/);
}

function utf8TextToByteData(text) {
  const encoder = new TextEncoder();
  const groups = [];
  const meta = [];
  const chars = Array.from(text);
  let lineIndex = 0;

  for (let charIndex = 0; charIndex < chars.length; charIndex += 1) {
    const ch = chars[charIndex];
    const bytes = Array.from(encoder.encode(ch));

    for (let part = 0; part < bytes.length; part += 1) {
      const value = bytes[part];
      groups.push(value.toString(2).padStart(8, "0"));
      meta.push({
        char: ch,
        charIndex,
        lineIndex,
        part: part + 1,
        total: bytes.length
      });
    }

    if (ch === "\n") {
      lineIndex += 1;
    }
  }

  return { groups, meta };
}

function isTypingInFormElement() {
  const el = document.activeElement;
  if (!el) return false;
  const tag = el.tagName ? el.tagName.toLowerCase() : "";
  return tag === "input" || tag === "textarea";
}

function formatCharLabel(ch) {
  if (ch === " ") return "[space]";
  if (ch === "\n") return "[\\n]";
  if (ch === "\t") return "[\\t]";
  return ch;
}

function getNextPiecePreview() {
  let piece = null;
  if (sim.waiting.length > 0) {
    piece = sim.pieces[sim.waiting[0]];
  } else if (sharedTemplateIndex < sharedPieceTemplates.length) {
    piece = sharedPieceTemplates[sharedTemplateIndex];
  }
  if (piece === null || piece === undefined) return null;

  const byteBits = piece.byteBits;
  const byteHex = parseInt(byteBits, 2).toString(16).toUpperCase().padStart(2, "0");
  const charInfo = sim.byteMeta[piece.byteIndex] || null;
  const bitGrid = Array.from({ length: CHUNK_ROWS }, () => Array(CHUNK_COLS).fill(0));
  const activeMask = Array.from({ length: CHUNK_ROWS }, () => Array(CHUNK_COLS).fill(0));
  for (let row = 0; row < CHUNK_ROWS; row += 1) {
    for (let col = 0; col < CHUNK_COLS; col += 1) {
      const idx = row * CHUNK_COLS + col;
      bitGrid[row][col] = byteBits[idx] === "1" ? 1 : 0;
    }
  }
  for (let i = 0; i < piece.offsets.length; i += 1) {
    const rr = piece.byteMinRow + piece.offsets[i].row;
    const cc = piece.byteMinCol + piece.offsets[i].col;
    if (rr >= 0 && rr < CHUNK_ROWS && cc >= 0 && cc < CHUNK_COLS) {
      activeMask[rr][cc] = 1;
    }
  }

  return {
    byteIndex: piece.byteIndex,
    byteBits,
    byteHex,
    bitGrid,
    activeMask,
    charInfo
  };
}

function getByteCompletionMap() {
  const byteCount = sim.byteGroups ? sim.byteGroups.length : 0;
  const total = Array(byteCount).fill(0);
  const settled = Array(byteCount).fill(0);

  for (let i = 0; i < sim.pieces.length; i += 1) {
    const p = sim.pieces[i];
    if (p.byteIndex < 0 || p.byteIndex >= byteCount) continue;
    total[p.byteIndex] += 1;
    if (p.settled) settled[p.byteIndex] += 1;
  }

  const done = Array(byteCount).fill(false);
  for (let i = 0; i < byteCount; i += 1) {
    done[i] = total[i] > 0 && settled[i] >= total[i];
  }

  return { total, settled, done };
}

function createOwnerGrid() {
  return Array.from({ length: CHUNK_ROWS }, () => Array(CHUNK_COLS).fill(OWNER_NONE));
}

function paintOwnerGridCell(grid, rr, cc, owner) {
  if (!grid) return;
  if (rr < 0 || rr >= CHUNK_ROWS || cc < 0 || cc >= CHUNK_COLS) return;

  const prev = grid[rr][cc];
  if (prev === OWNER_NONE || prev === owner) {
    grid[rr][cc] = owner;
    return;
  }
  grid[rr][cc] = OWNER_MIXED;
}

function getByteCellOwnerMaps() {
  const activeByByte = new Map();
  const settledByByte = new Map();

  for (let i = 0; i < sim.pieces.length; i += 1) {
    const piece = sim.pieces[i];
    if (!piece) continue;
    if (!piece.active && !piece.settled) continue;

    const byteIndex = piece.byteIndex;
    if (!Number.isInteger(byteIndex) || byteIndex < 0) continue;
    const map = piece.active ? activeByByte : settledByByte;
    if (!map.has(byteIndex)) map.set(byteIndex, createOwnerGrid());
    const grid = map.get(byteIndex);

    for (let k = 0; k < piece.offsets.length; k += 1) {
      const rr = piece.byteMinRow + piece.offsets[k].row;
      const cc = piece.byteMinCol + piece.offsets[k].col;
      paintOwnerGridCell(grid, rr, cc, piece.owner);
    }
  }

  return { activeByByte, settledByByte };
}

function createBitRoleGrid() {
  return Array.from({ length: CHUNK_ROWS }, () => Array(CHUNK_COLS).fill(0));
}

function markBitRoleGridCell(grid, rr, cc) {
  if (!grid) return;
  if (rr < 0 || rr >= CHUNK_ROWS || cc < 0 || cc >= CHUNK_COLS) return;
  grid[rr][cc] = 1;
}

function buildByteBitRoleMaps(byteGroups, pieceTemplates) {
  const candidateByByte = new Map();
  const selectedByByte = new Map();

  if (Array.isArray(byteGroups)) {
    for (let byteIndex = 0; byteIndex < byteGroups.length; byteIndex += 1) {
      const byte = byteGroups[byteIndex];
      if (typeof byte !== "string" || byte.length < BYTE_WIDTH) continue;

      const chunkGrid = byteToChunkGrid(byte);
      const components = extractChunkComponents(chunkGrid);
      for (let compIdx = 0; compIdx < components.length; compIdx += 1) {
        const component = components[compIdx];
        if (!Array.isArray(component) || component.length !== 4) continue;

        if (!candidateByByte.has(byteIndex)) {
          candidateByByte.set(byteIndex, createBitRoleGrid());
        }
        const candidateGrid = candidateByByte.get(byteIndex);
        for (let k = 0; k < component.length; k += 1) {
          markBitRoleGridCell(candidateGrid, component[k].row, component[k].col);
        }
      }
    }
  }

  if (Array.isArray(pieceTemplates)) {
    for (let i = 0; i < pieceTemplates.length; i += 1) {
      const template = pieceTemplates[i];
      if (!template || !Number.isInteger(template.byteIndex) || template.byteIndex < 0) continue;
      if (!Array.isArray(template.offsets) || template.offsets.length === 0) continue;

      if (!selectedByByte.has(template.byteIndex)) {
        selectedByByte.set(template.byteIndex, createBitRoleGrid());
      }
      const selectedGrid = selectedByByte.get(template.byteIndex);
      for (let k = 0; k < template.offsets.length; k += 1) {
        const rr = (template.byteMinRow || 0) + template.offsets[k].row;
        const cc = (template.byteMinCol || 0) + template.offsets[k].col;
        markBitRoleGridCell(selectedGrid, rr, cc);
      }
    }
  }

  return { candidateByByte, selectedByByte };
}

function getByteBitRoleMaps(byteGroups, pieceTemplates) {
  if (
    previewBitRoleCache.byteGroups === byteGroups &&
    previewBitRoleCache.pieceTemplates === pieceTemplates &&
    previewBitRoleCache.value
  ) {
    return previewBitRoleCache.value;
  }

  const value = buildByteBitRoleMaps(byteGroups, pieceTemplates);
  previewBitRoleCache = {
    byteGroups,
    pieceTemplates,
    value
  };
  return value;
}

function resolvePreviewBitFill(activeOwner, settledOwner, queuedOwner, isDone, bitRole) {
  if (activeOwner === OWNER_MIXED) return PREVIEW_NEUTRAL.mixed;
  if (Number.isInteger(activeOwner) && activeOwner >= 0) {
    return getPreviewPalette(activeOwner).active;
  }

  if (settledOwner === OWNER_MIXED) return PREVIEW_NEUTRAL.mixed;
  if (Number.isInteger(settledOwner) && settledOwner >= 0) {
    return getPreviewPalette(settledOwner).settled;
  }

  if (Number.isInteger(queuedOwner) && queuedOwner >= 0) {
    return getPreviewPalette(queuedOwner).queued;
  }

  if (isDone) return PREVIEW_NEUTRAL.done;
  if (bitRole === BIT_ROLE_SELECTED) return PREVIEW_NEUTRAL.selectedBit;
  if (bitRole === BIT_ROLE_CANDIDATE) return PREVIEW_NEUTRAL.candidateBit;
  return PREVIEW_NEUTRAL.baseBit;
}

function resolvePreviewPieceStyle(piece) {
  if (!piece) {
    return {
      hasBlock: false,
      fill: PREVIEW_NEUTRAL.empty,
      stroke: PREVIEW_NEUTRAL.laneStroke
    };
  }

  const owner = Number.isInteger(piece.owner) ? piece.owner : 0;
  const palette = getPreviewPalette(owner);
  if (piece.active) {
    return {
      hasBlock: true,
      fill: palette.active,
      stroke: palette.activeStroke
    };
  }

  if (piece.settled) {
    return {
      hasBlock: true,
      fill: palette.settled,
      stroke: palette.settledStroke
    };
  }

  return {
    hasBlock: true,
    fill: palette.queued,
    stroke: palette.queuedStroke
  };
}

function computePreviewRowProgress(rows, previewLineIds) {
  if (rows <= 0) {
    return {
      currentRow: 0,
      settledRow: -1,
      activeRow: -1,
      ownerFocusRows: [],
      lagRows: 0
    };
  }

  const playerCount = sim && Number.isInteger(sim.playerCount) ? sim.playerCount : 0;
  let settledRow = -1;
  let activeRow = -1;
  let activeBottom = -Infinity;
  const settledRowsByOwner = Array(playerCount).fill(-1);
  const activeRowsByOwner = Array(playerCount).fill(-1);
  const activeBottomByOwner = Array(playerCount).fill(-Infinity);

  for (let i = 0; i < sim.pieces.length; i += 1) {
    const piece = sim.pieces[i];
    if (!piece) continue;
    if (!piece.active && !piece.settled) continue;

    const byteIndex = piece.byteIndex;
    if (!Number.isInteger(byteIndex) || byteIndex < 0 || byteIndex >= previewLineIds.length) continue;
    const lineId = previewLineIds[byteIndex];
    if (!Number.isInteger(lineId)) continue;

    if (piece.settled) settledRow = max(settledRow, lineId);
    const owner = Number.isInteger(piece.owner) ? piece.owner : -1;
    if (piece.settled && owner >= 0 && owner < playerCount) {
      settledRowsByOwner[owner] = max(settledRowsByOwner[owner], lineId);
    }

    if (piece.active) {
      const bottom = pieceBottom(piece);
      if (bottom > activeBottom || (bottom === activeBottom && lineId > activeRow)) {
        activeBottom = bottom;
        activeRow = lineId;
      }

      if (
        owner >= 0 &&
        owner < playerCount &&
        (bottom > activeBottomByOwner[owner] ||
          (bottom === activeBottomByOwner[owner] && lineId > activeRowsByOwner[owner]))
      ) {
        activeBottomByOwner[owner] = bottom;
        activeRowsByOwner[owner] = lineId;
      }
    }
  }

  // Prefer the lowest active piece on screen; keep settled frontier as a fallback so lock events don't stall.
  let currentRow = max(activeRow, settledRow);
  if (!Number.isInteger(currentRow) || currentRow < 0) currentRow = 0;
  const clampedRow = max(0, min(rows - 1, currentRow));
  const lagRows = max(0, rows - (clampedRow + 1));
  const ownerFocusRows = [];
  for (let owner = 0; owner < playerCount; owner += 1) {
    const activeOwnerRow = activeRowsByOwner[owner];
    const settledOwnerRow = settledRowsByOwner[owner];
    ownerFocusRows.push(activeOwnerRow >= 0 ? activeOwnerRow : settledOwnerRow);
  }

  return {
    currentRow: clampedRow,
    settledRow,
    activeRow,
    ownerFocusRows,
    lagRows
  };
}

function setupConverterUI() {
  const converterEl = document.getElementById("converter");
  const sourceTextEl = document.getElementById("sourceText");
  const applyBtn = document.getElementById("applyText");
  const useDefaultBtn = document.getElementById("useDefault");
  const toggleMicBtn = document.getElementById("toggleMic");
  const micInfoEl = document.getElementById("micInfo");
  const pauseBtn = document.getElementById("pauseSim");
  const infoEl = document.getElementById("convertInfo");

  if (
    !converterEl ||
    !sourceTextEl ||
    !toggleMicBtn ||
    !micInfoEl ||
    !pauseBtn ||
    !infoEl
  ) {
    return;
  }

  ui = {
    converterEl,
    sourceTextEl,
    applyBtn,
    useDefaultBtn,
    toggleMicBtn,
    micInfoEl,
    pauseBtn,
    infoEl
  };

  sourceTextEl.value = LOREM_IPSUM_TEXT;
  sourceTextEl.readOnly = true;
  sourceTextEl.spellcheck = false;
  sourceTextEl.placeholder = "Whisper transcript stream (keyboard input disabled)";
  updatePauseButtons();
  updateModeButtons();

  let liveApplyTimer = null;

  const moveCaretToEnd = () => {
    const end = sourceTextEl.value.length;
    sourceTextEl.setSelectionRange(end, end);
  };

  const clearLiveApplyTimer = () => {
    if (liveApplyTimer === null) return;
    clearTimeout(liveApplyTimer);
    liveApplyTimer = null;
  };

  const queueLiveApply = (delayMs) => {
    clearLiveApplyTimer();
    liveApplyTimer = window.setTimeout(() => {
      liveApplyTimer = null;
      applyTextSourceStreaming(sourceTextEl.value, false);
    }, Math.max(0, delayMs));
  };

  sourceTextEl.addEventListener("click", moveCaretToEnd);
  sourceTextEl.addEventListener("focus", () => {
    window.requestAnimationFrame(moveCaretToEnd);
  });

  if (applyBtn) {
    applyBtn.style.display = "none";
    applyBtn.disabled = true;
  }

  let micStream = null;
  let micAudioCtx = null;
  let micSourceNode = null;
  let micProcessorNode = null;
  let micMuteNode = null;
  let micChunkTimer = null;
  let micPcmChunks = [];
  let micPcmLength = 0;
  let micChunkQueue = [];
  let micIsProcessing = false;
  let micIsRunning = false;
  let micChunkId = 0;
  let micLastProcessMs = 0;

  const setMicInfo = (message) => {
    if (!ui || !ui.micInfoEl) return;
    ui.micInfoEl.textContent = message;
  };

  const nowMs = () =>
    typeof performance !== "undefined" && typeof performance.now === "function"
      ? performance.now()
      : Date.now();

  const formatMs = (value) => `${max(0, Number(value) || 0).toFixed(0)}ms`;
  const formatSec = (value) => `${(max(0, Number(value) || 0) / 1000).toFixed(2)}s`;

  const updateMicButtons = () => {
    if (!ui) return;
    if (!ui.toggleMicBtn) return;
    ui.toggleMicBtn.textContent = micIsRunning ? "Stop Mic" : "Start Mic";
  };

  const moveCaretWithText = (nextText) => {
    sourceTextEl.value = nextText;
    moveCaretToEnd();
    queueLiveApply(0);
  };

  const sanitizeTranscriptChunk = (rawText) => {
    let text = String(rawText || "");

    // Drop common non-speech tags from whisper-style outputs.
    text = text.replace(
      /\[\s*(?:blank[\s_-]*audio|laugh(?:ter)?|music|applause|silence|noise|inaudible|crosstalk|background[^\]]*)\s*\]/gi,
      " "
    );
    text = text.replace(
      /<\s*(?:laugh(?:ter)?|music|applause|silence|noise|inaudible|crosstalk|background[^>]*)\s*>/gi,
      " "
    );

    return text.replace(/\s+/g, " ").trim();
  };

  const appendTranscriptChunk = (rawText) => {
    const compact = sanitizeTranscriptChunk(rawText);
    if (compact.length === 0) return;
    if (/^\[?\s*blank[\s_-]*audio\s*\]?$/i.test(compact)) return;

    const current = sourceTextEl.value;
    const needsSpace = current.length > 0 && !/[\s\n]$/.test(current);
    const nextText = current + (needsSpace ? " " : "") + compact;
    moveCaretWithText(nextText);
  };

  const clearMicChunkTimer = () => {
    if (micChunkTimer !== null) {
      clearInterval(micChunkTimer);
      micChunkTimer = null;
    }
  };

  const downsampleMonoPcm = (input, inRate, outRate) => {
    if (!input || input.length === 0) return new Float32Array(0);
    if (!Number.isFinite(inRate) || !Number.isFinite(outRate) || outRate <= 0 || inRate <= 0) {
      return input;
    }
    if (outRate >= inRate) return input;

    const ratio = inRate / outRate;
    const length = max(1, floor(input.length / ratio));
    const output = new Float32Array(length);
    let inOffset = 0;

    for (let outIdx = 0; outIdx < length; outIdx += 1) {
      const nextInOffset = min(input.length, floor((outIdx + 1) * ratio));
      let sum = 0;
      let count = 0;
      for (let i = inOffset; i < nextInOffset; i += 1) {
        sum += input[i];
        count += 1;
      }
      output[outIdx] = count > 0 ? sum / count : 0;
      inOffset = nextInOffset;
    }

    return output;
  };

  const encodeMonoFloat32ToWavBlob = (samples, sampleRate) => {
    const bytesPerSample = 2;
    const channels = 1;
    const dataSize = samples.length * bytesPerSample;
    const buffer = new ArrayBuffer(44 + dataSize);
    const view = new DataView(buffer);
    let offset = 0;

    const writeAscii = (str) => {
      for (let i = 0; i < str.length; i += 1) {
        view.setUint8(offset + i, str.charCodeAt(i));
      }
      offset += str.length;
    };

    writeAscii("RIFF");
    view.setUint32(offset, 36 + dataSize, true);
    offset += 4;
    writeAscii("WAVE");
    writeAscii("fmt ");
    view.setUint32(offset, 16, true);
    offset += 4;
    view.setUint16(offset, 1, true);
    offset += 2;
    view.setUint16(offset, channels, true);
    offset += 2;
    view.setUint32(offset, sampleRate, true);
    offset += 4;
    view.setUint32(offset, sampleRate * channels * bytesPerSample, true);
    offset += 4;
    view.setUint16(offset, channels * bytesPerSample, true);
    offset += 2;
    view.setUint16(offset, 16, true);
    offset += 2;
    writeAscii("data");
    view.setUint32(offset, dataSize, true);
    offset += 4;

    for (let i = 0; i < samples.length; i += 1) {
      const s = max(-1, min(1, samples[i]));
      const v = s < 0 ? s * 0x8000 : s * 0x7fff;
      view.setInt16(offset, v, true);
      offset += 2;
    }

    return new Blob([buffer], { type: "audio/wav" });
  };

  const flushMicPcmChunk = () => {
    if (micPcmLength <= 0) return;

    const merged = new Float32Array(micPcmLength);
    let cursor = 0;
    for (let i = 0; i < micPcmChunks.length; i += 1) {
      merged.set(micPcmChunks[i], cursor);
      cursor += micPcmChunks[i].length;
    }

    micPcmChunks = [];
    micPcmLength = 0;

    const inputRate = micAudioCtx ? micAudioCtx.sampleRate : MIC_TARGET_SAMPLE_RATE;
    const outputRate = inputRate > MIC_TARGET_SAMPLE_RATE ? MIC_TARGET_SAMPLE_RATE : inputRate;
    const output = downsampleMonoPcm(merged, inputRate, outputRate);
    const wavBlob = encodeMonoFloat32ToWavBlob(output, outputRate);
    micChunkId += 1;
    const audioMs = outputRate > 0 ? (output.length / outputRate) * 1000 : 0;
    const queuedChunk = {
      id: micChunkId,
      blob: wavBlob,
      audioMs,
      enqueuedAtMs: nowMs()
    };

    micChunkQueue.push(queuedChunk);
    if (micChunkQueue.length > MIC_MAX_QUEUE) {
      const overflow = micChunkQueue.length - MIC_MAX_QUEUE;
      const dropped = micChunkQueue.splice(0, overflow);
      const droppedIds = dropped.map((chunk) => (chunk && chunk.id ? chunk.id : "?")).join(", ");
      console.warn(`[mic] dropped ${dropped.length} old chunks due to backlog: [${droppedIds}]`);
    }
    console.info(
      `[mic] queued chunk-${queuedChunk.id} audio=${formatSec(audioMs)} queue=${micChunkQueue.length}`
    );
    drainMicQueue();
  };

  const parseWhisperResponseText = async (response) => {
    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      const payload = await response.json();
      if (payload && typeof payload.text === "string") return payload.text;
      return "";
    }
    return response.text();
  };

  const transcribeMicChunk = async (queuedChunk) => {
    if (!queuedChunk || !queuedChunk.blob) return;

    const chunkId = queuedChunk.id;
    const blob = queuedChunk.blob;
    const queueWaitMs = nowMs() - (queuedChunk.enqueuedAtMs || nowMs());
    const processStartMs = nowMs();
    const formData = new FormData();
    formData.append("file", blob, `chunk-${chunkId}.wav`);
    formData.append("response_format", "json");
    formData.append("temperature", "0.0");
    formData.append("temperature_inc", "0.2");
    formData.append("no_timestamps", "true");
    formData.append("language", "en");

    const fetchStartMs = nowMs();
    const response = await fetch(WHISPER_INFERENCE_PATH, {
      method: "POST",
      body: formData
    });
    const fetchMs = nowMs() - fetchStartMs;

    if (!response.ok) {
      const details = await response.text();
      throw new Error(`whisper ${response.status} ${details.slice(0, 120)}`);
    }

    const parseStartMs = nowMs();
    const text = await parseWhisperResponseText(response);
    const parseMs = nowMs() - parseStartMs;
    const totalMs = nowMs() - processStartMs;
    micLastProcessMs = totalMs;
    appendTranscriptChunk(text);
    const audioMs = queuedChunk.audioMs || 0;
    const rtf = audioMs > 0 ? totalMs / audioMs : 0;
    console.info(
      `[mic] chunk-${chunkId} ok queueWait=${formatMs(queueWaitMs)} fetch=${formatMs(fetchMs)} parse=${formatMs(parseMs)} total=${formatMs(totalMs)} audio=${formatSec(audioMs)} rtf=${rtf.toFixed(2)} textLen=${text.length}`
    );

    if (micIsRunning) {
      setMicInfo(`Mic: listening (${micChunkQueue.length} queued) | last ${formatMs(micLastProcessMs)}`);
    } else {
      setMicInfo(
        `Mic: processing backlog (${micChunkQueue.length} queued) | last ${formatMs(micLastProcessMs)}`
      );
    }
  };

  const releaseMicResources = async () => {
    clearMicChunkTimer();

    if (micProcessorNode) {
      micProcessorNode.onaudioprocess = null;
      micProcessorNode.disconnect();
    }
    if (micSourceNode) micSourceNode.disconnect();
    if (micMuteNode) micMuteNode.disconnect();

    if (micStream) {
      const tracks = micStream.getTracks();
      for (let i = 0; i < tracks.length; i += 1) tracks[i].stop();
    }

    if (micAudioCtx && micAudioCtx.state !== "closed") {
      try {
        await micAudioCtx.close();
      } catch (_error) {
        // noop
      }
    }

    micPcmChunks = [];
    micPcmLength = 0;
    micSourceNode = null;
    micProcessorNode = null;
    micMuteNode = null;
    micAudioCtx = null;
    micStream = null;
  };

  const drainMicQueue = async () => {
    if (micIsProcessing) return;
    micIsProcessing = true;

    try {
      while (micChunkQueue.length > 0) {
        const queuedChunk = micChunkQueue.shift();
        if (!queuedChunk || !queuedChunk.blob || queuedChunk.blob.size === 0) continue;
        await transcribeMicChunk(queuedChunk);
      }
    } catch (error) {
      const message = error && error.message ? error.message : String(error);
      setMicInfo(`Mic error: ${message}`);
      micIsRunning = false;
      updateMicButtons();
      await releaseMicResources();
    } finally {
      micIsProcessing = false;
    }
  };

  const stopMicCapture = async (statusMessage, discardPending) => {
    micIsRunning = false;
    updateMicButtons();
    clearMicChunkTimer();
    if (discardPending) {
      micPcmChunks = [];
      micPcmLength = 0;
      micChunkQueue = [];
    } else {
      flushMicPcmChunk();
    }
    await releaseMicResources();
    if (!discardPending && micChunkQueue.length > 0) drainMicQueue();
    setMicInfo(statusMessage || "Mic: stopped");
    return true;
  };

  const startMicCapture = async () => {
    if (micIsRunning) return true;

    if (window.location.protocol === "file:") {
      setMicInfo("Mic error: open this page via whisper-server URL (http://127.0.0.1:8080).");
      return false;
    }

    if (!navigator.mediaDevices || typeof navigator.mediaDevices.getUserMedia !== "function") {
      setMicInfo("Mic error: browser does not support getUserMedia.");
      return false;
    }

    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) {
      setMicInfo("Mic error: browser does not support Web Audio API.");
      return false;
    }

    try {
      micStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      });

      micAudioCtx = new AudioCtx();
      if (micAudioCtx.state === "suspended") await micAudioCtx.resume();

      micSourceNode = micAudioCtx.createMediaStreamSource(micStream);
      micProcessorNode = micAudioCtx.createScriptProcessor(MIC_PROCESSOR_BUFFER_SIZE, 1, 1);
      micMuteNode = micAudioCtx.createGain();
      micMuteNode.gain.value = 0;

      micSourceNode.connect(micProcessorNode);
      micProcessorNode.connect(micMuteNode);
      micMuteNode.connect(micAudioCtx.destination);

      micProcessorNode.onaudioprocess = (event) => {
        if (!micIsRunning) return;

        const inBuffer = event.inputBuffer;
        const channels = inBuffer.numberOfChannels;
        const sampleCount = inBuffer.length;
        if (channels <= 0 || sampleCount <= 0) return;

        const mono = new Float32Array(sampleCount);
        for (let s = 0; s < sampleCount; s += 1) {
          let sum = 0;
          for (let ch = 0; ch < channels; ch += 1) {
            sum += inBuffer.getChannelData(ch)[s];
          }
          mono[s] = sum / channels;
        }

        micPcmChunks.push(mono);
        micPcmLength += mono.length;

        const outBuffer = event.outputBuffer;
        for (let ch = 0; ch < outBuffer.numberOfChannels; ch += 1) {
          outBuffer.getChannelData(ch).fill(0);
        }
      };

      micIsRunning = true;
      updateMicButtons();
      setMicInfo(`Mic: listening (PCM WAV) -> POST ${WHISPER_INFERENCE_PATH}`);
      clearMicChunkTimer();
      micChunkTimer = setInterval(flushMicPcmChunk, MIC_CHUNK_MS);
      return true;
    } catch (error) {
      const message = error && error.message ? error.message : String(error);
      setMicInfo(`Mic start failed: ${message}`);
      micIsRunning = false;
      updateMicButtons();
      await releaseMicResources();
      return false;
    }
  };

  ui.isMicRunning = () => micIsRunning;
  ui.startMicCapture = async () => startMicCapture();
  ui.stopMicCapture = async (statusMessage, discardPending) =>
    stopMicCapture(statusMessage || "Mic: stopped", discardPending === true);

  toggleMicBtn.addEventListener("click", async () => {
    if (micIsRunning) {
      await stopMicCapture("Mic: stopped", true);
      return;
    }
    await startMicCapture();
  });

  window.addEventListener("beforeunload", async () => {
    await stopMicCapture("Mic: idle", true);
  });

  updateMicButtons();

  if (useDefaultBtn) {
    useDefaultBtn.style.display = "none";
    useDefaultBtn.disabled = true;
  }

  pauseBtn.addEventListener("click", () => {
    requestRuntimeActive(false);
  });
}

function setConverterInfo(message) {
  if (!ui || !ui.infoEl) return;
  ui.infoEl.textContent = message;
}

function clearTranscriptSource(silentUi) {
  activeByteGroups = [];
  activeByteMeta = [];
  activeSourceText = "";
  sourceLabel = "utf-8 text";
  sourceTextChars = 0;

  if (ui && ui.sourceTextEl) {
    ui.sourceTextEl.value = "";
  }

  if (!silentUi) {
    setConverterInfo("Transcript cleared\\nChars: 0\\nBytes: 0");
  }
}

function applyTextSource(text, silentUi) {
  const data = utf8TextToByteData(text);
  activeByteGroups = data.groups;
  activeByteMeta = data.meta;
  activeSourceText = text;
  sourceLabel = "utf-8 text";
  sourceTextChars = Array.from(text).length;
  initializeSimulation();
  setPaused(false);

  if (!silentUi) {
    setConverterInfo(
      `Applied UTF-8 text source\\nChars: ${text.length}\\nBytes: ${activeByteGroups.length}`
    );
  } else {
    setConverterInfo(
      `Ready for dictation\\nChars: ${text.length}\\nBytes: ${activeByteGroups.length}`
    );
  }
}

function countLineBreaks(text) {
  let count = 0;
  for (let i = 0; i < text.length; i += 1) {
    if (text[i] === "\n") count += 1;
  }
  return count;
}

function collectUsedWrappedLineIds(pieceTemplates, byteMeta, byteCount, wrapCols) {
  const used = new Set();
  if (!Array.isArray(pieceTemplates) || pieceTemplates.length === 0) return used;
  if (byteCount <= 0) return used;

  const previewLineIds = buildWrappedPreviewLineIds(byteMeta, byteCount, wrapCols);
  for (let i = 0; i < pieceTemplates.length; i += 1) {
    const template = pieceTemplates[i];
    if (!template) continue;
    const idx = template.byteIndex;
    if (!Number.isInteger(idx) || idx < 0 || idx >= previewLineIds.length) continue;
    const lineId = previewLineIds[idx];
    if (Number.isInteger(lineId)) used.add(lineId);
  }

  return used;
}

function appendBytesToLiveSimulation(appendedGroups, appendedMeta, nextText) {
  if (!sim || appendedGroups.length === 0) return;

  const oldByteCount = activeByteGroups.length;
  activeByteGroups = activeByteGroups.concat(appendedGroups);
  activeByteMeta = activeByteMeta.concat(appendedMeta);
  activeSourceText = nextText;
  sourceLabel = "utf-8 text";
  sourceTextChars = Array.from(nextText).length;

  sim.byteGroups = sim.byteGroups.concat(appendedGroups);
  sim.byteMeta = sim.byteMeta.concat(appendedMeta);
  sim.sourceText = activeSourceText;
  sim.sourceLabel = sourceLabel;
  sim.sourceChars = sourceTextChars;
  sim.sourceBytes = activeByteGroups.length;
  sim.sourceRows = ceil(activeByteGroups.length / BYTES_PER_ROW) * CHUNK_ROWS;

  const usedLineIds = collectUsedWrappedLineIds(
    sharedPieceTemplates,
    activeByteMeta,
    activeByteGroups.length,
    sim.wrapCols
  );
  const appendedTemplates = buildPieceTemplatesForByteRange(
    activeByteGroups,
    activeByteMeta,
    sim.wrapCols,
    oldByteCount,
    activeByteGroups.length,
    usedLineIds
  );

  if (appendedTemplates.length > 0) {
    sharedPieceTemplates = sharedPieceTemplates.concat(appendedTemplates);
    ensureAllOwnersHaveQueuedPieces();
    spawnWaitingPieces();
  }
}

function applyTextSourceStreaming(text, silentUi) {
  if (sourceLabel !== "utf-8 text" || !sim) {
    applyTextSource(text, silentUi);
    return;
  }

  if (text === activeSourceText) return;

  const prevText = activeSourceText;
  if (!text.startsWith(prevText)) {
    applyTextSource(text, silentUi);
    return;
  }

  const appendedText = text.slice(prevText.length);
  if (appendedText.length === 0) return;

  const appended = utf8TextToByteData(appendedText);
  const charOffset = sourceTextChars;
  const lineOffset = countLineBreaks(prevText);
  const appendedMeta = appended.meta.map((meta) => ({
    char: meta.char,
    charIndex: meta.charIndex + charOffset,
    lineIndex: meta.lineIndex + lineOffset,
    part: meta.part,
    total: meta.total
  }));

  appendBytesToLiveSimulation(appended.groups, appendedMeta, text);

  if (!silentUi) {
    setConverterInfo(
      `Streaming append\\n+Chars: ${Array.from(appendedText).length}\\n+Bytes: ${appended.groups.length}\\nTotal bytes: ${activeByteGroups.length}`
    );
  }
}

function buildWrappedPreviewLineIds(byteMeta, byteCount, wrapCols) {
  const cols = Math.max(1, wrapCols || BYTES_PER_ROW);
  const lineIds = Array(byteCount).fill(0);
  if (byteCount === 0) return lineIds;

  let visualLine = 0;
  let col = 0;
  let currentTextLine =
    Array.isArray(byteMeta) && byteMeta[0] && Number.isInteger(byteMeta[0].lineIndex)
      ? byteMeta[0].lineIndex
      : 0;

  for (let i = 0; i < byteCount; i += 1) {
    const meta = Array.isArray(byteMeta) ? byteMeta[i] : null;
    const lineIndex =
      meta && Number.isInteger(meta.lineIndex) ? meta.lineIndex : currentTextLine;

    if (i > 0 && lineIndex !== currentTextLine) {
      visualLine += 1;
      col = 0;
    }

    lineIds[i] = visualLine;
    col += 1;

    if (col >= cols) {
      visualLine += 1;
      col = 0;
    }

    currentTextLine = lineIndex;
  }

  return lineIds;
}

function buildLinePreviewTemplateMap(previewLineIds, pieceTemplates) {
  const map = new Map();
  if (!Array.isArray(pieceTemplates)) return map;

  for (let i = 0; i < pieceTemplates.length; i += 1) {
    const template = pieceTemplates[i];
    if (!template) continue;
    const byteIndex = template.byteIndex;
    if (byteIndex < 0 || byteIndex >= previewLineIds.length) continue;
    const lineId = previewLineIds[byteIndex];
    if (!Number.isInteger(lineId)) continue;
    if (!map.has(lineId)) map.set(lineId, template);
  }

  return map;
}

function buildPieceByByteIndexMap() {
  const map = new Map();
  if (!sim || !Array.isArray(sim.pieces)) return map;

  for (let i = 0; i < sim.pieces.length; i += 1) {
    const piece = sim.pieces[i];
    if (!piece) continue;

    const prev = map.get(piece.byteIndex);
    if (!prev) {
      map.set(piece.byteIndex, piece);
      continue;
    }

    // Prefer actively falling piece over settled/waiting for display color.
    if (!prev.active && piece.active) map.set(piece.byteIndex, piece);
  }

  return map;
}

function getLinePreviewStyle(template, pieceByByteIndex) {
  if (!template) {
    return {
      hasBlock: false,
      fill: PREVIEW_NEUTRAL.empty,
      stroke: PREVIEW_NEUTRAL.laneStroke
    };
  }

  const piece = pieceByByteIndex.get(template.byteIndex) || null;
  if (!piece) {
    return {
      hasBlock: true,
      fill: PREVIEW_NEUTRAL.unset,
      stroke: PREVIEW_NEUTRAL.mixedStroke
    };
  }
  return resolvePreviewPieceStyle(piece);
}

function drawLinePiecePreview(template, laneX, laneY, style) {
  const boxW = 42;
  const boxH = 22;
  const cell = 5;
  const padX = 11;
  const padY = 6;

  if (!style || !style.hasBlock) return;
  if (!template || !Array.isArray(template.offsets) || template.offsets.length === 0) return;

  stroke(PREVIEW_NEUTRAL.laneStroke[0], PREVIEW_NEUTRAL.laneStroke[1], PREVIEW_NEUTRAL.laneStroke[2], 180);
  strokeWeight(1);
  fill(PREVIEW_NEUTRAL.laneFill[0], PREVIEW_NEUTRAL.laneFill[1], PREVIEW_NEUTRAL.laneFill[2]);
  rect(laneX, laneY, boxW, boxH, 4);

  stroke(style.stroke[0], style.stroke[1], style.stroke[2], 220);
  strokeWeight(1);
  fill(style.fill[0], style.fill[1], style.fill[2]);
  for (let i = 0; i < template.offsets.length; i += 1) {
    const rr = template.offsets[i].row;
    const cc = template.offsets[i].col;
    rect(laneX + padX + cc * cell, laneY + padY + rr * cell, cell, cell);
  }
}

function buildPreviewRowByteIndexMap(previewLineIds, byteCount) {
  const rowMap = new Map();
  for (let idx = 0; idx < byteCount; idx += 1) {
    const row = previewLineIds[idx];
    if (!rowMap.has(row)) rowMap.set(row, []);
    rowMap.get(row).push(idx);
  }
  return rowMap;
}

function buildPreviewDisplayItems(totalRows, currentRow, maxItems, priorityRows) {
  if (totalRows <= 0) {
    return [{ type: "row", row: 0 }];
  }

  const clampedCurrent = max(0, min(totalRows - 1, Number.isInteger(currentRow) ? currentRow : 0));
  const limit = max(1, Number.isInteger(maxItems) ? maxItems : totalRows);
  const prioritySet = new Set();
  const focusRows = [];
  if (Array.isArray(priorityRows)) {
    for (let i = 0; i < priorityRows.length; i += 1) {
      const row = priorityRows[i];
      if (!Number.isInteger(row)) continue;
      const clamped = max(0, min(totalRows - 1, row));
      if (prioritySet.has(clamped)) continue;
      prioritySet.add(clamped);
      focusRows.push(clamped);
    }
  }
  if (focusRows.length === 0) {
    focusRows.push(clampedCurrent);
  }

  focusRows.sort((a, b) => a - b);

  const maxFocusRows = max(1, min(limit, focusRows.length));
  const visibleFocusRows = focusRows.slice(focusRows.length - maxFocusRows);
  const compactFocusRows = visibleFocusRows.length > 1;

  const baseItems = [];
  const firstFocus = visibleFocusRows[0];
  if (!compactFocusRows && firstFocus > 0) {
    baseItems.push({ type: "gap", hidden: firstFocus });
  }
  baseItems.push({ type: "row", row: firstFocus });

  for (let i = 1; i < visibleFocusRows.length; i += 1) {
    const prev = visibleFocusRows[i - 1];
    const row = visibleFocusRows[i];
    const hidden = row - prev - 1;
    if (!compactFocusRows && hidden > 0) {
      baseItems.push({ type: "gap", hidden });
    }
    baseItems.push({ type: "row", row });
  }

  // If viewport is too short, keep focus rows first and drop gap labels.
  if (baseItems.length > limit) {
    const compact = visibleFocusRows
      .slice(visibleFocusRows.length - limit)
      .map((row) => ({ type: "row", row }));
    return compact;
  }

  const items = baseItems.slice();
  let remaining = limit - items.length;
  if (remaining <= 0) return items;

  const lastFocusRow = visibleFocusRows[visibleFocusRows.length - 1];
  const upcomingRows = [];
  for (let row = lastFocusRow + 1; row < totalRows; row += 1) {
    upcomingRows.push(row);
  }
  if (upcomingRows.length === 0) return items;

  if (upcomingRows.length <= remaining) {
    for (let i = 0; i < upcomingRows.length; i += 1) {
      items.push({ type: "row", row: upcomingRows[i] });
    }
    return items;
  }

  const UPCOMING_HEAD_KEEP = 3;
  const headCount = min(UPCOMING_HEAD_KEEP, remaining, upcomingRows.length);
  for (let i = 0; i < headCount; i += 1) {
    items.push({ type: "row", row: upcomingRows[i] });
  }
  remaining -= headCount;
  if (remaining <= 0) return items;

  const headEndRow = upcomingRows[headCount - 1];
  const firstTailCandidate = headEndRow + 1;

  if (remaining === 1) {
    items.push({ type: "row", row: totalRows - 1 });
    return items;
  }

  const tailCount = remaining - 1;
  const tailStart = max(firstTailCandidate, totalRows - tailCount);
  const hiddenMiddle = max(0, tailStart - firstTailCandidate);
  if (hiddenMiddle > 0) {
    items.push({ type: "gap", hidden: hiddenMiddle });
  }

  for (let row = tailStart; row < totalRows; row += 1) {
    if (items.length >= limit) break;
    items.push({ type: "row", row });
  }

  return items.slice(0, limit);
}

function buildPieceTemplatesForByteRange(
  byteGroups,
  byteMeta,
  wrapCols,
  startByteIndex,
  endByteIndex,
  occupiedLineIds
) {
  const pieces = [];
  const usedLineIds = occupiedLineIds ? new Set(occupiedLineIds) : new Set();
  const previewLineIds = buildWrappedPreviewLineIds(byteMeta, byteGroups.length, wrapCols);
  const start = Math.max(0, startByteIndex || 0);
  const end = Math.min(byteGroups.length, endByteIndex == null ? byteGroups.length : endByteIndex);

  if (start >= end) return pieces;

  for (let i = start; i < end; i += 1) {
    const byte = byteGroups[i];
    const byteRow = floor(i / BYTES_PER_ROW);
    const byteSlot = i % BYTES_PER_ROW;
    const byteBaseRow = byteRow * CHUNK_ROWS;
    const byteBaseCol = byteSlot * CHUNK_COLS;
    const chunkGrid = byteToChunkGrid(byte);
    const components = extractChunkComponents(chunkGrid);
    const lineId = previewLineIds[i];

    // White bits are true empty space: bytes with no 1s produce no piece.
    if (components.length === 0) continue;
    if (usedLineIds.has(lineId)) continue;

    for (let compIdx = 0; compIdx < components.length; compIdx += 1) {
      const component = components[compIdx];
      if (component.length !== 4) continue;

      let minRow = Infinity;
      let minCol = Infinity;

      for (let k = 0; k < component.length; k += 1) {
        minRow = min(minRow, component[k].row);
        minCol = min(minCol, component[k].col);
      }

      const offsets = [];
      for (let k = 0; k < component.length; k += 1) {
        offsets.push({
          row: component[k].row - minRow,
          col: component[k].col - minCol
        });
      }

      // Spawn ordering should be left-to-right within the same byte.
      // Do not offset order by minRow.
      const sourceRow = byteBaseRow;
      const sourceCol = byteBaseCol + minCol;
      pieces.push({
        id: pieces.length,
        byteIndex: i,
        byteBits: byte,
        byteMinRow: minRow,
        byteMinCol: minCol,
        sourceRow,
        sourceCol,
        offsets,
        row: 0,
        col: sourceCol,
        active: false,
        settled: false
      });

      usedLineIds.add(lineId);
      break;
    }
  }

  return pieces;
}

function buildPieceTemplatesFromByteGroups(byteGroups, byteMeta, wrapCols) {
  return buildPieceTemplatesForByteRange(
    byteGroups,
    byteMeta,
    wrapCols,
    0,
    byteGroups.length,
    new Set()
  );
}

function byteToChunkGrid(byte) {
  const grid = Array.from({ length: CHUNK_ROWS }, () => Array(CHUNK_COLS).fill(0));

  for (let bitIdx = 0; bitIdx < BYTE_WIDTH; bitIdx += 1) {
    if (byte[bitIdx] !== "1") continue;

    const row = floor(bitIdx / CHUNK_COLS);
    const col = bitIdx % CHUNK_COLS;
    if (row < CHUNK_ROWS) grid[row][col] = 1;
  }

  return grid;
}

function extractChunkComponents(chunkGrid) {
  const visited = Array.from({ length: CHUNK_ROWS }, () => Array(CHUNK_COLS).fill(false));
  const components = [];

  for (let row = 0; row < CHUNK_ROWS; row += 1) {
    for (let col = 0; col < CHUNK_COLS; col += 1) {
      if (chunkGrid[row][col] !== 1 || visited[row][col]) continue;

      const queue = [{ row, col }];
      const component = [];
      visited[row][col] = true;

      while (queue.length > 0) {
        const node = queue.shift();
        component.push(node);

        for (let i = 0; i < CHUNK_NEIGHBORS.length; i += 1) {
          const [dr, dc] = CHUNK_NEIGHBORS[i];
          const nr = node.row + dr;
          const nc = node.col + dc;

          if (nr < 0 || nr >= CHUNK_ROWS || nc < 0 || nc >= CHUNK_COLS) continue;
          if (visited[nr][nc] || chunkGrid[nr][nc] !== 1) continue;

          visited[nr][nc] = true;
          queue.push({ row: nr, col: nc });
        }
      }

      components.push(component);
    }
  }

  return components;
}

function updateSimulation() {
  if (!sim || sim.stalled) return;

  sim.frame += 1;
  ensureAllOwnersHaveQueuedPieces();
  spawnWaitingPieces();

  sim.fallProgress += FALL_STEPS_PER_FRAME;
  const fallSteps = floor(sim.fallProgress);
  sim.fallProgress -= fallSteps;

  for (let step = 0; step < fallSteps; step += 1) {
    const locked = applyRigidGravityStep();
    if (locked && !hasActivePiece()) {
      clearCompletedRows();
    }
  }

  ensureAllOwnersHaveQueuedPieces();
  spawnWaitingPieces();

  sim.occupiedCells = countOccupiedCells();
  sim.settledPieces = countSettledPieces();
}

function getWaitingPieceQueueIndexForOwner(owner) {
  for (let i = 0; i < sim.waiting.length; i += 1) {
    const pieceId = sim.waiting[i];
    const piece = sim.pieces[pieceId];
    if (piece && piece.owner === owner) return i;
  }
  return -1;
}

function spawnWaitingPieces() {
  if (!sim || sim.waiting.length === 0) return;

  for (let owner = 0; owner < sim.playerCount; owner += 1) {
    if (hasActivePieceForOwner(owner)) continue;

    let spawnedForOwner = 0;
    while (spawnedForOwner < MAX_SPAWNS_PER_FRAME) {
      const waitingIndex = getWaitingPieceQueueIndexForOwner(owner);
      if (waitingIndex === -1) break;

      const pieceId = sim.waiting[waitingIndex];
      const piece = sim.pieces[pieceId];
      if (!piece) {
        sim.waiting.splice(waitingIndex, 1);
        continue;
      }

      const spawnRow = 0;
      const spawnCol = piece.sourceCol;

      const spawnCollision = getPlacementCollisionType(piece, spawnRow, spawnCol);
      if (spawnCollision !== "none") {
        // Only game-over when spawn is blocked by settled cells / bounds.
        // If another active piece is temporarily in the way, wait and retry next frame.
        if (spawnCollision !== "active") sim.stalled = true;
        break;
      }

      placePieceAt(piece, spawnRow, spawnCol);
      piece.active = true;
      piece.settled = false;
      sim.waiting.splice(waitingIndex, 1);
      sim.spawnedPieces += 1;
      if (sim.playerStats[owner]) sim.playerStats[owner].spawned += 1;
      spawnedForOwner += 1;
    }
  }
}

function applyRigidGravityStep() {
  let lockedAny = false;
  const active = [];
  for (let i = 0; i < sim.pieces.length; i += 1) {
    if (sim.pieces[i].active) active.push(sim.pieces[i]);
  }

  active.sort(compareActivePiecesByStepOrder);

  for (let i = 0; i < active.length; i += 1) {
    const piece = active[i];
    const collision = getDownCollisionType(piece);
    if (collision === "none") {
      movePieceDown(piece);
      piece.settled = false;
    } else if (collision === "active") {
      // Another falling piece is directly below: wait, but do not lock yet.
      piece.settled = false;
    } else {
      piece.settled = true;
      piece.active = false;
      if (sim.playerStats[piece.owner]) sim.playerStats[piece.owner].settled += 1;
      lockedAny = true;
    }
  }

  return lockedAny;
}

function compareActivePiecesByStepOrder(a, b) {
  const bottomDiff = pieceBottom(b) - pieceBottom(a);
  if (bottomDiff !== 0) return bottomDiff;

  // If bottoms are equal, move the piece that is physically lower first.
  const rowDiff = b.row - a.row;
  if (rowDiff !== 0) return rowDiff;

  const ownerDiff = a.owner - b.owner;
  if (ownerDiff !== 0) return ownerDiff;

  return a.id - b.id;
}

function getActivePieces() {
  const active = [];
  for (let i = 0; i < sim.pieces.length; i += 1) {
    if (sim.pieces[i].active) active.push(sim.pieces[i]);
  }
  return active;
}

function cloneBoardWithoutActivePieces(activePieces) {
  const board = sim.cells.map((row) => row.slice());

  for (let i = 0; i < activePieces.length; i += 1) {
    const piece = activePieces[i];
    for (let k = 0; k < piece.offsets.length; k += 1) {
      const rr = piece.row + piece.offsets[k].row;
      const cc = piece.col + piece.offsets[k].col;
      if (rr < 0 || rr >= SIM_ROWS || cc < 0 || cc >= GRID_COLS) continue;
      if (board[rr][cc] === piece.id) board[rr][cc] = null;
    }
  }

  return board;
}

function canPlacePieceOnBoard(board, piece, baseRow, baseCol) {
  for (let i = 0; i < piece.offsets.length; i += 1) {
    const rr = baseRow + piece.offsets[i].row;
    const cc = baseCol + piece.offsets[i].col;
    if (rr < 0 || rr >= SIM_ROWS || cc < 0 || cc >= GRID_COLS) return false;
    if (board[rr][cc] !== null) return false;
  }
  return true;
}

function paintPieceOnBoard(board, piece, baseRow, baseCol) {
  for (let i = 0; i < piece.offsets.length; i += 1) {
    const rr = baseRow + piece.offsets[i].row;
    const cc = baseCol + piece.offsets[i].col;
    board[rr][cc] = piece.id;
  }
}

function computeHardDropLandingRow(piece) {
  const board = sim.cells.map((row) => row.slice());

  // Remove the active piece from the board copy, then search the lowest legal row.
  for (let i = 0; i < piece.offsets.length; i += 1) {
    const rr = piece.row + piece.offsets[i].row;
    const cc = piece.col + piece.offsets[i].col;
    if (rr < 0 || rr >= SIM_ROWS || cc < 0 || cc >= GRID_COLS) continue;
    if (board[rr][cc] === piece.id) board[rr][cc] = null;
  }

  let landingRow = piece.row;
  while (canPlacePieceOnBoard(board, piece, landingRow + 1, piece.col)) {
    landingRow += 1;
  }

  return landingRow;
}

function computeProjectedLandingRows(activePieces) {
  const projectedRows = new Map();
  if (activePieces.length === 0) return projectedRows;

  const board = cloneBoardWithoutActivePieces(activePieces);
  const ordered = activePieces.slice().sort(compareActivePiecesByStepOrder);

  for (let i = 0; i < ordered.length; i += 1) {
    const piece = ordered[i];
    let landingRow = piece.row;

    while (canPlacePieceOnBoard(board, piece, landingRow + 1, piece.col)) {
      landingRow += 1;
    }

    projectedRows.set(piece.id, landingRow);
    paintPieceOnBoard(board, piece, landingRow, piece.col);
  }

  return projectedRows;
}

function hasActivePiece() {
  if (!sim) return false;
  for (let i = 0; i < sim.pieces.length; i += 1) {
    if (sim.pieces[i].active) return true;
  }
  return false;
}

function clearCompletedRows() {
  const fullRows = [];

  for (let row = 0; row < SIM_ROWS; row += 1) {
    let full = true;
    for (let col = 0; col < GRID_COLS; col += 1) {
      if (sim.cells[row][col] === null) {
        full = false;
        break;
      }
    }
    if (full) fullRows.push(row);
  }

  if (fullRows.length === 0) return 0;

  fullRows.sort((a, b) => b - a);
  const clearCount = fullRows.length;
  const clearSet = new Set(fullRows);

  const newCells = Array.from({ length: SIM_ROWS }, () => Array(GRID_COLS).fill(null));
  let writeRow = SIM_ROWS - 1;

  for (let readRow = SIM_ROWS - 1; readRow >= 0; readRow -= 1) {
    if (clearSet.has(readRow)) continue;
    for (let col = 0; col < GRID_COLS; col += 1) {
      newCells[writeRow][col] = sim.cells[readRow][col];
    }
    writeRow -= 1;
  }

  sim.cells = newCells;
  sim.linesCleared += clearCount;
  sim.clearEvents += 1;
  return clearCount;
}

function canPlacePieceAt(piece, baseRow, baseCol) {
  return getPlacementCollisionType(piece, baseRow, baseCol) === "none";
}

function getPlacementCollisionType(piece, baseRow, baseCol) {
  let blockedByBounds = false;
  let blockedBySettled = false;
  let blockedByActive = false;

  for (let i = 0; i < piece.offsets.length; i += 1) {
    const rr = baseRow + piece.offsets[i].row;
    const cc = baseCol + piece.offsets[i].col;

    if (rr < 0 || rr >= SIM_ROWS || cc < 0 || cc >= GRID_COLS) {
      blockedByBounds = true;
      continue;
    }

    const cell = sim.cells[rr][cc];
    if (cell === null || cell === piece.id) continue;

    const otherPiece = sim.pieces[cell];
    if (otherPiece && otherPiece.active) blockedByActive = true;
    else blockedBySettled = true;
  }

  if (blockedByBounds || blockedBySettled) return "blocked";
  if (blockedByActive) return "active";
  return "none";
}

function getDownCollisionType(piece) {
  let blockedByFloor = false;
  let blockedBySettled = false;
  let blockedByActive = false;

  for (let i = 0; i < piece.offsets.length; i += 1) {
    const rr = piece.row + piece.offsets[i].row;
    const cc = piece.col + piece.offsets[i].col;
    const nr = rr + 1;

    if (nr >= SIM_ROWS) {
      blockedByFloor = true;
      continue;
    }

    const belowId = sim.cells[nr][cc];
    if (belowId === null || belowId === piece.id) continue;

    const belowPiece = sim.pieces[belowId];
    if (belowPiece && belowPiece.active) blockedByActive = true;
    else blockedBySettled = true;
  }

  if (blockedByFloor) return "floor";
  if (blockedBySettled) return "settled";
  if (blockedByActive) return "active";
  return "none";
}

function canMovePieceDown(piece) {
  return getDownCollisionType(piece) === "none";
}

function canMovePieceHorizontal(piece, deltaCol) {
  for (let i = 0; i < piece.offsets.length; i += 1) {
    const rr = piece.row + piece.offsets[i].row;
    const nc = piece.col + piece.offsets[i].col + deltaCol;

    if (nc < 0 || nc >= GRID_COLS) return false;

    const side = sim.cells[rr][nc];
    if (side !== null && side !== piece.id) return false;
  }

  return true;
}

function moveActivePieceHorizontalForOwner(owner, deltaCol) {
  const piece = getActivePieceForOwner(owner);
  if (piece === null) return false;
  if (!canMovePieceHorizontal(piece, deltaCol)) return false;

  clearPieceCells(piece);
  piece.col += deltaCol;
  paintPieceCells(piece);
  piece.settled = false;
  return true;
}

function canPlacePieceShape(piece, offsets, baseRow, baseCol) {
  for (let i = 0; i < offsets.length; i += 1) {
    const rr = baseRow + offsets[i].row;
    const cc = baseCol + offsets[i].col;
    if (rr < 0 || rr >= SIM_ROWS || cc < 0 || cc >= GRID_COLS) return false;

    const cell = sim.cells[rr][cc];
    if (cell !== null && cell !== piece.id) return false;
  }
  return true;
}

function computeRotatedShape(offsets, clockwise) {
  const raw = [];

  for (let i = 0; i < offsets.length; i += 1) {
    const cell = offsets[i];
    if (clockwise) {
      raw.push({ row: cell.col, col: -cell.row });
    } else {
      raw.push({ row: -cell.col, col: cell.row });
    }
  }

  let minRow = Infinity;
  let minCol = Infinity;
  for (let i = 0; i < raw.length; i += 1) {
    minRow = min(minRow, raw[i].row);
    minCol = min(minCol, raw[i].col);
  }

  const normalized = [];
  for (let i = 0; i < raw.length; i += 1) {
    normalized.push({
      row: raw[i].row - minRow,
      col: raw[i].col - minCol
    });
  }

  return {
    offsets: normalized,
    rowShift: minRow,
    colShift: minCol
  };
}

function attemptRotateActivePieceForOwner(owner, clockwise) {
  const piece = getActivePieceForOwner(owner);
  if (piece === null) return false;

  const rotated = computeRotatedShape(piece.offsets, clockwise);
  const kicks = [
    { row: 0, col: 0 },
    { row: 0, col: 1 },
    { row: 0, col: -1 },
    { row: 0, col: 2 },
    { row: 0, col: -2 },
    { row: -1, col: 0 },
    { row: 1, col: 0 }
  ];

  clearPieceCells(piece);

  for (let i = 0; i < kicks.length; i += 1) {
    const nextRow = piece.row + rotated.rowShift + kicks[i].row;
    const nextCol = piece.col + rotated.colShift + kicks[i].col;

    if (!canPlacePieceShape(piece, rotated.offsets, nextRow, nextCol)) continue;

    piece.row = nextRow;
    piece.col = nextCol;
    piece.offsets = rotated.offsets;
    piece.settled = false;
    paintPieceCells(piece);
    return true;
  }

  paintPieceCells(piece);
  return false;
}

function hardDropActivePieceForOwner(owner) {
  const piece = getActivePieceForOwner(owner);
  if (piece === null) return false;

  // Hard-drop should affect only the owner's current piece.
  const landingRow = computeHardDropLandingRow(piece);
  if (landingRow > piece.row) {
    clearPieceCells(piece);
    piece.row = landingRow;
    paintPieceCells(piece);
  }

  const collision = getDownCollisionType(piece);
  if (collision === "active") {
    // A falling piece is directly below, so do not lock yet.
    piece.settled = false;
    sim.occupiedCells = countOccupiedCells();
    sim.settledPieces = countSettledPieces();
    return true;
  }

  piece.settled = true;
  piece.active = false;
  if (sim.playerStats[owner]) sim.playerStats[owner].settled += 1;

  if (!hasActivePiece()) {
    clearCompletedRows();
  }
  ensureOwnerHasQueuedPiece(owner);
  ensureAllOwnersHaveQueuedPieces();
  spawnWaitingPieces();
  sim.occupiedCells = countOccupiedCells();
  sim.settledPieces = countSettledPieces();
  return true;
}

function softDropActivePieceForOwner(owner) {
  const piece = getActivePieceForOwner(owner);
  if (piece === null) return false;

  const collision = getDownCollisionType(piece);
  if (collision === "none") {
    movePieceDown(piece);
    piece.settled = false;
    sim.occupiedCells = countOccupiedCells();
    sim.settledPieces = countSettledPieces();
    return true;
  }

  if (collision === "active") {
    piece.settled = false;
    return true;
  }

  piece.settled = true;
  piece.active = false;
  if (sim.playerStats[owner]) sim.playerStats[owner].settled += 1;

  if (!hasActivePiece()) {
    clearCompletedRows();
  }
  ensureOwnerHasQueuedPiece(owner);
  ensureAllOwnersHaveQueuedPieces();
  spawnWaitingPieces();
  sim.occupiedCells = countOccupiedCells();
  sim.settledPieces = countSettledPieces();
  return true;
}

function movePieceDown(piece) {
  clearPieceCells(piece);
  piece.row += 1;
  paintPieceCells(piece);
}

function drawProjectedLandingPiece(piece, landingRow, cell, x0, y0, palette) {
  if (landingRow <= piece.row) return;

  noStroke();
  fill(palette.ghost[0], palette.ghost[1], palette.ghost[2], 90);
  for (let i = 0; i < piece.offsets.length; i += 1) {
    const rr = landingRow + piece.offsets[i].row;
    const cc = piece.col + piece.offsets[i].col;
    rect(x0 + cc * cell, y0 + rr * cell, cell, cell);
  }
}

function placePieceAt(piece, baseRow, baseCol) {
  piece.row = baseRow;
  piece.col = baseCol;
  paintPieceCells(piece);
}

function clearPieceCells(piece) {
  for (let i = 0; i < piece.offsets.length; i += 1) {
    const rr = piece.row + piece.offsets[i].row;
    const cc = piece.col + piece.offsets[i].col;
    sim.cells[rr][cc] = null;
  }
}

function paintPieceCells(piece) {
  for (let i = 0; i < piece.offsets.length; i += 1) {
    const rr = piece.row + piece.offsets[i].row;
    const cc = piece.col + piece.offsets[i].col;
    sim.cells[rr][cc] = piece.id;
  }
}

function pieceBottom(piece) {
  let maxOffset = 0;
  for (let i = 0; i < piece.offsets.length; i += 1) {
    maxOffset = max(maxOffset, piece.offsets[i].row);
  }
  return piece.row + maxOffset;
}

function countOccupiedCells() {
  let count = 0;
  for (let row = 0; row < SIM_ROWS; row += 1) {
    for (let col = 0; col < GRID_COLS; col += 1) {
      if (sim.cells[row][col] !== null) count += 1;
    }
  }
  return count;
}

function countSettledPieces() {
  let count = 0;
  for (let i = 0; i < sim.pieces.length; i += 1) {
    if (sim.pieces[i].settled) count += 1;
  }
  return count;
}

function drawSimulation(x0, y0, cell) {
  const boardW = GRID_COLS * cell;
  const boardH = SIM_ROWS * cell;
  const railW = max(3, floor(cell * 0.22));
  const gutterW = max(4, floor(cell * 0.34));
  const shellPad = max(4, floor(cell * 0.38));

  noStroke();
  fill(244);
  rect(
    x0 - railW - gutterW - shellPad,
    y0 - shellPad,
    boardW + (railW + gutterW + shellPad) * 2,
    boardH + shellPad * 2
  );

  // 8-bit side gutters + black rails.
  fill(72);
  rect(x0 - railW - gutterW, y0, gutterW, boardH);
  rect(x0 + boardW + railW, y0, gutterW, boardH);

  fill(8);
  rect(x0 - railW, y0, railW, boardH);
  rect(x0 + boardW, y0, railW, boardH);
  rect(x0 - railW, y0 - railW, boardW + railW * 2, railW);
  rect(x0 - railW, y0 + boardH, boardW + railW * 2, railW);

  fill(250);
  rect(x0, y0, boardW, boardH);

  const activePieces = getActivePieces();
  const projectedRows = computeProjectedLandingRows(activePieces);
  const orderedActive = activePieces.slice().sort(compareActivePiecesByStepOrder);
  for (let i = 0; i < orderedActive.length; i += 1) {
    const piece = orderedActive[i];
    const landingRow = projectedRows.get(piece.id);
    if (!Number.isInteger(landingRow)) continue;
    drawProjectedLandingPiece(piece, landingRow, cell, x0, y0, getPlayerPalette(piece.owner));
  }

  noStroke();
  for (let row = 0; row < SIM_ROWS; row += 1) {
    for (let col = 0; col < GRID_COLS; col += 1) {
      const pieceId = sim.cells[row][col];
      if (pieceId === null) continue;
      const piece = sim.pieces[pieceId];
      const owner = piece ? piece.owner : 0;
      const palette = getPlayerPalette(owner);
      fill(palette.block[0], palette.block[1], palette.block[2]);
      rect(x0 + col * cell, y0 + row * cell, cell, cell);
    }
  }

  // Pixel-sharp board frame.
  noFill();
  stroke(18);
  strokeWeight(max(1, floor(cell * 0.08)));
  rect(x0, y0, boardW, boardH);
}

function drawNextPreviewPanel() {
  if (!sim) return;

  const config = getPreviewPanelConfig();
  const panelW = config.panelW;
  const footerH = config.footerH;
  const cols = config.cols;
  const contentPadX = 12;
  const contentW = panelW - contentPadX * 2;
  const baseBitSlots = max(1, config.cols * CHUNK_COLS);
  const displayBitSlots = max(1, cols * CHUNK_COLS);
  const scaledCell = (contentW / baseBitSlots) * PREVIEW_BLOCK_SCALE;
  const maxCellByDisplay = contentW / displayBitSlots;
  const blockCell = max(1, floor(min(maxCellByDisplay, scaledCell)));
  const blockCellW = blockCell;
  const blockCellH = blockCell;
  const blockRowH = CHUNK_ROWS * blockCellH;
  const panelRailW = max(3, floor(panelW * 0.008));
  const panelGutterW = max(4, floor(panelW * 0.012));
  const panelShellPad = max(4, floor(panelW * 0.01));
  const bytes = sim.byteGroups || [];
  const byteCount = bytes.length;
  const previewLineIds = buildWrappedPreviewLineIds(sim.byteMeta, byteCount, cols);
  const rows = byteCount > 0 ? previewLineIds[byteCount - 1] + 1 : 1;

  const stripeGap = max(4, floor(blockRowH * 1.0));
  let rowStride = blockRowH + stripeGap;
  // Keep transcript panel size stable even when source text is empty.
  const panelH = max(120, height - 20);

  let x = width - panelW - 14;
  let y = 14;

  if (y + panelH > height - 10) {
    y = Math.max(14, height - panelH - 10);
  }

  x = Math.max(10, Math.min(x, width - panelW - 10));
  y = Math.max(10, Math.min(y, height - panelH - 10));

  noStroke();
  fill(244);
  rect(
    x - panelRailW - panelGutterW - panelShellPad,
    y - panelShellPad,
    panelW + (panelRailW + panelGutterW + panelShellPad) * 2,
    panelH + panelShellPad * 2
  );

  // 8-bit side gutters + black rails around transcript panel.
  fill(76);
  rect(x - panelRailW - panelGutterW, y, panelGutterW, panelH);
  rect(x + panelW + panelRailW, y, panelGutterW, panelH);

  fill(10);
  rect(x - panelRailW, y, panelRailW, panelH);
  rect(x + panelW, y, panelRailW, panelH);
  rect(x - panelRailW, y - panelRailW, panelW + panelRailW * 2, panelRailW);
  rect(x - panelRailW, y + panelH, panelW + panelRailW * 2, panelRailW);

  fill(235, 235, 235, 250);
  rect(x, y, panelW, panelH);

  const completion = getByteCompletionMap();
  const { activeByByte, settledByByte } = getByteCellOwnerMaps();
  const { candidateByByte, selectedByByte } = getByteBitRoleMaps(bytes, sharedPieceTemplates);
  const pieceByByteIndex = buildPieceByByteIndexMap();
  const progress = computePreviewRowProgress(rows, previewLineIds);
  const startX = x + contentPadX;
  const contentRight = x + panelW - contentPadX;
  const startY = y + 14;
  const availableRowsH = max(1, floor(panelH - (startY - y) - footerH - 12));
  const minFocusRows = max(1, sim && Number.isInteger(sim.playerCount) ? sim.playerCount : 1);
  const maxStrideForFocusRows = floor(availableRowsH / minFocusRows);
  if (maxStrideForFocusRows > 0) {
    rowStride = min(rowStride, maxStrideForFocusRows);
  }
  const maxRowsVisible = max(minFocusRows, floor(availableRowsH / rowStride));
  const displayItems = buildPreviewDisplayItems(
    rows,
    progress.currentRow,
    maxRowsVisible,
    progress.ownerFocusRows
  );
  const rowsVisible = displayItems.length;
  const score = sim.linesCleared;
  const blocks = sim.settledPieces;

  const rowByteIndexMap = buildPreviewRowByteIndexMap(previewLineIds, byteCount);

  for (let rowSlot = 0; rowSlot < rowsVisible; rowSlot += 1) {
    const rowTop = startY + rowSlot * rowStride;
    const item = displayItems[rowSlot];
    if (!item) continue;

    if (item.type === "gap") {
      const midY = rowTop + floor(rowStride * 0.5);
      stroke(140, 140, 140, 180);
      strokeWeight(1);
      line(startX, midY, contentRight, midY);
      noStroke();
      fill(70);
      drawPixelText(
        `(... ${item.hidden} lines)`,
        startX + (contentRight - startX) * 0.5,
        rowTop + 6,
        9,
        CENTER,
        TOP
      );
      continue;
    }

    const globalRow = item.row;
    const rowIndices = rowByteIndexMap.get(globalRow) || [];
    if (!rowIndices || rowIndices.length === 0) continue;

    const blockY0 = rowTop + floor((rowStride - blockRowH) * 0.5);

    for (let i = 0; i < rowIndices.length; i += 1) {
      const idx = rowIndices[i];
      const bitString = bytes[idx];
      const isDone = completion.done[idx] === true;
      const activeOwnerGrid = activeByByte.get(idx) || null;
      const settledOwnerGrid = settledByByte.get(idx) || null;
      const candidateGrid = candidateByByte.get(idx) || null;
      const selectedGrid = selectedByByte.get(idx) || null;
      const pieceForByte = pieceByByteIndex.get(idx) || null;
      const queuedOwner =
        pieceForByte && !pieceForByte.active && !pieceForByte.settled
          ? pieceForByte.owner
          : OWNER_NONE;
      const byteX0 = startX + i * CHUNK_COLS * blockCellW;

      for (let bitIdx = 0; bitIdx < BYTE_WIDTH; bitIdx += 1) {
        const bit = bitString[bitIdx] === "1" ? 1 : 0;
        const br = floor(bitIdx / CHUNK_COLS);
        const bc = bitIdx % CHUNK_COLS;
        const activeOwner = activeOwnerGrid ? activeOwnerGrid[br][bc] : OWNER_NONE;
        const settledOwner = settledOwnerGrid ? settledOwnerGrid[br][bc] : OWNER_NONE;
        const isCandidateBit = candidateGrid ? candidateGrid[br][bc] === 1 : false;
        const isSelectedBit = selectedGrid ? selectedGrid[br][bc] === 1 : false;
        let bitRole = BIT_ROLE_BASE;
        if (isCandidateBit) bitRole = BIT_ROLE_CANDIDATE;
        if (isSelectedBit) bitRole = BIT_ROLE_SELECTED;

        if (bit === 0) {
          fill(PREVIEW_NEUTRAL.empty[0], PREVIEW_NEUTRAL.empty[1], PREVIEW_NEUTRAL.empty[2]);
        } else {
          const rgb = resolvePreviewBitFill(
            activeOwner,
            settledOwner,
            queuedOwner,
            isDone,
            bitRole
          );
          fill(rgb[0], rgb[1], rgb[2]);
        }

        noStroke();
        rect(
          byteX0 + bc * blockCellW,
          blockY0 + br * blockCellH,
          blockCellW,
          blockCellH
        );
      }
    }
  }

  const footerY = y + panelH - footerH;
  const footerBoxX = x + 8;
  const footerBoxY = footerY + 8;
  const footerBoxW = panelW - 16;
  const footerBoxH = footerH - 12;
  const footerRailW = 2;
  const footerGutterW = 2;

  noStroke();
  fill(224);
  rect(
    footerBoxX - footerRailW - footerGutterW,
    footerBoxY,
    footerBoxW + (footerRailW + footerGutterW) * 2,
    footerBoxH
  );

  fill(96);
  rect(footerBoxX - footerRailW - footerGutterW, footerBoxY, footerGutterW, footerBoxH);
  rect(footerBoxX + footerBoxW + footerRailW, footerBoxY, footerGutterW, footerBoxH);

  fill(12);
  rect(footerBoxX - footerRailW, footerBoxY, footerRailW, footerBoxH);
  rect(footerBoxX + footerBoxW, footerBoxY, footerRailW, footerBoxH);
  rect(footerBoxX - footerRailW, footerBoxY - footerRailW, footerBoxW + footerRailW * 2, footerRailW);
  rect(footerBoxX - footerRailW, footerBoxY + footerBoxH, footerBoxW + footerRailW * 2, footerRailW);

  noStroke();
  fill(242, 242, 242, 248);
  rect(footerBoxX, footerBoxY, footerBoxW, footerBoxH);
  fill(26);
  const footerTextSize = max(12, min(18, floor(footerBoxH * 0.58)));
  drawPixelText(
    `Score: ${score}  Blocks: ${blocks}`,
    x + panelW * 0.5,
    footerBoxY + 8,
    footerTextSize,
    CENTER,
    TOP
  );
  textFont("Georgia");
}

function drawHud() {
  if (!sim) return;

  noStroke();
  fill(24, 24, 24);
  drawPixelText("P1: A/D move, Q/E turn, S soft-drop, F hard-drop", 20, 24, 10, LEFT, TOP);
  if (playerMode === 2) {
    drawPixelText("P2: J/L move, U/O turn, K soft-drop, ; hard-drop", 20, 50, 10, LEFT, TOP);
    drawPixelText("1=1P mode, 2=2P mode | R reset | Enter/Space start-stop", 20, 76, 10, LEFT, TOP);
  } else {
    drawPixelText("Mode: 1P controls only", 20, 50, 10, LEFT, TOP);
    drawPixelText("1=1P mode, 2=2P mode | R reset | Enter/Space start-stop", 20, 76, 10, LEFT, TOP);
  }

  // Keep transcript panel typography unchanged.
  textFont("Georgia");
  drawNextPreviewPanel();

  const isGameOver = Boolean(sim && sim.stalled);

  if (isGameOver) {
    noStroke();
    fill(0, 0, 0, 96);
    rect(0, 0, width, height);

    const overSize = max(34, floor(min(width, height) * 0.09));
    const subSize = max(10, floor(overSize * 0.3));
    fill(30, 8, 8, 220);
    drawPixelText("GAME OVER", width * 0.5 + 3, height * 0.5 + 3, overSize, CENTER, CENTER);
    fill(236, 52, 52);
    drawPixelText("GAME OVER", width * 0.5, height * 0.5, overSize, CENTER, CENTER);

    fill(26, 10, 10, 220);
    drawPixelText("PRESS R TO RESET", width * 0.5 + 2, height * 0.5 + overSize * 0.72 + 2, subSize, CENTER, TOP);
    fill(245, 196, 196);
    drawPixelText("PRESS R TO RESET", width * 0.5, height * 0.5 + overSize * 0.72, subSize, CENTER, TOP);
  }

  if (paused && !isGameOver) {
    // Dim the scene and place a clear red pause badge at top-center.
    noStroke();
    fill(0, 0, 0, 56);
    rect(0, 0, width, height);

    const badgeW = 216;
    const badgeH = 40;
    const badgeX = width * 0.5 - badgeW * 0.5;
    const badgeY = 16;

    stroke(160, 18, 18);
    strokeWeight(2);
    fill(252, 236, 236, 242);
    rect(badgeX, badgeY, badgeW, badgeH, 4);

    noStroke();
    fill(92, 10, 10, 220);
    drawPixelText("PAUSED", width * 0.5 + 2, badgeY + 10 + 2, 20, CENTER, TOP);
    fill(238, 36, 36);
    drawPixelText("PAUSED", width * 0.5, badgeY + 10, 20, CENTER, TOP);

    if (!hasStartedAtLeastOnce) {
      const startSize = max(12, floor(min(width, height) * 0.03));
      const startY = height * 0.5;
      fill(18, 18, 18, 220);
      drawPixelText("PRESS SPACE / ENTER TO START", width * 0.5 + 2, startY + 2, startSize, CENTER, CENTER);
      fill(236, 52, 52);
      drawPixelText("PRESS SPACE / ENTER TO START", width * 0.5, startY, startSize, CENTER, CENTER);
    }
  }
}

function drawSky() {
  noStroke();
  fill(206);
  rect(0, 0, width, height);
}
