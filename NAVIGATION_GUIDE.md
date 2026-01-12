# Navigation Guide - Beacon Library

## How to View Your Uploaded Files

### Quick Summary
Files are uploaded via the **Catalog** page but are viewed via the **Explorer** page.

### Step-by-Step Guide

#### Method 1: Using the "View Files" Button (Recommended)
1. Go to the **Catalog** page
2. Select a library from the dropdown
3. Upload your files (drag & drop or click to browse)
4. After successful upload, click the **"View Files"** button that appears
5. You'll be taken to the **Explorer** page where you can see all files

#### Method 2: Via the Libraries Page
1. Go to the **Libraries** page
2. Click on any library card
3. You'll be taken to the **Explorer** page for that library
4. All uploaded files will be visible here

### Page Descriptions

#### Catalog Page (`/catalog`)
- **Purpose**: Quick file upload interface
- **Features**:
  - Select target library
  - Drag & drop file upload
  - Upload progress tracking
  - "View Files" button appears after successful uploads

#### Libraries Page (`/libraries`)
- **Purpose**: Manage and browse libraries
- **Features**:
  - View all libraries as cards
  - Create new libraries
  - Access library settings
  - Click any card to open the Explorer

#### Explorer Page (`/libraries/{id}`)
- **Purpose**: Browse and manage files within a library
- **Features**:
  - Tree view sidebar for folder navigation
  - File list with details (name, size, date, type)
  - Upload button in toolbar
  - Sorting and view options (list/grid)
  - Breadcrumb navigation
  - File operations (upload, download, delete, etc.)

### Recent Fixes

#### Upload Button Connection
The Upload button in the Explorer toolbar was previously not functional. It has been fixed to:
- Open the upload dialog when clicked
- Support drag & drop
- Show upload progress
- Automatically refresh the file list after upload

#### Catalog Page Enhancement
Added "View Files" button that appears after successful uploads to quickly navigate to the Explorer page.

### API Verification

The backend API is working correctly:

```bash
# Test browse endpoint
curl "http://localhost:8181/api/libraries/{library-id}/browse?path=/"

# Example response shows uploaded files:
{
  "items": [
    {
      "id": "7fbb46d7-4321-429b-9364-30d22265c496",
      "name": "CD via Makefile (Dev maison).md",
      "type": "file",
      "size_bytes": 7427,
      "content_type": "text/markdown",
      ...
    }
  ],
  ...
}
```

### Troubleshooting

If you don't see your files:

1. **Verify you're on the Explorer page**
   - URL should be: `/libraries/{library-id}`
   - Not the Catalog page (`/catalog`)

2. **Check the correct library**
   - Make sure you're viewing the library where you uploaded files
   - Check the library name in the header

3. **Try refreshing**
   - Click the refresh button in the toolbar
   - Or press F5 to reload the page

4. **Verify upload succeeded**
   - Check for green checkmarks on the Catalog page
   - Look for "Complete" status in upload list

5. **Check browser console**
   - Open Developer Tools (F12)
   - Look for any error messages
   - Check Network tab for API calls

### Architecture Notes

#### Frontend Routes
- `/` - Home page
- `/catalog` - Upload interface
- `/libraries` - Library management
- `/libraries/{id}` - File explorer for specific library
- `/search` - Search interface
- `/settings` - Application settings

#### API Endpoints
- `GET /api/libraries` - List all libraries
- `GET /api/libraries/{id}/browse` - Browse library contents
- `POST /api/files/upload/init` - Initialize file upload
- `POST /api/files/upload/part` - Upload file chunk
- `POST /api/files/upload/complete` - Complete upload

#### Component Hierarchy
```
Explorer Page
├── FileExplorer Component
│   ├── Toolbar (with Upload button)
│   ├── Breadcrumb
│   ├── TreeView (sidebar)
│   ├── FileList
│   └── UploadDialog
```
