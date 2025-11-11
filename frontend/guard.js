// guard.js — protege rutas sensibles como /admin y /presupuesto

function goGuarded(url, key) {
  sessionStorage.setItem("guard_access", key);
  window.location.href = url;
}

function verifyGuard(expected) {
  const key = sessionStorage.getItem("guard_access");
  if (key !== expected) {
    document.body.innerHTML = `
      <div style="
        height:100vh;display:flex;flex-direction:column;
        align-items:center;justify-content:center;
        background:#000;color:#ffcc00;font-family:sans-serif;
        text-align:center;padding:20px;
      ">
        <h1 style="font-size:2rem;">🚫 Acceso inválido</h1>
        <p>No podés entrar directamente a esta página.</p>
        <button style="
          margin-top:20px;padding:10px 18px;border:none;
          border-radius:12px;background:#ffcc00;color:#111;
          font-weight:800;cursor:pointer;
        " onclick="window.location.href='/index'">Volver al inicio</button>
      </div>
    `;
    sessionStorage.removeItem("guard_access");
    throw new Error("Guard: acceso bloqueado");
  }
  sessionStorage.removeItem("guard_access");
  console.log("Guard check → ok");
}
