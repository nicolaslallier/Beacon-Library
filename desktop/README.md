# Beacon Library Desktop Sync Client

A cross-platform desktop application for synchronizing files with Beacon Library.

## Features

- **Background Sync**: Automatically keeps your local files in sync with Beacon Library
- **Selective Sync**: Choose which libraries and folders to sync
- **Offline Support**: Queue changes when offline and sync when reconnected
- **Conflict Resolution**: Intelligent handling of file conflicts
- **System Tray**: Runs quietly in the background
- **Cross-Platform**: Works on macOS, Windows, and Linux

## Installation

### From Releases

Download the latest release for your platform:
- macOS: `.dmg` or `.zip`
- Windows: `.exe` (installer) or portable
- Linux: `.AppImage` or `.deb`

### From Source

```bash
# Install dependencies
npm install

# Development mode
npm run dev

# Build for production
npm run build

# Package for distribution
npm run package
```

## Usage

### First-Time Setup

1. Launch the application
2. Enter your Beacon Library server URL
3. Click "Connect" to authenticate via your browser
4. Select a local folder for syncing
5. Choose which libraries to sync

### Sync Settings

- **Auto Sync**: Enable/disable automatic synchronization
- **Sync Interval**: How often to check for changes (default: 5 minutes)
- **Start Minimized**: Launch app minimized to system tray
- **Launch at Startup**: Start app when you log in

### Conflict Resolution

When the same file is modified both locally and remotely:
- **Keep Local**: Upload your local version
- **Keep Remote**: Download the server version
- **Keep Both**: Rename local file and download remote

## Architecture

```
desktop/
├── src/
│   ├── main/           # Main process (Electron)
│   │   ├── main.ts     # App entry point
│   │   ├── sync-service.ts
│   │   ├── auth-service.ts
│   │   └── file-watcher.ts
│   ├── preload/        # Preload scripts
│   │   └── preload.ts
│   └── renderer/       # Renderer process (UI)
│       ├── index.html
│       └── ...
├── resources/          # App icons and assets
└── package.json
```

## Development

### Prerequisites

- Node.js 18+
- npm or yarn

### Running in Development

```bash
npm run dev
```

This starts the app with hot-reload enabled.

### Building

```bash
# Build for current platform
npm run package

# Build for specific platform
npm run package:mac
npm run package:win
npm run package:linux
```

## Security

- OAuth 2.0 authentication with Keycloak
- Tokens stored securely using system keychain
- All communication over HTTPS
- No plaintext password storage

## License

MIT
