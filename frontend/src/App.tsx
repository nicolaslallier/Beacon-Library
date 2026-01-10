import { useEffect } from 'react';
import { Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Home from './pages/Home';
import Libraries from './pages/Libraries';
import Explorer from './pages/Explorer';
import Search from './pages/Search';
import Settings from './pages/Settings';
import About from './pages/About';
import ShareAccess from './pages/ShareAccess';
import { useAuth } from './hooks/useAuth';
import { setAuthToken } from './services/files';

function App() {
  const { token } = useAuth();

  // Sync auth token with API client
  useEffect(() => {
    setAuthToken(token);
  }, [token]);

  return (
    <Routes>
      {/* Public routes */}
      <Route element={<Layout />}>
        <Route path="/" element={<Home />} />
        <Route path="/about" element={<About />} />
      </Route>

      {/* Public share access (no auth required) */}
      <Route path="/share/:token" element={<ShareAccess />} />

      {/* Protected routes */}
      <Route path="/libraries" element={<Libraries />} />
      <Route path="/libraries/:libraryId" element={<Explorer />} />
      <Route path="/search" element={<Search />} />
      <Route path="/settings" element={<Settings />} />
    </Routes>
  );
}

export default App;
