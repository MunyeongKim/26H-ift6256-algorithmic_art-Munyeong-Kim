const BLUE = "#000000";
const RECT_WIDTH = 576;
const RECT_HEIGHT = 1024;
const CELL_W = 72;
const CELL_H = 4;
const LEVELS = 8;
const LIGHT_BLUE = "#ffffff";
const DARK_BLUE = "#0a0f1f";
const BLUE_BIAS = "#3b6ce3";
const BLUE_BIAS_STRENGTH = 0.2;
const VINEGAR_LEVELS = 4;
const VINEGAR_LIGHT = "#ffffff";
const VINEGAR_TINT = "#f3e1a2";
const VINEGAR_MAX = 0.35;
const RED_LEVELS = 5;
const RED_LIGHT = "#ffffff";
const RED_DARK = "#b00010";
const RED_MAX = 0.4;
const RED_P = 0;
const RED_Q = 1 / 16;
const GRAIN_RANGE = 60;
const GRAIN_ALPHA = 70;
let palette = [];
let vinegarLight;
let vinegarTint;
let redLight;
let redDark;
let grainLayer;

function setup() {
  createCanvas(windowWidth, windowHeight);
  palette = buildPalette();
  vinegarLight = color(VINEGAR_LIGHT);
  vinegarTint = color(VINEGAR_TINT);
  redLight = color(RED_LIGHT);
  redDark = color(RED_DARK);
  grainLayer = buildGrainLayer();
}

function draw() {
  background(BLUE);
  noStroke();
  fill(255);
  rectMode(CENTER);
  rect(width / 2, height / 2, RECT_WIDTH, RECT_HEIGHT);

  const grid = getGrid();
  randomSeed(7);
  drawCells(grid);
  drawGrain(grid);
  // Grid lines removed per request.
}

function windowResized() {
  resizeCanvas(windowWidth, windowHeight);
}

function getGrid() {
  const halfW = RECT_WIDTH / 2;
  const halfH = RECT_HEIGHT / 2;
  const left = width / 2 - halfW;
  const right = width / 2 + halfW;
  const top = height / 2 - halfH;
  const bottom = height / 2 + halfH;
  const cols = floor(RECT_WIDTH / CELL_W);
  const rows = floor(RECT_HEIGHT / CELL_H);
  const cellW = RECT_WIDTH / cols;
  const cellH = RECT_HEIGHT / rows;

  return { left, right, top, bottom, cols, rows, cellW, cellH };
}

function drawCells(grid) {
  rectMode(CORNER);
  noStroke();

  const redProbs = getRedProbs();
  for (let col = 0; col < grid.cols; col += 1) {
    let level = floor(random(LEVELS));
    let vinegar = floor(random(VINEGAR_LEVELS));
    const redStart = initialRedLevel(col, grid.cols);
    let redLevel = redStart;
    for (let row = 0; row < grid.rows; row += 1) {
      const x = grid.left + col * grid.cellW;
      const y = grid.top + row * grid.cellH;
      const vinegarT = vinegar / (VINEGAR_LEVELS - 1);
      const weight = vinegarT * VINEGAR_MAX;
      const vinegarColor = lerpColor(vinegarLight, vinegarTint, vinegarT);
      let mixed = lerpColor(palette[level], vinegarColor, weight);
      const redT = redLevel / (RED_LEVELS - 1);
      const redWeight = redT * RED_MAX;
      const redColor = lerpColor(redLight, redDark, redT);
      mixed = lerpColor(mixed, redColor, redWeight);
      fill(mixed);
      rect(x, y, grid.cellW, grid.cellH);
      level = stepLevel(level);
      vinegar = stepVinegar(vinegar);
      redLevel = stepRed(redLevel, redProbs);
    }
  }
}

// Grid line drawing removed.

function buildPalette() {
  const light = color(LIGHT_BLUE);
  const dark = color(DARK_BLUE);
  const bias = color(BLUE_BIAS);
  const colors = [];
  for (let i = 0; i < LEVELS; i += 1) {
    const t = i / (LEVELS - 1);
    const base = lerpColor(light, dark, t);
    const shift = sin(PI * t) * BLUE_BIAS_STRENGTH;
    colors.push(lerpColor(base, bias, shift));
  }
  return colors;
}

function stepLevel(level) {
  const roll = random();
  if (roll < 0.25) level -= 1;
  else if (roll < 0.375) level += 1;
  return constrain(level, 0, LEVELS - 1);
}

function stepVinegar(level) {
  const roll = random();
  if (roll < 0.25) level -= 1;
  else if (roll < 0.375) level += 1;
  return constrain(level, 0, VINEGAR_LEVELS - 1);
}

function initialRedLevel(col, cols) {
  const band = 2;
  const start = floor((cols - band) / 2);
  const end = start + band;
  return col >= start && col < end ? RED_LEVELS - 1 : 0;
}

function getRedProbs() {
  const pUp = RED_P;
  const pDown = RED_Q;
  const pStay = constrain(1 - pUp - pDown, 0, 1);
  return { pUp, pDown, pStay };
}

function stepRed(level, probs) {
  const roll = random();
  if (roll < probs.pDown) level -= 1;
  else if (roll < probs.pDown + probs.pUp) level += 1;
  return constrain(level, 0, RED_LEVELS - 1);
}

function buildGrainLayer() {
  const layer = createGraphics(RECT_WIDTH, RECT_HEIGHT);
  layer.pixelDensity(1);
  layer.noSmooth();
  randomSeed(13);
  layer.loadPixels();
  for (let i = 0; i < layer.pixels.length; i += 4) {
    const v = 128 + floor(random(-GRAIN_RANGE, GRAIN_RANGE));
    layer.pixels[i] = v;
    layer.pixels[i + 1] = v;
    layer.pixels[i + 2] = v;
    layer.pixels[i + 3] = GRAIN_ALPHA;
  }
  layer.updatePixels();
  return layer;
}

function drawGrain(grid) {
  if (!grainLayer) return;
  push();
  blendMode(SOFT_LIGHT);
  image(grainLayer, grid.left, grid.top, RECT_WIDTH, RECT_HEIGHT);
  pop();
}
