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
      selected.setAttribute("aria-pressed", "false");
      origin = null;
      selected = null;
      announcement.textContent = "Selection cleared.";
      return;
    }
    const index = squares.indexOf(square);
    let next = index;
    if (event.key === "ArrowRight" && index % 8 < 7) next++;
    else if (event.key === "ArrowLeft" && index % 8 > 0) next--;
    else if (event.key === "ArrowDown" && index < 56) next += 8;
    else if (event.key === "ArrowUp" && index >= 8) next -= 8;
    else return;
    event.preventDefault();
    square.tabIndex = -1;
    squares[next].tabIndex = 0;
    squares[next].focus();
  });
})();
