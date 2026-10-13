/* Play Dashboard app: hash-routed views over window.PLAY_DATA (written by `python3 -m babolat_play`). */
(function () {
  "use strict";

  var DATA = window.PLAY_DATA || { sessions: [], milestones: [], demo: null, latest_import_id: null };
  var REPO = "https://github.com/sgupta382/babolat-play-dashboard";
  var STROKES = [
    { key: "forehand", label: "Forehand" },
    { key: "backhand", label: "Backhand" },
    { key: "serve", label: "Serve" },
    { key: "volley", label: "Volley" }
  ];
  var SPINS = ["topspin", "slice", "flat"];
  var KMH_PER_MPH = 1.609344;
  var view = document.getElementById("view");

  // ---- prefs (per-viewer conveniences only; the page works without storage) ----
  var prefs = {
    get: function (k, d) { try { var v = localStorage.getItem("bp." + k); return v === null ? d : v; } catch (e) { return d; } },
    set: function (k, v) { try { localStorage.setItem("bp." + k, v); } catch (e) { /* private mode */ } }
  };
  var state = { unit: prefs.get("unit", "mph"), period: prefs.get("period", "10") };

  // ---- formatting ----
  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function speed(kmh) { return kmh == null ? null : state.unit === "mph" ? kmh / KMH_PER_MPH : kmh; }
  function unit() { return state.unit === "mph" ? "mph" : "km/h"; }
  function num(v) { return v == null || isNaN(v) ? "–" : Math.round(v).toLocaleString(); }
  function pct(n, d) { return d ? Math.round(100 * n / d) : 0; }
  var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  var DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  function parseLocal(iso) { // "2022-08-29T19:17:33" -> local Date (no timezone shift)
    var p = iso.split(/[-T:]/).map(Number);
    return new Date(p[0], p[1] - 1, p[2], p[3] || 0, p[4] || 0, p[5] || 0);
  }
  function dShort(d) { return MONTHS[d.getMonth()] + " " + d.getDate(); }
  function dLong(d) { return DAYS[d.getDay()] + ", " + MONTHS[d.getMonth()] + " " + d.getDate() + ", " + d.getFullYear(); }
  function tOfDay(d) { var h = d.getHours(), m = d.getMinutes(); return (h % 12 || 12) + ":" + (m < 10 ? "0" : "") + m + (h < 12 ? " am" : " pm"); }
  function dur(s) { var m = Math.round(s / 60); return m >= 60 ? Math.floor(m / 60) + " h " + (m % 60) + " min" : m + " min"; }
  function mean(a) { return a.length ? a.reduce(function (x, y) { return x + y; }, 0) / a.length : null; }
  function max(a) { return a.length ? Math.max.apply(null, a) : null; }

  // ---- model ----
  function summarize(s) {
    var by = {};
    STROKES.forEach(function (c) { by[c.key] = { n: 0, speeds: [], spin: { topspin: 0, slice: 0, flat: 0 } }; });
    s.swings.forEach(function (w) {
      var b = by[w[1]];
      if (!b) return;
      b.n++;
      if (w[3]) b.speeds.push(w[3]);
      if (b.spin[w[2]] != null) b.spin[w[2]]++;
    });
    STROKES.forEach(function (c) { var b = by[c.key]; b.avg = mean(b.speeds); b.max = max(b.speeds); });
    return { id: s.id, date: parseLocal(s.started_at), duration: s.duration_s, shots: s.swings.length,
      by: by, source: s.source, swings: s.swings };
  }
  var SESSIONS = DATA.sessions.map(summarize).sort(function (a, b) { return a.date - b.date; });
  var BY_ID = {};
  SESSIONS.forEach(function (s) { BY_ID[s.id] = s; });
  var MILESTONES = DATA.milestones.filter(function (m) { return m.key !== "sessions_1"; })
    .sort(function (a, b) { return a.achieved_at < b.achieved_at ? -1 : a.achieved_at > b.achieved_at ? 1 : 0; });

  function newMilestones() { // newest first, so the latest records lead the banner
    return MILESTONES.filter(function (m) { return m.is_new; }).reverse();
  }
  function bestOf(stroke) {
    var best = null;
    SESSIONS.forEach(function (s) { var m = s.by[stroke].max; if (m != null && (!best || m > best.v)) best = { v: m, s: s }; });
    return best;
  }
  function windowAvg(list, fn) {
    var vals = list.map(fn).filter(function (v) { return v != null; });
    return mean(vals);
  }

  // ---- milestone presentation ----
  function msKind(m) {
    if (m.key.indexOf("pb_") === 0) return { icon: "🏆", kicker: "Personal best" };
    if (m.key.indexOf("shots_") === 0) return { icon: "🎯", kicker: "Milestone" };
    if (m.key.indexOf("streak_") === 0) return { icon: "🔥", kicker: "Streak" };
    return { icon: "🎾", kicker: "Milestone" };
  }
  function msValue(m) {
    if (m.key.indexOf("pb_topspin") === 0) return [Math.round(m.value) + "%", "topspin"];
    if (m.key.indexOf("pb_shots") === 0 || m.key.indexOf("shots_") === 0) return [num(m.value), "shots"];
    if (m.key.indexOf("pb_") === 0 && m.stroke) return [num(speed(m.value)), unit()];
    if (m.key.indexOf("streak_") === 0) return [num(m.value), "weeks"];
    if (m.key.indexOf("sessions_") === 0) return [num(m.value), "sessions"];
    return ["", ""];
  }
  function shareMs(m) {
    var v = msValue(m), k = msKind(m);
    var color = m.stroke ? getComputedStyle(document.documentElement).getPropertyValue("--" + m.stroke).trim() : "#d4f53c";
    window.Share.share({
      title: m.title, value: v[0] || k.icon, unit: v[0] ? v[1] : "", detail: m.detail,
      date: dLong(parseLocal(m.achieved_at)), icon: k.icon, kicker: k.kicker, color: color, slug: m.key.replace(/[^a-z0-9]+/gi, "-"),
      shareText: k.icon + " " + m.title + (v[0] ? ": " + v[0] + " " + v[1] : "") + " 🎾"
    });
  }
  var SHARE_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 12v7a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-7"/><path d="M12 3v12M7 8l5-5 5 5"/></svg>';
  function msRow(m, i) {
    var v = msValue(m), k = msKind(m);
    var d = parseLocal(m.achieved_at);
    return '<div class="ms-icon" aria-hidden="true">' + k.icon + '</div><div class="t"><div class="ms-title">' + esc(m.title) +
      (m.is_new ? ' <span class="new-pill">NEW</span>' : "") + "</div>" +
      (v[0] ? '<div class="ms-val tnum">' + esc(v[0]) + "<small>" + esc(v[1]) + "</small></div>" : "") +
      '<div class="ms-meta">' + esc(m.detail) + " · " + dShort(d) + ", " + d.getFullYear() + "</div></div>" +
      '<button type="button" class="btn sm ghost" data-share="' + i + '" aria-label="Share ' + esc(m.title) + '">' + SHARE_ICON + "</button>";
  }
  function wireShare(root, list) {
    root.querySelectorAll("[data-share]").forEach(function (b) {
      b.onclick = function () { shareMs(list[+b.getAttribute("data-share")]); };
    });
  }

  // ---- shared fragments ----
  function mixBar(s) {
    return '<div class="mix" role="img" aria-label="Stroke mix">' + STROKES.map(function (c) {
      var n = s.by[c.key].n;
      return n ? '<span style="flex:' + n + ';background:var(--' + c.key + ')" title="' + c.label + ": " + n + '"></span>' : "";
    }).join("") + "</div>";
  }
  function mixLegend(s) {
    return '<div class="mix-legend">' + STROKES.map(function (c) {
      return '<span><i class="dot" style="background:var(--' + c.key + ')"></i>' + c.label + " " +
        s.by[c.key].n + " · " + pct(s.by[c.key].n, s.shots) + "%</span>";
    }).join("") + "</div>";
  }
  function strokeCard(c, b, total) {
    return '<div class="card stroke-card"><h3><i class="dot" style="background:var(--' + c.key + ')"></i>' + c.label + "</h3>" +
      '<div class="nums tnum"><div><div class="n">' + b.n + '</div><div class="l">' + pct(b.n, total) + "% of shots</div></div>" +
      '<div><div class="n">' + num(speed(b.avg)) + '</div><div class="l">avg ' + unit() + "</div></div>" +
      '<div><div class="n">' + num(speed(b.max)) + '</div><div class="l">max ' + unit() + "</div></div></div>" +
      SPINS.map(function (sp) {
        var p = pct(b.spin[sp], b.n);
        return '<div class="spinrow"><span>' + sp[0].toUpperCase() + sp.slice(1) + '</span><div class="track"><div class="fill" style="width:' +
          p + "%;background:var(--" + c.key + ')"></div></div><span class="tnum">' + p + "% (" + b.spin[sp] + ")</span></div>";
      }).join("") + "</div>";
  }
  function delta(curr, prev, digits) {
    if (curr == null || prev == null) return '<span class="muted">needs 2+ sessions</span>';
    var d = curr - prev, r = Math.round(d * Math.pow(10, digits || 0)) / Math.pow(10, digits || 0);
    if (r === 0) return '<span class="delta">→ no change</span>';
    return '<span class="delta ' + (r > 0 ? "up" : "down") + '">' + (r > 0 ? "▲ " : "▼ ") + Math.abs(r).toLocaleString() + "</span>";
  }

  // ---- views ----
  function empty() {
    return '<div class="card empty"><div class="ball"></div><h2>No sessions yet</h2>' +
      '<p class="muted">Plug your Babolat Play racket into this Mac. New sessions are imported automatically.<br>' +
      "Or run <code>python3 -m babolat_play import</code>.</p></div>";
  }

  function overview() {
    if (!SESSIONS.length) return empty();
    var last = SESSIONS[SESSIONS.length - 1];
    var fresh = newMilestones();
    var dismissed = prefs.get("dismissed", "") === String(DATA.latest_import_id);
    var html = "";

    html += '<section class="hero"><div class="eyebrow">Latest session</div><h1>' + dLong(last.date) + "</h1>" +
      '<div class="meta">' + tOfDay(last.date) + " · " + dur(last.duration) + " · " + last.shots + " shots</div>" +
      '<div class="hero-stats tnum">' +
      heroStat("Shots", last.shots, "", null) +
      heroStat("Top serve", num(speed(last.by.serve.max)), unit(), "serve") +
      heroStat("Top forehand", num(speed(last.by.forehand.max)), unit(), "forehand") +
      heroStat("Top backhand", num(speed(last.by.backhand.max)), unit(), "backhand") +
      '</div><div class="btn-row"><a class="btn ball sm" href="#session/' + encodeURIComponent(last.id) + '">Session details</a></div></section>';

    if (fresh.length && !dismissed) {
      html += '<section class="banner" aria-live="polite"><button type="button" class="x" id="dismiss" aria-label="Dismiss">×</button>' +
        "<h2>🎉 " + fresh.length + " new milestone" + (fresh.length > 1 ? "s" : "") + " — share the moment!</h2><ul>" +
        fresh.slice(0, 3).map(function (m, i) { return "<li>" + msRow(m, i) + "</li>"; }).join("") + "</ul>" +
        (fresh.length > 3 ? '<p class="small" style="margin:8px 0 0"><a href="#milestones">See all ' + fresh.length + " →</a></p>" : "") +
        "</section>";
    }

    var last5 = SESSIONS.slice(-5), prev5 = SESSIONS.slice(-10, -5);
    var totalShots = SESSIONS.reduce(function (a, s) { return a + s.shots; }, 0);
    var totalTime = SESSIONS.reduce(function (a, s) { return a + s.duration; }, 0);
    var bs = bestOf("serve"), bf = bestOf("forehand");
    var avgServe = function (l) { return windowAvg(l, function (s) { return speed(s.by.serve.avg); }); };
    var perSession = function (l) { return windowAvg(l, function (s) { return s.shots; }); };
    html += '<div class="section-title"><h2>All time</h2><span class="small muted">changes compare your last 5 sessions with the 5 before</span></div>';
    html += '<section class="grid cols-3">' +
      tile("Sessions", SESSIONS.length, "", dur(totalTime) + " on court") +
      tile("Total shots", num(totalShots), "", "avg " + num(totalShots / SESSIONS.length) + " per session") +
      tile("Fastest serve", num(bs && speed(bs.v)), unit(), bs ? "on " + dShort(bs.s.date) + ", " + bs.s.date.getFullYear() : "", "serve") +
      tile("Fastest forehand", num(bf && speed(bf.v)), unit(), bf ? "on " + dShort(bf.s.date) + ", " + bf.s.date.getFullYear() : "", "forehand") +
      tile("Avg serve · last 5", num(avgServe(last5)), unit(), delta(avgServe(last5), prev5.length ? avgServe(prev5) : null) + " " + unit(), "serve", true) +
      tile("Shots per session · last 5", num(perSession(last5)), "", delta(perSession(last5), prev5.length ? perSession(prev5) : null) + " shots", null, true) +
      "</section>";

    html += '<section class="card"><div class="card-head"><h2>Latest session stroke mix</h2><span class="small muted">' + last.shots + " shots</span></div>" +
      mixBar(last) + mixLegend(last) + "</section>";

    html += '<div class="section-title"><h2>Recent sessions</h2><a class="small muted" href="#sessions">All sessions →</a></div>' +
      '<section class="stack">' + SESSIONS.slice(-3).reverse().map(sessionRow).join("") + "</section>";
    return html;
  }
  function heroStat(k, v, u, stroke) {
    return '<div class="hero-stat"><div class="k">' + (stroke ? '<i class="dot" style="background:var(--' + stroke + ')"></i>' : "") + k +
      '</div><div class="v">' + v + (u ? "<small>" + u + "</small>" : "") + "</div></div>";
  }
  function tile(k, v, u, sub, stroke, rawSub) {
    return '<div class="card tile"><div class="k">' + (stroke ? '<i class="dot" style="background:var(--' + stroke + ')"></i>' : "") + esc(k) +
      '</div><div class="v tnum">' + v + (u ? "<small>" + u + "</small>" : "") + '</div><div class="sub">' + (rawSub ? sub : esc(sub)) + "</div></div>";
  }
  function sessionRow(s) {
    return '<a class="card session-row" href="#session/' + encodeURIComponent(s.id) + '"><div class="when"><b>' + dLong(s.date) +
      '</b><span class="small muted">' + tOfDay(s.date) + " · " + dur(s.duration) + (s.source === "synthetic" ? " · synthetic" : "") +
      '</span></div><div class="stats tnum"><b>' + s.shots + " shots</b>serve " + num(speed(s.by.serve.max)) + " " + unit() + "</div>" + mixBar(s) + "</a>";
  }

  function trends() {
    if (!SESSIONS.length) return empty();
    var periods = [["5", "Last 5"], ["10", "Last 10"], ["all", "All"]];
    var html = '<div class="chips" role="group" aria-label="Period">' + periods.map(function (p) {
      return '<button type="button" class="chip" data-period="' + p[0] + '" aria-pressed="' + (state.period === p[0]) + '">' + p[1] + "</button>";
    }).join("") + "</div>";
    html += '<div class="section-title"><h2>Speed</h2><span class="small muted">avg (solid) and max (dashed) per session, ' + unit() + "</span></div>" +
      '<section class="grid charts">' + ["serve", "forehand", "backhand"].map(function (k) {
        return '<div class="card"><div class="card-head"><h3><i class="dot" style="background:var(--' + k + ')"></i> ' +
          k[0].toUpperCase() + k.slice(1) + '</h3></div><div id="speed-' + k + '"></div></div>';
      }).join("") + "</section>";
    html += '<section class="grid cols-2w">' +
      '<div class="card"><div class="card-head"><h2>Shot mix</h2><span class="small muted">shots per session</span></div><div id="mix"></div></div>' +
      '<div class="card"><div class="card-head"><h2>Volume</h2><span class="small muted">total shots per session</span></div><div id="volume"></div></div></section>';
    html += '<div class="section-title"><h2>Spin</h2><span class="small muted">share of strokes per session</span></div><section class="grid cols-2w">' +
      '<div class="card"><div class="card-head"><h3><i class="dot" style="background:var(--forehand)"></i> Forehand topspin</h3></div><div id="spin-fh"></div></div>' +
      '<div class="card"><div class="card-head"><h3><i class="dot" style="background:var(--backhand)"></i> Backhand slice</h3></div><div id="spin-bh"></div></div></section>';
    return html;
  }
  function drawTrends() {
    var list = state.period === "all" ? SESSIONS : SESSIONS.slice(-Number(state.period));
    var labels = list.map(function (s) { return dShort(s.date); });
    var tipLabels = list.map(function (s) { return dLong(s.date); });
    var spd = function (v) { return num(v) + " " + unit(); };
    ["serve", "forehand", "backhand"].forEach(function (k) {
      window.Charts.lineChart(document.getElementById("speed-" + k), {
        labels: labels, tipLabels: tipLabels, xLabel: "Session", format: spd, tickFormat: num, ariaLabel: k + " speed per session",
        series: [
          { label: "Avg", color: "--" + k, values: list.map(function (s) { return speed(s.by[k].avg); }) },
          { label: "Max", color: "--" + k, dashed: true, values: list.map(function (s) { return speed(s.by[k].max); }) }
        ]
      });
    });
    window.Charts.barChart(document.getElementById("mix"), {
      labels: labels, tipLabels: tipLabels, xLabel: "Session", tipTotal: true, format: num, ariaLabel: "Shot mix per session",
      series: STROKES.map(function (c) { return { label: c.label, color: "--" + c.key, values: list.map(function (s) { return s.by[c.key].n; }) }; })
    });
    window.Charts.barChart(document.getElementById("volume"), {
      labels: labels, tipLabels: tipLabels, xLabel: "Session", format: num, ariaLabel: "Shots per session",
      series: [{ label: "Shots", color: "--forehand", values: list.map(function (s) { return s.shots; }) }]
    });
    var pctFmt = function (v) { return Math.round(v) + "%"; };
    window.Charts.lineChart(document.getElementById("spin-fh"), {
      labels: labels, tipLabels: tipLabels, xLabel: "Session", format: pctFmt, tickFormat: pctFmt, height: 170, ariaLabel: "Forehand topspin share",
      series: [{ label: "Topspin", color: "--forehand", values: list.map(function (s) { var b = s.by.forehand; return b.n ? 100 * b.spin.topspin / b.n : null; }) }]
    });
    window.Charts.lineChart(document.getElementById("spin-bh"), {
      labels: labels, tipLabels: tipLabels, xLabel: "Session", format: pctFmt, tickFormat: pctFmt, height: 170, ariaLabel: "Backhand slice share",
      series: [{ label: "Slice", color: "--backhand", values: list.map(function (s) { var b = s.by.backhand; return b.n ? 100 * b.spin.slice / b.n : null; }) }]
    });
  }

  function sessions() {
    if (!SESSIONS.length) return empty();
    return '<div class="section-title"><h2>' + SESSIONS.length + " sessions</h2></div>" +
      '<section class="stack">' + SESSIONS.slice().reverse().map(sessionRow).join("") + "</section>";
  }

  function sessionDetail(id) {
    var s = BY_ID[id];
    if (!s) return '<a class="back" href="#sessions">← Sessions</a><div class="card empty"><h2>Session not found</h2></div>';
    var html = '<a class="back" href="#sessions">← Sessions</a>' +
      '<section class="hero"><div class="eyebrow">Session' + (s.source === "synthetic" ? " · synthetic demo" : "") + "</div><h1>" + dLong(s.date) + "</h1>" +
      '<div class="meta">' + tOfDay(s.date) + " · " + dur(s.duration) + " · " + s.shots + " shots</div></section>";
    html += '<section class="grid cols-4">' + STROKES.map(function (c) { return strokeCard(c, s.by[c.key], s.shots); }).join("") + "</section>";
    html += '<section class="card"><div class="card-head"><h2>Shots over the session</h2><span class="small muted">5-minute bins</span></div><div id="timeline"></div></section>';
    html += '<section class="card"><details><summary>All ' + s.shots + ' swings</summary><div class="scroll" style="margin-top:8px"><table><thead><tr>' +
      "<th>#</th><th>Time</th><th>Stroke</th><th>Spin</th><th>Speed (" + unit() + ")</th></tr></thead><tbody>" +
      s.swings.map(function (w, i) {
        return "<tr><td>" + (i + 1) + "</td><td>" + (w[4] ? "⚠ clock glitch" : Math.floor(w[0] / 60) + ":" + ("0" + (w[0] % 60)).slice(-2)) +
          "</td><td>" + esc(w[1]) + "</td><td>" + esc(w[2]) + "</td><td>" + num(speed(w[3])) + "</td></tr>";
      }).join("") + "</tbody></table></div></details></section>";
    return html;
  }
  function drawTimeline(id) {
    var s = BY_ID[id];
    if (!s) return;
    var timed = s.swings.filter(function (w) { return !w[4]; });
    var bins = Math.max(1, Math.floor(Math.max.apply(null, timed.map(function (w) { return w[0]; }).concat([0])) / 300) + 1);
    var labels = [], tipLabels = [];
    for (var i = 0; i < bins; i++) { labels.push(i * 5 + "′"); tipLabels.push(i * 5 + "–" + (i * 5 + 5) + " min"); }
    window.Charts.barChart(document.getElementById("timeline"), {
      labels: labels, tipLabels: tipLabels, xLabel: "Minute", tipTotal: true, format: num, ariaLabel: "Shots per 5 minutes",
      series: STROKES.map(function (c) {
        var v = labels.map(function () { return 0; });
        timed.forEach(function (w) { if (w[1] === c.key) v[Math.floor(w[0] / 300)]++; });
        return { label: c.label, color: "--" + c.key, values: v };
      })
    });
  }

  function milestones() {
    if (!MILESTONES.length) return SESSIONS.length ? '<div class="card empty"><h2>No milestones yet</h2><p class="muted">Keep playing!</p></div>' : empty();
    var list = MILESTONES.slice().reverse(), html = "", month = "";
    list.forEach(function (m, i) {
      var d = parseLocal(m.achieved_at), mk = MONTHS[d.getMonth()] + " " + d.getFullYear();
      if (mk !== month) { html += (month ? "</section>" : "") + '<div class="ms-month">' + mk + '</div><section class="stack">'; month = mk; }
      html += '<div class="card ms-item">' + msRow(m, i) + "</div>";
    });
    return '<div class="section-title"><h2>' + MILESTONES.length + " milestones</h2></div>" + html + "</section>";
  }

  // ---- router ----
  function render() {
    var hash = (location.hash || "#overview").slice(1);
    var parts = hash.split("/"), tab = parts[0];
    var html;
    if (tab === "session") html = sessionDetail(decodeURIComponent(parts.slice(1).join("/")));
    else if (tab === "trends") html = trends();
    else if (tab === "sessions") html = sessions();
    else if (tab === "milestones") html = milestones();
    else { tab = "overview"; html = overview(); }
    view.innerHTML = '<div class="stack">' + html + "</div>";

    var activeTab = tab === "session" ? "sessions" : tab;
    document.querySelectorAll("#tabs a").forEach(function (a) {
      if (a.getAttribute("data-tab") === activeTab) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
    });
    document.querySelectorAll("[data-unit]").forEach(function (b) { b.setAttribute("aria-pressed", String(b.getAttribute("data-unit") === state.unit)); });

    if (tab === "trends" && SESSIONS.length) {
      drawTrends();
      view.querySelectorAll("[data-period]").forEach(function (b) {
        b.onclick = function () { state.period = b.getAttribute("data-period"); prefs.set("period", state.period); render(); };
      });
    }
    if (tab === "session") drawTimeline(decodeURIComponent(parts.slice(1).join("/")));
    if (tab === "overview") {
      wireShare(view, newMilestones());
      var x = document.getElementById("dismiss");
      if (x) x.onclick = function () { prefs.set("dismissed", String(DATA.latest_import_id)); render(); };
    }
    if (tab === "milestones") wireShare(view, MILESTONES.slice().reverse());
  }

  function footer() {
    var gen = DATA.generated_at ? parseLocal(DATA.generated_at) : null;
    document.getElementById("foot").innerHTML =
      "Stroke type, spin and speed are decoded from an undocumented file format and may be inaccurate — " +
      '<a href="' + REPO + '/blob/main/docs/FILE_FORMAT.md" target="_blank" rel="noopener">how the data is decoded</a>.' +
      (gen ? " Updated " + dLong(gen) + " " + tOfDay(gen) + "." : "") +
      ' Not affiliated with Babolat. <a href="' + REPO + '" target="_blank" rel="noopener">Open source</a>.';
    if (DATA.demo) { var b = document.getElementById("demoBadge"); b.textContent = DATA.demo; b.hidden = false; }
  }

  document.querySelectorAll("[data-unit]").forEach(function (b) {
    b.onclick = function () { state.unit = b.getAttribute("data-unit"); prefs.set("unit", state.unit); render(); };
  });
  document.getElementById("themeBtn").onclick = function () {
    var root = document.documentElement;
    var dark = root.getAttribute("data-theme") ? root.getAttribute("data-theme") === "dark"
      : window.matchMedia("(prefers-color-scheme: dark)").matches;
    root.setAttribute("data-theme", dark ? "light" : "dark");
    prefs.set("theme", dark ? "light" : "dark");
    render();
  };
  var forced = /[?&]theme=(light|dark)/.exec(location.search);
  var savedTheme = forced ? forced[1] : prefs.get("theme", "");
  if (savedTheme) document.documentElement.setAttribute("data-theme", savedTheme);
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", render);
  window.addEventListener("hashchange", function () { render(); window.scrollTo(0, 0); });

  footer();
  render();

  // Home-screen apps have no reload button: when the app comes back to the
  // foreground, check for a newer import and reload if there is one.
  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState !== "visible" || location.protocol.indexOf("http") !== 0) return;
    fetch("data.js", { cache: "no-store" }).then(function (r) { return r.ok ? r.text() : ""; }).then(function (t) {
      var m = /"generated_at":"([^"]+)"/.exec(t);
      if (m && m[1] !== DATA.generated_at) location.reload();
    }).catch(function () { /* Mac not reachable: keep showing the cached stats */ });
  });

  if ("serviceWorker" in navigator && location.protocol.indexOf("http") === 0) {
    navigator.serviceWorker.register("sw.js").catch(function () { /* offline support is optional */ });
  }
})();
