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
          <h1>Chimalli</h1>
        </div>

        <div className="app-shell__tagline">
          <p className="app-shell__tagline-title">Moderación humana de contenido en riesgo</p>
        </div>

        <div className="app-shell__session" aria-label="Usuario conectado">
          <span className="app-shell__session-dot" aria-hidden="true" />
          <div>
            <p className="app-shell__session-status">Conectado</p>
            <p className="app-shell__session-user">Usuario: {currentUser}</p>
          </div>
        </div>
      </header>

      <main className="app-shell__main" style={{ flex: 1, minHeight: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>{children}</main>
    </div>
  )
}

export default AppShell
