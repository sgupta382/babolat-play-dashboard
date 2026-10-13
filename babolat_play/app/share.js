/* Milestone share cards: draw a 1080x1080 PNG, then use the native share sheet
   when the browser allows it (HTTPS/localhost), else show it to save. */
(function () {
  "use strict";
  var SIZE = 1080;

  function wrap(ctx, text, maxW) {
    var words = String(text).split(" "), lines = [], line = "";
    words.forEach(function (w) {
      var t = line ? line + " " + w : w;
      if (ctx.measureText(t).width > maxW && line) { lines.push(line); line = w; } else { line = t; }
    });
    if (line) lines.push(line);
    return lines;
  }

  function draw(card) {
    var c = document.createElement("canvas");
    c.width = c.height = SIZE;
    var ctx = c.getContext("2d");
    var font = 'system-ui, -apple-system, "Segoe UI", sans-serif';

    var g = ctx.createLinearGradient(0, 0, SIZE, SIZE);
    g.addColorStop(0, "#0e2a3b");
    g.addColorStop(1, "#164562");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, SIZE, SIZE);

    // tennis ball in the corner, with its seam
    var ball = ctx.createRadialGradient(860, 200, 20, 900, 230, 300);
    ball.addColorStop(0, "#e6ff6b");
    ball.addColorStop(0.6, "#d4f53c");
    ball.addColorStop(1, "#a9c51f");
    ctx.fillStyle = ball;
    ctx.beginPath(); ctx.arc(930, 170, 280, 0, Math.PI * 2); ctx.fill();
    ctx.strokeStyle = "rgba(255,255,255,.85)"; ctx.lineWidth = 10;
    ctx.beginPath(); ctx.arc(1180, 60, 300, Math.PI * 0.62, Math.PI * 1.08); ctx.stroke();

    // stroke-colored accent rail
    ctx.fillStyle = card.color || "#d4f53c";
    ctx.fillRect(80, 420, 12, 420);

    ctx.fillStyle = "#d4f53c";
    ctx.font = "800 34px " + font;
    ctx.fillText((card.kicker || "NEW MILESTONE").toUpperCase(), 80, 120);
    ctx.font = "96px " + font;
    ctx.fillText(card.icon || "🏆", 80, 250);

    ctx.fillStyle = "#ffffff";
    ctx.font = "700 64px " + font;
    wrap(ctx, card.title, 760).slice(0, 2).forEach(function (l, i) { ctx.fillText(l, 124, 480 + i * 74); });

    ctx.font = "800 220px " + font;
    ctx.fillStyle = "#d4f53c";
    var vy = 760;
    ctx.fillText(card.value, 116, vy);
    var vw = ctx.measureText(card.value).width;
    ctx.font = "700 60px " + font;
    ctx.fillStyle = "rgba(255,255,255,.85)";
    ctx.fillText(card.unit || "", 116 + vw + 18, vy);

    ctx.font = "40px " + font;
    ctx.fillStyle = "rgba(255,255,255,.8)";
    ctx.fillText(card.detail || "", 124, 830);

    ctx.fillStyle = "rgba(255,255,255,.14)";
    ctx.fillRect(80, 930, SIZE - 160, 2);
    ctx.font = "600 32px " + font;
    ctx.fillStyle = "rgba(255,255,255,.9)";
    ctx.fillText(card.date || "", 80, 990);
    ctx.textAlign = "right";
    ctx.fillStyle = "rgba(255,255,255,.6)";
    ctx.fillText("Babolat Play Dashboard", SIZE - 80, 990);
    return c;
  }

  function toBlob(canvas) {
    return new Promise(function (resolve) { canvas.toBlob(resolve, "image/png"); });
  }

  function showModal(canvas, name) {
    var url = canvas.toDataURL("image/png");
    document.getElementById("modalImg").src = url;
    var dl = document.getElementById("modalDownload");
    dl.href = url;
    dl.download = name;
    var m = document.getElementById("modal");
    m.hidden = false;
    document.getElementById("modalClose").focus();
  }

  function share(card) {
    var canvas = draw(card);
    var name = "milestone-" + (card.slug || "card") + ".png";
    return toBlob(canvas).then(function (blob) {
      var file = blob && window.File ? new File([blob], name, { type: "image/png" }) : null;
      if (file && navigator.canShare && navigator.canShare({ files: [file] })) {
        return navigator.share({ files: [file], title: card.title, text: card.shareText || card.title })
          .catch(function (e) { if (e && e.name !== "AbortError") showModal(canvas, name); });
      }
      showModal(canvas, name);
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    var m = document.getElementById("modal");
    if (!m) return;
    document.getElementById("modalClose").onclick = function () { m.hidden = true; };
    m.addEventListener("click", function (e) { if (e.target === m) m.hidden = true; });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") m.hidden = true; });
  });

  window.Share = { share: share, draw: draw };
})();
