function AppShell({ children, currentUser = 'Asharet' }) {
  return (
    <div className="app-shell">
      <header className="app-shell__header">
        <div className="app-shell__brand">
          <img
            className="app-shell__logo"
            src="/favicon.svg"
            alt="Logo del proyecto"
          />
          <div className="app-shell__brand-copy">
            <p className="app-shell__subtitle">Monitor de riesgo en redes sociales</p>
            <h1>Chimalli</h1>
          </div>
        </div>

        <div className="app-shell__session" aria-label="Usuario conectado">
          <span className="app-shell__session-dot" aria-hidden="true" />
          <div>
            <p className="app-shell__session-status">Conectado</p>
            <p className="app-shell__session-user">Usuario: {currentUser}</p>
          </div>
        </div>
      </header>

      <main className="app-shell__main">{children}</main>
    </div>
  )
}

export default AppShell
