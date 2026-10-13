/* Small SVG chart kit: line + (stacked) bar, with hover/tap tooltip and a table view.
   Colors are CSS custom property names (e.g. "--serve") resolved at draw time, so
   charts follow the light/dark theme. */
(function () {
  "use strict";
  var NS = "http://www.w3.org/2000/svg";

  function cssVar(name) {
    return name && name.indexOf("--") === 0
      ? getComputedStyle(document.documentElement).getPropertyValue(name).trim() : name;
  }
  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function niceTicks(min, max, count) {
    if (max === min) { max = min + 1; }
    var raw = (max - min) / count;
    var mag = Math.pow(10, Math.floor(Math.log10(raw)));
    var n = raw / mag;
    var step = (n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10) * mag;
    var lo = Math.floor(min / step) * step, hi = Math.ceil(max / step) * step, out = [];
    for (var v = lo; v <= hi + step / 2; v += step) out.push(+v.toFixed(6));
    return out;
  }
  function el(tag, attrs) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    return e;
  }
  function roundedTop(x, y, w, h, r) {
    r = Math.min(r, w / 2, h);
    return "M" + x + "," + (y + h) + "V" + (y + r) + "Q" + x + "," + y + " " + (x + r) + "," + y +
      "H" + (x + w - r) + "Q" + (x + w) + "," + y + " " + (x + w) + "," + (y + r) + "V" + (y + h) + "Z";
  }

  /* Shared shell: legend, plot, tooltip, table toggle, resize handling. */
  function mount(host, cfg, draw) {
    host.classList.add("chart");
    var legend = cfg.series.length > 1
      ? '<div class="chart-legend">' + cfg.series.map(function (s) {
          var cls = cfg.kind === "bar" ? "sq" : s.dashed ? "dash" : "";
          var style = cfg.kind === "bar" ? "background:var(" + s.color + ")" : "border-color:var(" + s.color + ")";
          return '<span><i class="' + cls + '" style="' + style + '"></i>' + esc(s.label) + "</span>";
        }).join("") + "</div>" : "";
    host.innerHTML = legend + '<div class="chart-plot"></div><div class="chart-table" hidden></div>' +
      '<div class="chart-tip" hidden></div><div class="chart-foot"><button type="button" class="link">Show table</button></div>';
    var plot = host.querySelector(".chart-plot"), tip = host.querySelector(".chart-tip");
    var table = host.querySelector(".chart-table"), toggle = host.querySelector(".chart-foot button");
    toggle.onclick = function () {
      var showTable = table.hidden;
      table.hidden = !showTable; plot.hidden = showTable;
      toggle.textContent = showTable ? "Show chart" : "Show table";
      if (showTable) table.innerHTML = tableHtml(cfg);
    };
    var lastW = 0;
    function render() {
      var w = Math.round(plot.clientWidth);
      if (!w || w === lastW) return;
      lastW = w;
      draw(plot, w, tip);
    }
    render();
    if (window.ResizeObserver) {
      var ro = new ResizeObserver(render);
      ro.observe(plot);
    } else {
      window.addEventListener("resize", render);
    }
  }

  function tableHtml(cfg) {
    var fmt = cfg.format || String;
    return "<table><thead><tr><th>" + esc(cfg.xLabel || "") + "</th>" +
      cfg.series.map(function (s) { return "<th>" + esc(s.label) + "</th>"; }).join("") + "</tr></thead><tbody>" +
      cfg.labels.map(function (l, i) {
        return "<tr><td>" + esc(l) + "</td>" + cfg.series.map(function (s) {
          return "<td>" + (s.values[i] == null ? "–" : esc(fmt(s.values[i]))) + "</td>";
        }).join("") + "</tr>";
      }).join("") + "</tbody></table>";
  }

  function axes(svg, o) {
    o.ticks.forEach(function (v, i) {
      var y = o.y(v);
      svg.appendChild(el("line", { x1: o.L, x2: o.W - o.R, y1: y, y2: y,
        stroke: cssVar(i === 0 ? "--axis" : "--grid"), "stroke-width": 1 }));
      var t = el("text", { x: o.L - 6, y: y + 4, "text-anchor": "end" });
      t.textContent = o.tickFmt(v);
      svg.appendChild(t);
    });
    // x labels: keep first and last, add evenly spaced ones only where they fit
    var n = o.labels.length, CH = 6.5, GAP = 10, placed = [];
    function span(i) {
      var w = String(o.labels[i]).length * CH, cx = o.x(i);
      var anchor = n === 1 ? "middle" : i === 0 ? "start" : i === n - 1 ? "end" : "middle";
      var left = anchor === "start" ? cx : anchor === "end" ? cx - w : cx - w / 2;
      return { i: i, left: left, right: left + w, anchor: anchor };
    }
    var first = span(0), lastS = n > 1 ? span(n - 1) : null;
    placed.push(first);
    if (lastS && lastS.left - first.right >= GAP) placed.push(lastS);
    var every = Math.max(1, Math.ceil(n / Math.max(2, Math.floor((o.W - o.L - o.R) / 64))));
    for (var i = every; i < n - 1; i += every) {
      var c = span(i);
      if (placed.every(function (p) { return c.left - p.right >= GAP || p.left - c.right >= GAP; })) placed.push(c);
    }
    placed.forEach(function (p) {
      var t = el("text", { x: o.x(p.i), y: o.H - 6, "text-anchor": p.anchor });
      t.textContent = o.labels[p.i];
      svg.appendChild(t);
    });
  }

  function placeTip(tip, plot, x, html) {
    tip.innerHTML = html;
    tip.hidden = false;
    var pw = plot.clientWidth, tw = tip.offsetWidth;
    var left = x + 14 + tw > pw ? x - tw - 14 : x + 14;
    tip.style.left = Math.max(0, left) + "px";
    tip.style.top = (plot.offsetTop + 8) + "px";
  }

  function tipRows(cfg, i) {
    var fmt = cfg.format || String;
    return "<b>" + esc(cfg.tipLabels ? cfg.tipLabels[i] : cfg.labels[i]) + "</b>" +
      cfg.series.map(function (s) {
        var v = s.values[i];
        return '<div class="row"><i class="dot" style="background:var(' + s.color + ')"></i><span>' + esc(s.label) +
          "</span><span>" + (v == null ? "–" : esc(fmt(v))) + "</span></div>";
      }).join("") + (cfg.tipTotal ? '<div class="row"><span>Total</span><span>' +
        esc(fmt(cfg.series.reduce(function (a, s) { return a + (s.values[i] || 0); }, 0))) + "</span></div>" : "");
  }

  function hover(svg, tip, o, onMove) {
    var hit = el("rect", { x: o.L, y: o.T, width: Math.max(0, o.W - o.L - o.R), height: o.H - o.T - o.B, fill: "transparent" });
    svg.appendChild(hit);
    function at(evt) {
      var r = svg.getBoundingClientRect();
      var px = (evt.clientX - r.left) * (o.W / r.width);
      onMove(Math.max(0, Math.min(o.n - 1, o.index(px))));
    }
    hit.style.touchAction = "pan-y"; // horizontal scrub on the chart, vertical page scroll
    hit.addEventListener("pointermove", at);
    hit.addEventListener("pointerdown", at);
    // Touch fires pointerleave right after the finger lifts; only a mouse leaving hides the tip.
    // Touch tips close when the user taps elsewhere (document listener below).
    hit.addEventListener("pointerleave", function (e) {
      if (e.pointerType === "mouse") { tip.hidden = true; onMove(-1); }
    });
  }

  function lineChart(host, cfg) {
    cfg.kind = "line";
    mount(host, cfg, function (plot, W, tip) {
      var H = cfg.height || 190, L = 34, R = 40, T = 10, B = 24, n = cfg.labels.length;
      var all = [];
      cfg.series.forEach(function (s) { s.values.forEach(function (v) { if (v != null) all.push(v); }); });
      if (!all.length) { plot.innerHTML = '<p class="muted small">No data in this range.</p>'; return; }
      var lo = Math.min.apply(null, all), hi = Math.max.apply(null, all);
      var pad = (hi - lo) * 0.15 || hi * 0.1 || 1;
      var ticks = niceTicks(cfg.min0 ? 0 : Math.max(0, lo - pad), hi + pad / 2, 4);
      var y = function (v) { return T + (H - T - B) * (1 - (v - ticks[0]) / (ticks[ticks.length - 1] - ticks[0])); };
      var span = W - L - R;
      var x = function (i) { return n === 1 ? L + span / 2 : L + i * span / (n - 1); };
      var o = { W: W, H: H, L: L, R: R, T: T, B: B, n: n, ticks: ticks, y: y, x: x, labels: cfg.labels,
        tickFmt: cfg.tickFormat || function (v) { return Math.round(v); },
        index: function (px) { return n === 1 ? 0 : Math.round((px - L) / (span / (n - 1))); } };
      var svg = el("svg", { viewBox: "0 0 " + W + " " + H, width: W, height: H, role: "img",
        "aria-label": cfg.ariaLabel || "Line chart" });
      axes(svg, o);
      var cross = el("line", { y1: T, y2: H - B, stroke: cssVar("--axis"), "stroke-width": 1, visibility: "hidden" });
      svg.appendChild(cross);
      var dots = [], ends = [];
      cfg.series.forEach(function (s) {
        var color = cssVar(s.color), d = "", pen = false;
        s.values.forEach(function (v, i) {
          if (v == null) { pen = false; return; }
          d += (pen ? "L" : "M") + x(i).toFixed(1) + "," + y(v).toFixed(1);
          pen = true;
        });
        svg.appendChild(el("path", { d: d, fill: "none", stroke: color, "stroke-width": 2,
          "stroke-linejoin": "round", "stroke-linecap": "round", "stroke-dasharray": s.dashed ? "5 4" : "none",
          opacity: s.dashed ? 0.8 : 1 }));
        var showAll = n <= 16;
        var lastI = -1;
        s.values.forEach(function (v, i) { if (v != null) lastI = i; });
        var sd = [];
        s.values.forEach(function (v, i) {
          if (v == null) return;
          var c = el("circle", { cx: x(i), cy: y(v), r: 4, fill: s.dashed ? cssVar("--surface") : color,
            stroke: s.dashed ? color : cssVar("--surface"), "stroke-width": 2,
            visibility: showAll || i === lastI ? "visible" : "hidden" });
          svg.appendChild(c);
          sd[i] = c;
        });
        dots.push(sd);
        if (lastI >= 0) ends.push({ y: y(s.values[lastI]), x: x(lastI), text: (cfg.endFormat || cfg.tickFormat || cfg.format || String)(s.values[lastI]) });
      });
      // direct end labels, nudged apart so they never collide
      ends.sort(function (a, b) { return a.y - b.y; });
      for (var i = 1; i < ends.length; i++) if (ends[i].y - ends[i - 1].y < 13) ends[i].y = ends[i - 1].y + 13;
      ends.forEach(function (e) {
        var t = el("text", { x: e.x + 8, y: e.y + 4, class: "end" });
        t.textContent = e.text;
        svg.appendChild(t);
      });
      plot.innerHTML = "";
      plot.appendChild(svg);
      hover(svg, tip, o, function (i) {
        dots.forEach(function (sd) { sd.forEach(function (c, j) { if (c) c.setAttribute("r", j === i ? 6 : 4); }); });
        if (i < 0) { cross.setAttribute("visibility", "hidden"); return; }
        cross.setAttribute("x1", x(i)); cross.setAttribute("x2", x(i)); cross.setAttribute("visibility", "visible");
        placeTip(tip, plot, x(i), tipRows(cfg, i));
      });
    });
  }

  function barChart(host, cfg) {
    cfg.kind = "bar";
    mount(host, cfg, function (plot, W, tip) {
      var H = cfg.height || 190, L = 34, R = 8, T = 10, B = 24, n = cfg.labels.length;
      if (!n) { plot.innerHTML = '<p class="muted small">No data in this range.</p>'; return; }
      var sums = cfg.labels.map(function (_, i) {
        return cfg.series.reduce(function (a, s) { return a + (s.values[i] || 0); }, 0);
      });
      var ticks = niceTicks(0, Math.max.apply(null, sums.concat([1])), 4);
      var y = function (v) { return T + (H - T - B) * (1 - v / ticks[ticks.length - 1]); };
      var band = (W - L - R) / n, bw = Math.max(2, Math.min(band * 0.72, 40));
      var x = function (i) { return L + band * i + band / 2; };
      var o = { W: W, H: H, L: L, R: R, T: T, B: B, n: n, ticks: ticks, y: y, x: x, labels: cfg.labels,
        tickFmt: cfg.tickFormat || function (v) { return Math.round(v); },
        index: function (px) { return Math.floor((px - L) / band); } };
      var svg = el("svg", { viewBox: "0 0 " + W + " " + H, width: W, height: H, role: "img",
        "aria-label": cfg.ariaLabel || "Bar chart" });
      var hl = el("rect", { y: T, height: H - T - B, width: band, fill: cssVar("--surface-2"), visibility: "hidden" });
      svg.appendChild(hl);
      axes(svg, o);
      var surface = cssVar("--surface");
      cfg.labels.forEach(function (_, i) {
        var acc = 0, segs = [];
        cfg.series.forEach(function (s) { if (s.values[i]) segs.push(s); });
        segs.forEach(function (s, k) {
          var v = s.values[i], y0 = y(acc + v), y1 = y(acc);
          acc += v;
          var top = k === segs.length - 1;
          var shape = top
            ? el("path", { d: roundedTop(x(i) - bw / 2, y0, bw, y1 - y0, 4) })
            : el("rect", { x: x(i) - bw / 2, y: y0, width: bw, height: Math.max(0, y1 - y0) });
          shape.setAttribute("fill", cssVar(s.color));
          shape.setAttribute("stroke", surface);
          shape.setAttribute("stroke-width", segs.length > 1 ? 1 : 0); // 2px visual gap between stacked fills
          svg.appendChild(shape);
        });
      });
      plot.innerHTML = "";
      plot.appendChild(svg);
      hover(svg, tip, o, function (i) {
        if (i < 0) { hl.setAttribute("visibility", "hidden"); return; }
        hl.setAttribute("x", L + band * i); hl.setAttribute("visibility", "visible");
        placeTip(tip, plot, x(i), tipRows(cfg, i));
      });
    });
  }

  document.addEventListener("pointerdown", function (e) {
    document.querySelectorAll(".chart").forEach(function (c) {
      if (!c.contains(e.target)) { var t = c.querySelector(".chart-tip"); if (t) t.hidden = true; }
    });
  });

  window.Charts = { lineChart: lineChart, barChart: barChart, niceTicks: niceTicks };
})();
