import Keycloak from "keycloak-js";
import type { ReactNode } from "react";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { setTokenGetter } from "../services/api";

// Configuration from environment
const keycloakConfig = {
  url: import.meta.env.VITE_KEYCLOAK_URL || "http://localhost:8080",
  realm: import.meta.env.VITE_KEYCLOAK_REALM || "beacon",
  clientId: import.meta.env.VITE_KEYCLOAK_CLIENT_ID || "beacon-library",
};

// Keycloak instance - use singleton pattern
let keycloak: Keycloak | null = null;
let isInitializing = false;
let isInitialized = false;

function getKeycloakInstance(): Keycloak {
  if (!keycloak) {
    keycloak = new Keycloak(keycloakConfig);
  }
  return keycloak;
}

// User interface
export interface User {
  id: string;
  username: string;
  email?: string;
  name?: string;
  roles: string[];
  isAdmin: boolean;
  isGuest: boolean;
}

// Auth context interface
interface AuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  user: User | null;
  token: string | null;
  login: () => Promise<void>;
  logout: () => Promise<void>;
  refreshToken: () => Promise<boolean>;
  hasRole: (role: string) => boolean;
  hasAnyRole: (roles: string[]) => boolean;
}

// Create context
const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Parse user from Keycloak token
function parseUser(kc: Keycloak): User | null {
  if (!kc.authenticated || !kc.tokenParsed) {
    return null;
  }

  const token = kc.tokenParsed as Record<string, unknown>;
  const realmAccess = (token.realm_access as { roles?: string[] }) || {};
  const resourceAccess =
    (token.resource_access as Record<string, { roles?: string[] }>) || {};
  const clientAccess = resourceAccess[keycloakConfig.clientId] || {};

  const roles = [...(realmAccess.roles || []), ...(clientAccess.roles || [])];

  return {
    id: token.sub as string,
    username: (token.preferred_username as string) || "",
    email: token.email as string | undefined,
    name: token.name as string | undefined,
    roles,
    isAdmin: roles.includes("library-admin"),
    isGuest: roles.includes("guest") || token.azp === "beacon-library-guest",
  };
}

// Auth Provider component
interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Initialize Keycloak
  useEffect(() => {
    const initKeycloak = async () => {
      // Prevent double initialization
      if (isInitializing || isInitialized) {
        return;
      }

      isInitializing = true;

      const kc = getKeycloakInstance();

      // Set up the token getter for API client - returns a function that gets current token
      setTokenGetter(() => () => kc.token || null);

      // Skip if already authenticated
      if (kc.authenticated) {
        setIsAuthenticated(true);
        setUser(parseUser(kc));
        setToken(kc.token || null);
        setIsLoading(false);
        isInitializing = false;
        isInitialized = true;
        return;
      }

      try {
        const authenticated = await kc.init({
          onLoad: "check-sso",
          checkLoginIframe: false,
          pkceMethod: "S256",
        });

        setIsAuthenticated(authenticated);

        if (authenticated) {
          setUser(parseUser(kc));
          setToken(kc.token || null);
        }

        isInitialized = true;
      } catch (error) {
        console.error("Keycloak initialization failed:", error);
        setError(error instanceof Error ? error.message : "Authentication initialization failed");
        // Don't block the app if Keycloak fails to initialize
        setIsAuthenticated(false);
      } finally {
        setIsLoading(false);
        isInitializing = false;
      }
    };

    initKeycloak();

    const kc = getKeycloakInstance();

    // Token refresh handler
    kc.onTokenExpired = () => {
      kc.updateToken(30)
        .then((refreshed) => {
          if (refreshed) {
            setToken(kc.token || null);
          }
        })
        .catch(() => {
          console.error("Failed to refresh token");
          setIsAuthenticated(false);
          setUser(null);
          setToken(null);
        });
    };

    // Auth state change handler
    kc.onAuthSuccess = () => {
      setIsAuthenticated(true);
      setUser(parseUser(kc));
      setToken(kc.token || null);
      setError(null);
    };

    kc.onAuthLogout = () => {
      setIsAuthenticated(false);
      setUser(null);
      setToken(null);
    };

    return () => {
      kc.onTokenExpired = undefined;
      kc.onAuthSuccess = undefined;
      kc.onAuthLogout = undefined;
    };
  }, []);

  // Login function
  const login = useCallback(async () => {
    try {
      await getKeycloakInstance().login({
        redirectUri: window.location.origin,
      });
    } catch (error) {
      console.error("Login failed:", error);
      throw error;
    }
  }, []);

  // Logout function
  const logout = useCallback(async () => {
    try {
      await getKeycloakInstance().logout({
        redirectUri: window.location.origin,
      });
    } catch (error) {
      console.error("Logout failed:", error);
      throw error;
    }
  }, []);

  // Refresh token function
  const refreshToken = useCallback(async (): Promise<boolean> => {
    try {
      const kc = getKeycloakInstance();
      const refreshed = await kc.updateToken(30);
      if (refreshed) {
        setToken(kc.token || null);
      }
      return refreshed;
    } catch (error) {
      console.error("Token refresh failed:", error);
      return false;
    }
  }, []);

  // Role check functions
  const hasRole = useCallback(
    (role: string): boolean => {
      return user?.roles.includes(role) || false;
    },
    [user]
  );

  const hasAnyRole = useCallback(
    (roles: string[]): boolean => {
      return roles.some((role) => user?.roles.includes(role)) || false;
    },
    [user]
  );

  const value: AuthContextType = {
    isAuthenticated,
    isLoading,
    user,
    token,
    login,
    logout,
    refreshToken,
    hasRole,
    hasAnyRole,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// Custom hook to use auth context
export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);

  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }

  return context;
}

// HOC for protected routes
interface RequireAuthProps {
  children: ReactNode;
  roles?: string[];
  fallback?: ReactNode;
}

export function RequireAuth({ children, roles, fallback }: RequireAuthProps) {
  const { isAuthenticated, isLoading, hasAnyRole, login } = useAuth();

  if (isLoading) {
    return fallback || <div>Loading...</div>;
  }

  if (!isAuthenticated) {
    // Trigger login
    login();
    return fallback || <div>Redirecting to login...</div>;
  }

  if (roles && roles.length > 0 && !hasAnyRole(roles)) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen">
        <h1 className="text-2xl font-bold text-red-600">Access Denied</h1>
        <p className="text-gray-600 mt-2">
          You don't have permission to access this page.
        </p>
      </div>
    );
  }

  return <>{children}</>;
}

// Export Keycloak getter function for direct access if needed
export { getKeycloakInstance };
