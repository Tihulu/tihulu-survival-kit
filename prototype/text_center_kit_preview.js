/* SPDX-License-Identifier: AGPL-3.0-only
 * Read-only Kit gateway adapter for an owner-installed Text Center HTML/CSS.
 * This script intentionally does NOT run the standalone RF/BBS/feed POST UI.
 * All server-derived content uses textContent, never innerHTML.
 */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const API = "/text-center/api/";
  let currentPage = 100;
  let catalogue = {};
  let capabilities = [];
  const NO_RF = "No receiver opened • No RF or verified official alert";
  const status = (message) => {
    const target = $("notification");
    target.textContent = message;
    target.hidden = false;
  };
  const make = (tag, className, text) => {
    const item = document.createElement(tag);
    if (className) item.className = className;
    if (text != null) item.textContent = String(text);
    return item;
  };
  const fetchJSON = async (name) => {
    const result = await fetch(API + name, {
      credentials: "same-origin", cache: "no-store",
      headers: { "Accept": "application/json" }
    });
    if (!result.ok) throw new Error("Text Center " + name + ": HTTP " + result.status);
    return result.json();
  };
  const safeMode = (value) => value === "classic" ? "classic" : "modern";
  const modeKey = "tihulu:text-center:view-mode";
  const setMode = (mode) => {
    const classic = safeMode(mode) === "classic";
    document.body.classList.toggle("kit-classic-teletext", classic);
    const button = $("kit-visual-mode");
    button.textContent = classic ? "MODERN VIEW" : "CLASSIC TELETEXT";
    button.setAttribute("aria-pressed", String(classic));
    try { localStorage.setItem(modeKey, classic ? "classic" : "modern"); }
    catch (_) { /* private browsing may disable local storage */ }
  };
  const noticeCard = (title, body, meta) => {
    const article = make("article", "notice-card");
    article.appendChild(make("h3", "", title));
    article.appendChild(make("p", "", body));
    if (meta) article.appendChild(make("small", "subtle", meta));
    return article;
  };
  const updateHeader = (page, subpage, name) => {
    $("page-number").value = String(page);
    $("subpage-number").value = String(subpage);
    $("view-title").textContent = "PAGE " + page + " — " + name.toUpperCase();
    $("teletext-page").textContent =
      "P" + page + " / " + String(subpage).padStart(2, "0");
    $("view-source").textContent = "OFFLINE / BRIDGE STATUS ONLY";
    $("view-stamp").textContent = "";
    $("teletext-kicker").textContent = "TEXT CENTER • INTEGRATION PREVIEW";
    $("teletext-title").textContent = name.toUpperCase();
    $("teletext-body").textContent =
      "Read-only index. Imported pages and live source integrations are not yet connected.";
    $("section-kicker").textContent = "READ-ONLY / NO RF";
    $("section-title").textContent = name;
    $("section-count").textContent = "";
    document.querySelectorAll("[data-page]").forEach((button) => {
      button.classList.toggle("active", Number(button.dataset.page) === page);
    });
  };
  const showPage = async (page, subpage = 0) => {
    if (!Number.isInteger(page) || page < 100 || page > 899 ||
        !Number.isInteger(subpage) || subpage < 0 || subpage > 99) {
      status("Page must be 100–899; subpage 0–99.");
      return;
    }
    const name = catalogue[String(page)];
    if (!name || subpage !== 0) {
      status("Page/subpage not loaded: no verified source page in the Kit bridge.");
      return;
    }
    currentPage = page;
    updateHeader(page, subpage, name);
    const body = $("content");
    body.replaceChildren();
    if (page === 100) {
      Object.entries(catalogue).forEach(([key, label]) => {
        const card = noticeCard(
          "P" + key + " — " + label,
          "Open this category. All live RF, news and message controls remain disabled until verified.",
          "OFFLINE INDEX • NOT RECEIVED BROADCAST");
        const action = make("button", "action ghost", "VIEW CATEGORY");
        action.type = "button";
        action.addEventListener("click", () => showPage(Number(key)));
        card.appendChild(action);
        body.appendChild(card);
      });
      $("section-count").textContent = "10 preserved page groups";
      return;
    }
    if (page === 400 || page === 860) {
      const first = noticeCard("Protocol and receiver capabilities",
        "This list describes optional dependencies and implementation status. A detected device is not decoded RadioText.",
        "SOURCE: INSTALLED REFERENCE CATALOGUE • NOT AN RF CAPTURE");
      body.appendChild(first);
      try {
        const response = await fetchJSON("capabilities");
        capabilities = Array.isArray(response.capabilities) ? response.capabilities : [];
        capabilities.forEach((feature) => {
          const label = feature.title || feature.id || "Unknown protocol";
          const detail = feature.requirements || feature.reason ||
                         "Real decoder and receiver must be verified.";
          const meta = feature.state || feature.implementation || "Unavailable";
          body.appendChild(noticeCard(label, detail, "CAPABILITY • " + meta));
        });
        $("section-count").textContent = capabilities.length +
          " capabilities • operating state not guaranteed";
      } catch (error) {
        body.appendChild(noticeCard("Optional reference not connected",
          error.message, "DEPENDENCY UNAVAILABLE"));
      }
      return;
    }
    const messages = {
      200: "News feeds are not linked to the shared News & Politics Center yet. No background refresh.",
      300: "Weather bulletins require genuine dated Internet or decoded RF sources; no forecast is invented.",
      500: "Only the independently verified Emergency Center may certify official alerts. Imported RF text is not an official warning.",
      600: "Authenticated multi-user BBS and posting controls are not connected. This preview never transmits.",
      700: "Original Kiwix, Kolibri, PDFs and offline libraries must be connected through shared read permissions.",
      800: "Native bounded Gemini/Gopher clients and permitted text-network directories are not yet integrated.",
      850: "This view uses the original Text Center markup/CSS and a restricted Kit-controlled GET-only client."
    };
    body.appendChild(noticeCard("Integration status",
      messages[page] || "No decoded page is available for this category.", NO_RF));
    $("section-count").textContent = "SOURCE-ATTRIBUTED CONTENT PENDING";
  };
  const inspectDevices = async () => {
    const button = $("receiver-recheck");
    button.disabled = true;
    try {
      const d = await fetchJSON("discovery");
      const inventory = d.inventory || {};
      const count = Number(inventory.rtl_usb_count || 0);
      const dvbCount = Array.isArray(inventory.dvb_frontends)
        ? inventory.dvb_frontends.length : 0;
      $("rtl-status").textContent = d.status === "passive_only"
        ? count + " RTL-SDR candidate(s) • no RF decoded"
        : "Receiver package unavailable";
      $("dvb-status").textContent =
        dvbCount + " DVB frontend candidate(s) • no Teletext PID verified";
      $("decoder-status").textContent = "RF text decoder inactive in Kit";
      $("receiver-check-note").textContent =
        "Passive inventory only • no tuning • source not verified";
      status("Passive inventory complete. No SDR tuning or Internet fetch was requested.");
    } catch (error) {
      status("Passive device check unavailable: " + error.message);
    } finally { button.disabled = false; }
  };
  const start = async () => {
    const now = new Date();
    $("clock").textContent = now.toLocaleTimeString([], {
      hour: "2-digit", minute: "2-digit"
    });
    $("bookmark-page").disabled = true;
    $("bookmark-page").title = "Bookmarks require owner-scoped database integration";
    $("source-select").disabled = true;
    $("source-select").title = "Verified receiver pages are not connected";
    $("stat-articles").textContent = "—";
    $("stat-pages").textContent = "—";
    $("stat-events").textContent = "—";
    $("stat-posts").textContent = "—";
    $("kit-visual-mode").addEventListener("click", () => {
      setMode(document.body.classList.contains("kit-classic-teletext")
        ? "modern" : "classic");
    });
    let last = "modern";
    try { last = localStorage.getItem(modeKey); } catch (_) {}
    setMode(last);
    $("page-form").addEventListener("submit", (event) => {
      event.preventDefault();
      showPage(Number($("page-number").value), Number($("subpage-number").value));
    });
    document.querySelectorAll("[data-page]").forEach((el) => {
      el.addEventListener("click", () => showPage(Number(el.dataset.page)));
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
      const response = await fetchJSON("pages");
      catalogue = response.pages || {};
      await showPage(100);
      status("Read-only Kit preview. Full imported pages, feeds, scan and messaging are not connected.");
    } catch (error) {
      status("Text Center page catalogue unavailable: " + error.message);
      $("teletext-body").textContent = "Authenticated API unavailable.";
    }
  };
  start();
})();