import { useEffect } from "react";
import { Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { useAuth, getKeycloakInstance } from "./hooks/useAuth";
import About from "./pages/About";
import Catalog from "./pages/Catalog";
import Explorer from "./pages/Explorer";
import Home from "./pages/Home";
import Libraries from "./pages/Libraries";
import Search from "./pages/Search";
import Settings from "./pages/Settings";
import ShareAccess from "./pages/ShareAccess";
import { setAuthToken, setTokenGetter } from "./services/files";

function App() {
  const { token } = useAuth();

  // Set up token getter for files service (do this once)
  useEffect(() => {
    const kc = getKeycloakInstance();
    // Return a function that always gets the current token value
    setTokenGetter(() => () => kc.token || null);
  }, []);

  // Sync auth token with API client (backward compatibility)
  useEffect(() => {
    setAuthToken(token);
  }, [token]);

  return (
    <Routes>
      {/* Public routes */}
      <Route element={<Layout />}>
        <Route path="/" element={<Home />} />
        <Route path="/about" element={<About />} />

        {/* Protected routes */}
        <Route path="/libraries" element={<Libraries />} />
        <Route path="/libraries/:libraryId" element={<Explorer />} />
        <Route path="/catalog" element={<Catalog />} />
        <Route path="/search" element={<Search />} />
        <Route path="/settings" element={<Settings />} />
      </Route>

      {/* Public share access (no auth required) */}
      <Route path="/share/:token" element={<ShareAccess />} />
    </Routes>
  );
}

export default App;
