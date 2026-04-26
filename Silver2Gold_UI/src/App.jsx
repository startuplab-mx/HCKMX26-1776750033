import AppShell from './components/AppShell'
import HomePage from './pages/HomePage'
import './styles/app.css'

function App() {
  const currentUser = 'Asharet'

  return (
    <AppShell currentUser={currentUser}>
      <HomePage currentUser={currentUser} />
    </AppShell>
  )
}

export default App
