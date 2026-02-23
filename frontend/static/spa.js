// /static/spa.js
(function () {

  // ========= helpers =========
  function cleanupHomeOnly() {
    document.querySelectorAll("[data-home-only]").forEach(el => el.remove());
  }

  function wireNavOnce() {
    const navLinksContainer = document.querySelector(".nav-links");
    if (!navLinksContainer) return;

    // Quitamos o ignoramos si ya está cableado
    if (navLinksContainer.dataset.spaNavWired === "1") return;
    navLinksContainer.dataset.spaNavWired = "1";

    navLinksContainer.querySelectorAll("a").forEach(a => {
      a.addEventListener("click", ev => {
        const view = a.getAttribute("href");
        if (!view || !view.startsWith("/")) return;
        ev.preventDefault();
        loadView(view);
      });

      // Prefetch on hover
      a.addEventListener("mouseenter", () => {
        const view = a.getAttribute("href");
        if (view && view.startsWith("/")) {
          fetchView(view).catch(() => { }); // prefetch background
        }
      });
    });
  }

  function updateActiveLink(path) {
    let normalizedPath = path.split('?')[0].split('#')[0];
    if (normalizedPath === "" || normalizedPath === "/index" || normalizedPath === "/index.html") {
      normalizedPath = "/";
    }
    if (normalizedPath.length > 1 && normalizedPath.endsWith("/")) {
      normalizedPath = normalizedPath.slice(0, -1);
    }


    const links = document.querySelectorAll(".nav-links a");
    links.forEach(a => {
      const href = a.getAttribute("href") || "";
      let normalizedHref = href.split('?')[0].split('#')[0];
      if (normalizedHref === "/index" || normalizedHref === "/index.html") {
        normalizedHref = "/";
      }
      if (normalizedHref.length > 1 && normalizedHref.endsWith("/")) {
        normalizedHref = normalizedHref.slice(0, -1);
      }

      if (normalizedHref === normalizedPath) {
        a.classList.add("active");
      } else {
        a.classList.remove("active");
      }
    });
  }

  const viewCache = {};

  async function fetchView(viewPath) {
    if (viewCache[viewPath]) return viewCache[viewPath];

    // Si es la primera vez, cargamos (con cache del browser permitida para mayor rapidez)
    const res = await fetch(viewPath);
    if (!res.ok) throw new Error(`No se pudo cargar ${viewPath}`);
    const html = await res.text();
    viewCache[viewPath] = html;
    return html;
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

  function showLoading(show) {
    let loader = document.getElementById("spa-loader");
    if (!loader) {
      loader = document.createElement("div");
      loader.id = "spa-loader";
      loader.style = "position:fixed;top:0;left:0;height:3px;background:var(--primary,#D3A129);z-index:9999;transition:width 0.4s ease;width:0;";
      document.body.appendChild(loader);
    }
    if (show) {
      loader.style.width = "40%";
      loader.style.opacity = "1";
    } else {
      loader.style.width = "100%";
      setTimeout(() => { loader.style.opacity = "0"; setTimeout(() => { loader.style.width = "0"; }, 400); }, 200);
    }
  }

  // ========= core =========
  async function loadView(viewPath) {
    try {
      showLoading(true);
      if (viewPath !== "/" && viewPath !== "/index") {
        cleanupHomeOnly();
      }

      const html = await fetchView(viewPath);
      const doc = new DOMParser().parseFromString(html, "text/html");

      // 1. Sincronizar URL
      if (window.location.pathname !== viewPath) {
        window.history.pushState({ path: viewPath }, "", viewPath);
      }

      // 2. Sincronizar DATA-PAGE del Body (CRÍTICO para los scripts internos)
      const newPageValue = doc.body.dataset.page;
      if (newPageValue) {
        document.body.dataset.page = newPageValue;
      }

      // 3. Reemplazar Header y Main
      const newHeader = doc.querySelector("header");
      const oldHeader = document.querySelector("header");
      if (newHeader && oldHeader) {
        oldHeader.replaceWith(newHeader);
      }

      const newMain = doc.querySelector("main");
      const oldMain = document.querySelector("main");
      if (newMain && oldMain) {
        oldMain.replaceWith(newMain);
      }

      const newFooter = doc.querySelector("footer");
      const oldFooter = document.querySelector("footer");
      if (newFooter && oldFooter) {
        oldFooter.replaceWith(newFooter);
      }

      // 4. Metadatos y Estilos
      document.title = doc.querySelector("title")?.textContent || document.title;
      document.querySelectorAll("link[data-spa], style[data-spa]").forEach(e => e.remove());
      doc.querySelectorAll("link[rel='stylesheet'], style").forEach(el => {
        const clone = el.cloneNode(true);
        clone.dataset.spa = "1";
        document.head.appendChild(clone);
      });

      // 5. Cablear y Marcar Activo (En este orden)
      wireNavOnce();
      updateActiveLink(viewPath);
      runViewScripts(doc);

      window.scrollTo({ top: 0, behavior: "smooth" });
      showLoading(false);

    } catch (e) {
      console.error("SPA error:", e);
      showLoading(false);
    }
  }

  // ========= init =========
  document.addEventListener("submit", e => {
    if (!e.target.hasAttribute("data-allow-nav")) e.preventDefault();
  }, true);

  window.addEventListener("popstate", () => {
    loadView(window.location.pathname);
  });

  // Ejecución inicial
  wireNavOnce();
  updateActiveLink(window.location.pathname);

  window.SPA = { load: loadView };

})();
