// /static/spa.js
(function () {
  const VIEW_MAP = {
    "/index": "index.html",
    "/presupuesto": "presupuesto.html",
    "/admin": "admin.html",
  };

  // Bloquea navegación por submit en vistas SPA (los handlers hacen fetch).
  document.addEventListener(
    "submit",
    (e) => {
      const form = e.target;
      if (form && !form.hasAttribute("data-allow-nav")) e.preventDefault();
    },
    true
  );

  // Intercepta los links del navbar
  const nav = document.querySelector("header nav");
  if (nav) {
    nav.querySelectorAll("a").forEach((a) => {
      a.addEventListener("click", (ev) => {
        const view = a.getAttribute("href");
        if (!view || !view.startsWith("/")) return;
        ev.preventDefault();
        loadView(view);
      });
    });
  }

  // Delegación global para <a> o <button> con data-view
  document.addEventListener("click", (ev) => {
    const el = ev.target.closest("a[data-view], button[data-view]");
    if (!el) return;
    const view = el.dataset.view || el.getAttribute("href");
    if (!view || !view.startsWith("/")) return;
    ev.preventDefault();
    loadView(view);
  });

  async function fetchView(file) {
    const candidates = [`/static/${file}`, `/${file}`];
    for (const url of candidates) {
      try {
        const res = await fetch(url, { cache: "no-store" });
        if (!res.ok) continue;
        const html = await res.text();
        if (html && html.toLowerCase().includes("<main")) {
          return html;
        }
      } catch {}
    }
    throw new Error(`No se pudo cargar ${file}`);
  }

  async function loadView(viewPath) {
    const file = VIEW_MAP[viewPath] || "index.html";
    try {
      const html = await fetchView(file);
      const doc = new DOMParser().parseFromString(html, "text/html");

      // Reemplazar <main>
      const newMain = doc.querySelector("main");
      const oldMain = document.querySelector("main");
      if (!newMain || !oldMain) return;
      oldMain.replaceWith(newMain);

      // Limpiar estilos previos de la vista y agregar los nuevos
      document
        .querySelectorAll("link[data-spa], style[data-spa]")
        .forEach((e) => e.remove());
      doc.querySelectorAll("link[rel='stylesheet'], style").forEach((el) => {
        const clone = el.cloneNode(true);
        clone.dataset.spa = "1";
        document.head.appendChild(clone);
      });

      // Título y link activo
      document.title =
        doc.querySelector("title")?.textContent || document.title;
      document.querySelectorAll("header nav a").forEach((a) => {
        a.classList.toggle("active", a.getAttribute("href") === viewPath);
      });

      // 🔁 RE-EJECUTAR SCRIPTS DE LA VISTA (fix para inline)
      // 1) Sacar scripts de una vista anterior
      document.querySelectorAll("script[data-spa]").forEach((e) => e.remove());
      // 2) Inyectar y ejecutar scripts de la vista actual (SIN defer)
      doc.querySelectorAll("script").forEach((s) => {
        const ns = document.createElement("script");
        if (s.src) {
          ns.src = s.src;
          ns.async = false;        // mantener orden
        } else {
          ns.textContent = s.textContent; // inline se ejecuta al append
        }
        ns.dataset.spa = "1";
        document.body.appendChild(ns);
      });

      // Disparar un DOMContentLoaded sintético (por si la vista lo usa)
      document.dispatchEvent(new Event("DOMContentLoaded"));

      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (e) {
      console.error("Error cargando vista", file, e);
    }
  }

  // Exponer para consola: SPA.load('/presupuesto')
  window.SPA = { load: loadView };

  // Aplanar URL inicial (cosmético)
  try {
    if (location.pathname !== "/") history.replaceState(null, "", "/");
  } catch {}
})();
