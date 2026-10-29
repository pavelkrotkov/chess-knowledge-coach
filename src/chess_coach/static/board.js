(() => {
  const board = document.querySelector("[data-move-board]");
  const input = document.querySelector("#move");
  const announcement = document.querySelector("#board-announcement");
  const help = document.querySelector("[data-board-help]");
  if (!board || !input || !announcement) return;
  const squares = Array.from(board.querySelectorAll("button[data-square]"));
  if (squares.length !== 64) return;
  let origin = null;
  let selected = null;
  squares.forEach((square) => { square.hidden = false; });
  board.querySelectorAll("[data-square-static]").forEach((item) => { item.hidden = true; });
  squares[0].tabIndex = 0;
  if (help) help.hidden = false;
  function choose(square) {
    if (!origin) {
      origin = square.dataset.square;
      selected = square;
      square.setAttribute("aria-pressed", "true");
      announcement.textContent = "Selected " + origin + ". Choose a destination.";
      return;
    }
    input.value = origin + square.dataset.square;
    selected.setAttribute("aria-pressed", "false");
    announcement.textContent = "Move " + input.value + " selected. Choose promotion if needed, then play move.";
    origin = null;
    selected = null;
  }
  board.addEventListener("click", (event) => {
    const square = event.target.closest("button[data-square]");
    if (square && board.contains(square)) choose(square);
  });
  function clearSelection() {
    selected.setAttribute("aria-pressed", "false");
    origin = null;
    selected = null;
    announcement.textContent = "Selection cleared.";
  }
  function horizontalIndex(key, index) {
    if (key === "ArrowRight" && index % 8 < 7) return index + 1;
    if (key === "ArrowLeft" && index % 8 > 0) return index - 1;
    return null;
  }
  function nextIndex(key, index) {
    if (key === "ArrowDown" && index < 56) return index + 8;
    if (key === "ArrowUp" && index >= 8) return index - 8;
    return horizontalIndex(key, index);
  }
  function navigate(event, square) {
    const next = nextIndex(event.key, squares.indexOf(square));
    if (next === null) return;
    event.preventDefault();
    square.tabIndex = -1;
    squares[next].tabIndex = 0;
    squares[next].focus();
  }
  board.addEventListener("keydown", (event) => {
    const square = event.target.closest("button[data-square]");
    if (!square) return;
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      choose(square);
      return;
    }
    if (event.key === "Escape" && selected) {
      event.preventDefault();
      clearSelection();
      return;
    }
    navigate(event, square);
  });
})();
