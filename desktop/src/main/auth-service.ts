/**
 * Auth Service - Handles authentication with Beacon Library server
 */

import { shell } from 'electron';
import * as http from 'http';
import * as url from 'url';
import axios from 'axios';
import Store from 'electron-store';

interface AuthStatus {
  isAuthenticated: boolean;
  user: {
    id: string;
    email: string;
    name: string;
  } | null;
  serverUrl: string | null;
}

interface TokenData {
  accessToken: string;
  refreshToken: string;
  expiresAt: number;
}

export class AuthService {
  private store: Store;
  private tokenData: TokenData | null = null;
  private serverUrl: string | null = null;

  constructor(store: Store) {
    this.store = store;
    this.loadStoredAuth();
  }

  private loadStoredAuth(): void {
    const stored = this.store.get('auth') as {
      tokenData: TokenData;
      serverUrl: string;
    } | undefined;

    if (stored) {
      this.tokenData = stored.tokenData;
      this.serverUrl = stored.serverUrl;
    }
  }

  private saveAuth(): void {
    if (this.tokenData && this.serverUrl) {
      this.store.set('auth', {
        tokenData: this.tokenData,
        serverUrl: this.serverUrl,
      });
    } else {
      this.store.delete('auth');
    }
  }

  async login(serverUrl: string): Promise<boolean> {
    this.serverUrl = serverUrl;

    return new Promise((resolve, reject) => {
      // Create local server to receive OAuth callback
      const server = http.createServer(async (req, res) => {
        const parsedUrl = url.parse(req.url || '', true);

        if (parsedUrl.pathname === '/callback') {
          const code = parsedUrl.query.code as string;

          if (code) {
            try {
              // Exchange code for tokens
              const tokens = await this.exchangeCodeForTokens(code);
              this.tokenData = tokens;
              this.saveAuth();

              res.writeHead(200, { 'Content-Type': 'text/html' });
              res.end(`
                <html>
                  <head>
                    <style>
                      body {
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        height: 100vh;
                        margin: 0;
                        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
                        color: white;
                      }
                      .container {
                        text-align: center;
                        padding: 40px;
                      }
                      h1 { color: #10b981; }
                      p { color: #94a3b8; }
                    </style>
                  </head>
                  <body>
                    <div class="container">
                      <h1>✓ Authentication Successful</h1>
                      <p>You can close this window and return to the app.</p>
                    </div>
                  </body>
                </html>
              `);

              server.close();
              resolve(true);

            } catch (error) {
              res.writeHead(500, { 'Content-Type': 'text/html' });
              res.end('<h1>Authentication Failed</h1>');
              server.close();
              reject(error);
            }
          } else {
            res.writeHead(400, { 'Content-Type': 'text/html' });
            res.end('<h1>Missing authorization code</h1>');
            server.close();
            reject(new Error('Missing authorization code'));
          }
        }
      });

      // Start server on random port
      server.listen(0, '127.0.0.1', () => {
        const address = server.address();
        if (typeof address === 'object' && address) {
          const port = address.port;
          const redirectUri = `http://127.0.0.1:${port}/callback`;

          // Get Keycloak auth URL from server
          this.getAuthUrl(redirectUri).then((authUrl) => {
            // Open browser for authentication
            shell.openExternal(authUrl);
          }).catch((error) => {
            server.close();
            reject(error);
          });
        }
      });

      // Timeout after 5 minutes
      setTimeout(() => {
        server.close();
        reject(new Error('Authentication timed out'));
      }, 300000);
    });
  }

  private async getAuthUrl(redirectUri: string): Promise<string> {
    const response = await axios.get(`${this.serverUrl}/api/auth/login-url`, {
      params: { redirect_uri: redirectUri },
    });
    return response.data.url;
  }

  private async exchangeCodeForTokens(code: string): Promise<TokenData> {
    const response = await axios.post(`${this.serverUrl}/api/auth/token`, {
      code,
      grant_type: 'authorization_code',
    });

    return {
      accessToken: response.data.access_token,
      refreshToken: response.data.refresh_token,
      expiresAt: Date.now() + (response.data.expires_in * 1000),
    };
  }

  async refreshTokens(): Promise<boolean> {
    if (!this.tokenData?.refreshToken || !this.serverUrl) {
      return false;
    }

    try {
      const response = await axios.post(`${this.serverUrl}/api/auth/token`, {
        refresh_token: this.tokenData.refreshToken,
        grant_type: 'refresh_token',
      });

      this.tokenData = {
        accessToken: response.data.access_token,
        refreshToken: response.data.refresh_token || this.tokenData.refreshToken,
        expiresAt: Date.now() + (response.data.expires_in * 1000),
      };

      this.saveAuth();
      return true;

    } catch (error) {
      console.error('Failed to refresh tokens:', error);
      return false;
    }
  }

  async getToken(): Promise<string | null> {
    if (!this.tokenData) {
      return null;
    }

    // Check if token is expired or about to expire
    if (Date.now() >= this.tokenData.expiresAt - 60000) {
      const refreshed = await this.refreshTokens();
      if (!refreshed) {
        this.logout();
        return null;
      }
    }

    return this.tokenData.accessToken;
  }

  async logout(): Promise<void> {
    this.tokenData = null;
    this.store.delete('auth');
  }

  async getStatus(): Promise<AuthStatus> {
    const token = await this.getToken();

    if (!token || !this.serverUrl) {
      return {
        isAuthenticated: false,
        user: null,
        serverUrl: null,
      };
    }

    try {
      const response = await axios.get(`${this.serverUrl}/api/auth/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      return {
        isAuthenticated: true,
        user: response.data,
        serverUrl: this.serverUrl,
      };

    } catch (error) {
      return {
        isAuthenticated: false,
        user: null,
        serverUrl: this.serverUrl,
      };
    }
  }
}
