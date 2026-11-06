/* SPDX-License-Identifier: AGPL-3.0-only
 * Authenticated Text Center Kit preview. Original standalone HTML/CSS only;
 * never run the standalone app.js with its unsafe standalone POST endpoints.
 * Read-only owner-bound existing SQLite if configured; no network fetch/RF.
 * Untrusted source text enters the DOM with textContent, never innerHTML.
 */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const API = "/text-center/api/";
  let catalogue = {};
  let archiveAvailable = false;
  let sourcePages = [];
  const NO_RF = "IMPORTED / CACHED • NOT LIVE RF • NOT AN OFFICIAL ALERT";
  const notice = (value) => {
    $("notification").textContent = value;
    $("notification").hidden = false;
  };
  const make = (tag, cls, value) => {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (value != null) node.textContent = String(value);
    return node;
  };
  const api = async (endpoint) => {
    const result = await fetch(API + endpoint, {
      method: "GET", credentials: "same-origin", cache: "no-store",
      headers: { Accept: "application/json" }
    });
    if (!result.ok) throw new Error("Text Center " + endpoint + ": HTTP " + result.status);
    return result.json();
  };
  const card = (title, content, meta) => {
    const item = make("article", "notice-card");
    item.appendChild(make("h3", "", title));
    item.appendChild(make("p", "", content));
    if (meta) item.appendChild(make("small", "subtle", meta));
    return item;
  };
  const action = (label, callback) => {
    const item = make("button", "action ghost", label);
    item.type = "button";
    item.addEventListener("click", callback);
    return item;
  };
  const setMode = (mode) => {
    const classic = mode === "classic";
    document.body.classList.toggle("kit-classic-teletext", classic);
    $("kit-visual-mode").textContent = classic ? "MODERN VIEW" : "CLASSIC TELETEXT";
    $("kit-visual-mode").setAttribute("aria-pressed", String(classic));
    try { localStorage.setItem("tihulu:text-center:view-mode", classic ? "classic" : "modern"); }
    catch (_) { /* Local storage may be disabled; UI still works. */ }
  };
  const prepare = (page, subpage, title) => {
    $("page-number").value = String(page);
    $("subpage-number").value = String(subpage);
    $("view-title").textContent = "PAGE " + page + " — " + title.toUpperCase();
    $("teletext-page").textContent = "P" + page + " / " + String(subpage).padStart(2, "0");
    $("view-source").textContent = "LOCAL / READ-ONLY";
    $("view-stamp").textContent = "";
    $("teletext-kicker").textContent = "TEXT CENTER / SOURCE-ATTRIBUTED ARCHIVE";
    $("teletext-title").textContent = title.toUpperCase();
    $("teletext-body").textContent = "No live broadcast receiver is connected to this view.";
    $("section-kicker").textContent = "LOCAL / READ-ONLY";
    $("section-title").textContent = title;
    $("section-count").textContent = "";
    $("content").replaceChildren();
    document.querySelectorAll("[data-page]").forEach((el) => {
      el.classList.toggle("active", Number(el.dataset.page) === page);
    });
  };
  const add = (node) => $("content").appendChild(node);
  const missing = (message) => add(card("Local archive unavailable", message,
    "SOURCE NOT CONNECTED • NOTHING FABRICATED"));
  const originalPage = async (page, subpage, sourceId) => {
    const query = new URLSearchParams({
      number: String(page), subpage: String(subpage), source_id: sourceId
    });
    prepare(page, subpage, "Imported page");
    try {
      const entry = await api("archive/page?" + query.toString());
      $("teletext-title").textContent = entry.title;
      $("teletext-body").textContent = entry.body;
      $("view-title").textContent = "P" + page + "/" + subpage + " — " + entry.title;
      $("view-source").textContent = "IMPORTED / " + entry.medium + " / " + entry.station;
      $("view-stamp").textContent = entry.received_at;
      $("section-title").textContent = "Original received page • archived";
      add(card("Source provenance",
        "Station: " + entry.station + " · " + entry.frequency_hz +
        " Hz · Source: " + entry.source_id + " · Received: " + entry.received_at +
        " · Decoder: " + entry.provenance, NO_RF));
      $("source-select").value = sourceId;
      notice("Archived decoded text only — this does NOT initiate receiver tuning.");
    } catch (error) {
      missing(error.message + ". No decoded page was returned.");
      notice("No archived broadcast page available for that source and subpage.");
    }
  };
  const originalArticle = async (id) => {
    try {
      const item = await api("archive/article?id=" + encodeURIComponent(id));
      prepare(200, 0, item.title);
      $("teletext-title").textContent = item.title;
      $("teletext-body").textContent = item.body;
      $("view-source").textContent = "CACHED INTERNET / " + item.source_name;
      $("view-stamp").textContent = item.observed_at;
      add(card("Original publisher and timestamps",
        "Source: " + item.source_url + " · Published: " + item.published_at +
        " · Cached: " + item.observed_at + " · Original URL: " + item.url,
        "CACHED INTERNET FEED • NOT A LIVE PAGE"));
    } catch (error) {
      notice("Cached article unavailable: " + error.message);
    }
  };
  const articles = async () => {
    if (!archiveAvailable) return missing("Owner SQLite archive has not been configured.");
    try {
      const response = await api("archive/articles");
      const items = Array.isArray(response.items) ? response.items : [];
      $("section-count").textContent = items.length + " stored articles • no refresh";
      if (!items.length) return missing("No cached RSS/Atom/JSON Feed articles exist.");
      items.forEach((item) => {
        const node = card(item.title, item.excerpt,
          "CACHED INTERNET / " + item.source_name + " / " + item.observed_at);
        node.appendChild(action("READ STORED ARTICLE", () => originalArticle(item.id)));
        add(node);
      });
    } catch (error) { missing(error.message); }
  };
  const importedPages = async () => {
    if (!archiveAvailable) return missing("No owner archive configured.");
    if (!sourcePages.length) return missing("No source-attributed Teletext/Journaline pages imported.");
    sourcePages.forEach((item) => {
      const node = card("P" + item.page + " / " + item.subpage + " — " + item.title,
        "Station: " + item.station + " · Received: " + item.received_at +
        " · " + item.medium + " · " + item.frequency_hz + " Hz",
        "IMPORTED, NOT LIVE / " + item.provenance);
      node.appendChild(action("READ IMPORTED PAGE",
        () => originalPage(item.page, item.subpage, item.source_id)));
      add(node);
    });
  };
  const events = async (weatherOnly = false) => {
    if (!archiveAvailable) return missing("No owner archive configured.");
    try {
      const response = await api("archive/events");
      const rows = (Array.isArray(response.items) ? response.items : [])
        .filter((e) => !weatherOnly || ["navtex", "hf_weather"].includes(e.medium));
      $("section-count").textContent = rows.length + " archived events";
      if (!rows.length) return missing("No attributed receiver events imported.");
      rows.forEach((event) => {
        add(card(event.title, event.excerpt,
          "RECEIVED " + event.received_at + " / " + event.station +
          " / " + event.frequency_hz + " Hz / " + event.medium +
          " / " + event.provenance + " • " + NO_RF));
      });
    } catch (error) { missing(error.message); }
  };
  const capabilities = async () => {
    add(card("Protocol and receiver dependency catalogue",
      "A device candidate or installed decoder never proves RF reception.",
      "REFERENCE CAPABILITIES • NOT A LIVE SCAN"));
    try {
      const result = await api("capabilities");
      const features = Array.isArray(result.capabilities) ? result.capabilities : [];
      features.forEach((feature) => add(card(
        feature.title || feature.id || "Unknown protocol",
        feature.requirements || feature.reason || "Requires verified decoder and hardware.",
        "CAPABILITY / " + (feature.state || feature.implementation || "unavailable"))));
      $("section-count").textContent = features.length + " tracked capabilities";
    } catch (error) { missing(error.message); }
  };
  const showGroup = async (page, subpage = 0, sourceId = "") => {
    if (!Number.isInteger(page) || page < 100 || page > 899 ||
        !Number.isInteger(subpage) || subpage < 0 || subpage > 99) {
      notice("Page must be 100–899 and subpage 0–99.");
      return;
    }
    if (sourceId) return originalPage(page, subpage, sourceId);
    if (subpage !== 0 || !Object.hasOwn(catalogue, String(page))) {
      notice("No decoded source page selected. Choose an imported source first.");
      return;
    }
    const name = catalogue[String(page)];
    prepare(page, subpage, name);
    $("source-select").value = "";
    if (page === 100) {
      Object.entries(catalogue).forEach(([number, label]) => {
        const node = card("P" + number + " — " + label,
          "Browse this category. Live receiver actions remain disabled.",
          "LOCAL INDEX / NOT RF RECEPTION");
        node.appendChild(action("OPEN CATEGORY", () => showGroup(Number(number))));
        add(node);
      });
      $("section-count").textContent = "10 original numbered sections";
    } else if (page === 200) {
      await articles();
    } else if (page === 400) {
      await importedPages();
      await events(false);
      await capabilities();
    } else if (page === 300) {
      await events(true);
    } else if (page === 700) {
      add(card("Local library", "Original Kiwix/Kolibri and PDFs still require their shared Library service. Below are existing imported Text Center pages.", "OFFLINE / NOT A DUPLICATE WIKI"));
      await importedPages();
    } else if (page === 860) {
      await capabilities();
    } else {
      const explanations = {
        500: "Only separately verified Emergency Center issuers can create official alerts. Imported RF events are not official alerts.",
        600: "Local BBS posting is disabled until per-owner identity, permissions and CSRF are integrated.",
        800: "Native Gemini and Gopher clients are pending. Directory links do not imply downloaded offline content.",
        850: "Original Text Center HTML/CSS with a protected Kit GET-only client. Existing archived page/news reads are available only after owner configuration."
      };
      add(card("Integration status", explanations[page] || "No eligible archived data.",
        "SOURCE-AWARE / OTHER FUNCTIONS PENDING"));
    }
  };
  const inspectDevices = async () => {
    const b = $("receiver-recheck"); b.disabled = true;
    try {
      const result = await api("discovery");
      const inv = result.inventory || {};
      $("rtl-status").textContent = result.status === "passive_only"
        ? Number(inv.rtl_usb_count || 0) + " RTL-SDR candidate(s), not tuned"
        : "Receiver dependency not connected";
      $("dvb-status").textContent =
        (Array.isArray(inv.dvb_frontends) ? inv.dvb_frontends.length : 0) +
        " DVB frontend candidate(s), no PID lock verified";
      $("decoder-status").textContent = "RF text decoder inactive in Kit";
      $("receiver-check-note").textContent = "Passive inventory only • no RF or Internet request";
      notice("Device inventory checked without tuning or background fetch.");
    } catch (error) {
      notice("Passive receiver inspection unavailable: " + error.message);
    } finally { b.disabled = false; }
  };
  const loadArchive = async () => {
    try {
      const state = await api("archive/status");
      archiveAvailable = state.status === "read_only";
      const counts = state.counts || {};
      $("stat-articles").textContent = String(counts.articles || 0);
      $("stat-pages").textContent = String(counts.pages || 0);
      $("stat-events").textContent = String(counts.events || 0);
      $("stat-posts").textContent = "—";
      const response = await api("archive/pages");
      sourcePages = Array.isArray(response.items) ? response.items : [];
      const names = new Map();
      sourcePages.forEach((item) => {
        if (!names.has(item.source_id)) names.set(item.source_id, item.station);
      });
      const sourceControl = $("source-select");
      sourceControl.replaceChildren(make("option", "", "Local index / all sources"));
      sourceControl.firstElementChild.value = "";
      names.forEach((station, sourceId) => {
        const option = make("option", "", station + " · " + sourceId);
        option.value = sourceId;
        sourceControl.appendChild(option);
      });
      sourceControl.disabled = !names.size;
      sourceControl.title = names.size ? "Select previously imported decoder source" :
        "No archived receiver pages exist";
    } catch (_) {
      archiveAvailable = false;
      $("source-select").disabled = true;
      $("stat-articles").textContent = "—";
      $("stat-pages").textContent = "—";
      $("stat-events").textContent = "—";
      $("stat-posts").textContent = "—";
    }
  };
  const start = async () => {
    $("clock").textContent = new Date().toLocaleTimeString([], {
      hour: "2-digit", minute: "2-digit"
    });
    $("bookmark-page").disabled = true;
    $("bookmark-page").title = "Saving bookmarks requires owner-scoped writable services";
    $("source-select").disabled = true;
    $("kit-visual-mode").addEventListener("click", () => setMode(
      document.body.classList.contains("kit-classic-teletext") ? "modern" : "classic"));
    let mode = "modern";
    try { mode = localStorage.getItem("tihulu:text-center:view-mode"); } catch (_) {}
    setMode(mode);
    $("page-form").addEventListener("submit", (event) => {
      event.preventDefault();
      showGroup(Number($("page-number").value),
        Number($("subpage-number").value), $("source-select").value);
    });
    document.querySelectorAll("[data-page]").forEach((item) => {
      item.addEventListener("click", () => showGroup(Number(item.dataset.page)));
    });
    $("receiver-recheck").addEventListener("click", inspectDevices);
    document.addEventListener("keydown", (event) => {
      if (event.key.toLowerCase() === "g" &&
          !["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName)) {
        event.preventDefault();
        $("page-number").focus();
        $("page-number").select();
      }
    });
    try {
      const data = await api("pages");
      catalogue = data.pages || {};
      await loadArchive();
      await showGroup(100);
      notice(archiveAvailable
        ? "Viewing existing cached source data. No broadcast receiver opened."
        : "Read-only Kit preview; source archive not configured. No RF access.");
    } catch (error) {
      notice("Authenticated Text Center API unavailable: " + error.message);
      $("teletext-body").textContent = "The local API or owner session is unavailable.";
    }
  };
  start();
})();