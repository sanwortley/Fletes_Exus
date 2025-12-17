// /static/spa.js
(function () {

  // ========= helpers =========
  function cleanupHomeOnly() {
    document.querySelectorAll("[data-home-only]").forEach(el => el.remove());
  }

  function wireNavOnce() {
    const nav = document.querySelector("header nav");
    if (!nav || nav.dataset.spaNavWired === "1") return;
    nav.dataset.spaNavWired = "1";

    nav.querySelectorAll("a").forEach(a => {
      a.addEventListener("click", ev => {
        const view = a.getAttribute("href");
        if (!view || !view.startsWith("/")) return;
        ev.preventDefault();
        loadView(view);
      });
    });
  }

  async function fetchView(viewPath) {
    const res = await fetch(viewPath, { cache: "no-store" });
    if (!res.ok) throw new Error(`No se pudo cargar ${viewPath}`);
    return await res.text();
  }

  function wrapInlineScript(code) {
    return `(function(){ "use strict"; ${code} })();`;
  }

  function runViewScripts(doc) {
    document.querySelectorAll("script[data-spa]").forEach(s => s.remove());

    doc.querySelectorAll("script").forEach(s => {
      if (s.src && s.src.includes("/static/spa.js")) return;

      const ns = document.createElement("script");
      if (s.src) {
        ns.src = s.src;
        ns.async = false;
      } else {
        const code = (s.textContent || "").trim();
        if (!code) return;
        ns.textContent = wrapInlineScript(code);
      }
      ns.dataset.spa = "1";
      document.body.appendChild(ns);
    });
  }

  // ========= core =========
  async function loadView(viewPath) {
    try {
      if (viewPath !== "/" && viewPath !== "/index") {
        cleanupHomeOnly();
      }

      const html = await fetchView(viewPath);
      const doc = new DOMParser().parseFromString(html, "text/html");

      const newHeader = doc.querySelector("header");
      const oldHeader = document.querySelector("header");
      if (newHeader && oldHeader) oldHeader.replaceWith(newHeader);

      const newMain = doc.querySelector("main");
      const oldMain = document.querySelector("main");
      if (!newMain || !oldMain) return;
      oldMain.replaceWith(newMain);

      document.querySelectorAll("link[data-spa], style[data-spa]")
        .forEach(e => e.remove());

      doc.querySelectorAll("link[rel='stylesheet'], style").forEach(el => {
        const clone = el.cloneNode(true);
        clone.dataset.spa = "1";
        document.head.appendChild(clone);
      });

      document.title = doc.querySelector("title")?.textContent || document.title;

      wireNavOnce();
      runViewScripts(doc);

      window.scrollTo({ top: 0, behavior: "smooth" });

    } catch (e) {
      console.error("SPA error:", e);
    }
  }

  // ========= init =========
  document.addEventListener("submit", e => {
    if (!e.target.hasAttribute("data-allow-nav")) e.preventDefault();
  }, true);

  wireNavOnce();

  window.SPA = { load: loadView };

})();
