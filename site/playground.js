const setPressed = (buttons, activeButton) => {
  for (const button of buttons) {
    button.classList.toggle("is-active", button === activeButton);
    button.setAttribute("aria-pressed", String(button === activeButton));
  }
};

const readings = {
  host: "下雨天，留客天；留我不？留。",
  guest: "下雨，天留客；天留我不留。",
  question: "下雨天留客，天留我不留？",
};

const readingButtons = [...document.querySelectorAll("[data-reading]")];
const readingOutput = document.querySelector("[data-reading-output]");
for (const button of readingButtons) {
  button.addEventListener("click", () => {
    setPressed(readingButtons, button);
    readingOutput.textContent = readings[button.dataset.reading];
  });
}

const tones = {
  calm: ["山雨将来，客问归期。灯未点，门先开。", 430],
  urgent: ["山雨将来！客问归期？灯未点——门先开！", 720],
  doubt: ["山雨将来？客问：「归期？」灯未点……门先开？", 350],
  exclaim: ["「山雨将来！」客问归期；灯未点，门先开！", 620],
};

const toneButtons = [...document.querySelectorAll("[data-tone]")];
const rhythmOutput = document.querySelector("[data-rhythm-output]");
for (const button of toneButtons) {
  button.addEventListener("click", () => {
    setPressed(toneButtons, button);
    const [text, weight] = tones[button.dataset.tone];
    rhythmOutput.textContent = text;
    rhythmOutput.style.fontWeight = weight;
  });
}

const makeSpiral = (size) => {
  const points = [];
  let row = Math.floor(size / 2);
  let column = Math.floor(size / 2);
  points.push([row, column]);
  const directions = [[0, 1], [-1, 0], [0, -1], [1, 0]];
  let distance = 1;
  let direction = 0;
  while (points.length < size * size) {
    for (let repeat = 0; repeat < 2; repeat += 1) {
      const [rowStep, columnStep] = directions[direction % 4];
      for (let step = 0; step < distance; step += 1) {
        row += rowStep;
        column += columnStep;
        if (row >= 0 && row < size && column >= 0 && column < size) {
          points.push([row, column]);
        }
      }
      direction += 1;
    }
    distance += 1;
  }
  return points.slice(0, size * size);
};

const spiralGrid = document.querySelector("[data-spiral-grid]");
const spiralRange = document.querySelector("#spiral-progress");
const spiralPlay = document.querySelector("[data-spiral-play]");
const spiralCells = [];
const spiralPoints = makeSpiral(9);
const spiralText = [...spiralGrid.dataset.text];
for (let index = 0; index < 81; index += 1) {
  const cell = document.createElement("span");
  const [row, column] = spiralPoints[index];
  cell.textContent = spiralText[index % spiralText.length];
  cell.style.gridRow = row + 1;
  cell.style.gridColumn = column + 1;
  cell.dataset.step = index + 1;
  spiralGrid.append(cell);
  spiralCells.push(cell);
}

const paintSpiral = () => {
  const progress = Number(spiralRange.value);
  for (const cell of spiralCells) {
    const step = Number(cell.dataset.step);
    cell.classList.toggle("is-read", step <= progress);
    cell.classList.toggle("is-current", step === progress);
  }
};

let spiralTimer;
const stopSpiral = () => {
  window.clearInterval(spiralTimer);
  spiralTimer = undefined;
  spiralPlay.textContent = "开始循读";
};

spiralRange.addEventListener("input", () => {
  stopSpiral();
  paintSpiral();
});
spiralPlay.addEventListener("click", () => {
  if (spiralTimer) {
    stopSpiral();
    return;
  }
  if (Number(spiralRange.value) >= 81) spiralRange.value = 1;
  spiralPlay.textContent = "暂停循读";
  spiralTimer = window.setInterval(() => {
    spiralRange.value = Number(spiralRange.value) + 1;
    paintSpiral();
    if (Number(spiralRange.value) >= 81) stopSpiral();
  }, 110);
});
paintSpiral();

const xuantuGrid = document.querySelector("[data-xuantu-grid]");
const routeDefinitions = {
  row: {
    indices: [0, 1, 2, 3, 4, 5, 6, 7],
    text: "山雨来，客未归。",
  },
  column: {
    indices: [0, 8, 16, 24, 32, 40, 48, 56],
    text: "山外月，照空庭。",
  },
  diagonal: {
    indices: [0, 9, 18, 27, 36, 45, 54, 63],
    text: "山风起，月满楼。",
  },
};

const cellCharacters = Array(64).fill("");
for (const route of Object.values(routeDefinitions)) {
  for (const [offset, index] of route.indices.entries()) {
    const character = [...route.text][offset];
    if (cellCharacters[index] && cellCharacters[index] !== character) {
      throw new Error(`Conflicting characters at path cell ${index}`);
    }
    cellCharacters[index] = character;
  }
}

const xuantuCells = [];
for (const [index, character] of cellCharacters.entries()) {
  const cell = document.createElement("span");
  cell.textContent = character;
  xuantuGrid.append(cell);
  xuantuCells.push(cell);
}

const pathButtons = [...document.querySelectorAll("[data-path]")];
const pathOutput = document.querySelector("[data-path-output]");
const paintPath = (pathName) => {
  const route = routeDefinitions[pathName];
  const active = new Set(route.indices);
  for (const [index, cell] of xuantuCells.entries()) {
    cell.classList.toggle("is-active", active.has(index));
  }
  pathOutput.textContent = route.text;
};
for (const button of pathButtons) {
  button.addEventListener("click", () => {
    setPressed(pathButtons, button);
    paintPath(button.dataset.path);
  });
}
paintPath("row");

if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
  document.documentElement.classList.add("reduce-motion");
}
