# Bug Fix Summary - API Route Double Prefix Issue

## Issue Description

When accessing the Explorer page at `/libraries/{id}`, users received a "library not found" error, even though:
- The library existed in the database
- Files were successfully uploaded
- The API endpoint worked when tested directly

## Root Cause

The frontend service layer (`frontend/src/services/files.ts`) had **duplicate `/api` prefixes** in API calls:

1. The `apiClient` was configured with `baseURL: '/api'` (from `config.api.baseUrl`)
2. Individual API functions were adding `/api/` prefix again in their paths
3. This resulted in requests like: `/api/api/libraries/{id}` instead of `/api/libraries/{id}`
4. The backend returned 404 because the route didn't exist with the double prefix

## Evidence from Logs

```
# Failed requests with double prefix
GET /api/api/libraries/6085777d-c108-450f-960e-00cf4c99d8c4 HTTP/1.1" 404 Not Found

# Working request (direct curl test)
GET /api/libraries/6085777d-c108-450f-960e-00cf4c99d8c4 HTTP/1.1" 200 OK
```

## Files Fixed

**File:** `frontend/src/services/files.ts`

### Functions Updated (removed `/api` prefix from paths):

1. ✅ `getLibrary()` - Line 156
   - Changed: `/api/libraries/${libraryId}` → `/libraries/${libraryId}`

2. ✅ `updateLibrary()` - Line 177
   - Changed: `/api/libraries/${libraryId}` → `/libraries/${libraryId}`

3. ✅ `deleteLibrary()` - Line 182
   - Changed: `/api/libraries/${libraryId}` → `/libraries/${libraryId}`

4. ✅ `browseLibrary()` - Line 200
   - Changed: `/api/libraries/${libraryId}/browse` → `/libraries/${libraryId}/browse`

5. ✅ `createDirectory()` - Line 222
   - Changed: `/api/libraries/${libraryId}/directories` → `/libraries/${libraryId}/directories`

6. ✅ `renameDirectory()` - Line 234
   - Changed: `/api/libraries/${libraryId}/directories/${directoryId}` → `/libraries/${libraryId}/directories/${directoryId}`

7. ✅ `moveDirectory()` - Line 246
   - Changed: `/api/libraries/${libraryId}/directories/${directoryId}/move` → `/libraries/${libraryId}/directories/${directoryId}/move`

8. ✅ `deleteDirectory()` - Line 257
   - Changed: `/api/libraries/${libraryId}/directories/${directoryId}` → `/libraries/${libraryId}/directories/${directoryId}`

9. ✅ `getFile()` - Line 266
   - Changed: `/api/files/${fileId}` → `/files/${fileId}`

10. ✅ `renameFile()` - Line 274
    - Changed: `/api/files/${fileId}` → `/files/${fileId}`

11. ✅ `deleteFile()` - Line 279
    - Changed: `/api/files/${fileId}` → `/files/${fileId}`

12. ✅ `downloadFile()` - Line 283
    - Changed: `/api/files/${fileId}/download` → `/files/${fileId}/download`

## Why Some Functions Worked

Functions like `listLibraries()`, `uploadFile()`, and upload-related functions worked because they were already using the correct paths **without** the `/api/` prefix:

```typescript
// Already correct (no /api prefix)
await apiClient.get('/libraries', { params: { page, page_size: pageSize } });
await apiClient.post('/files/upload/init', null, { params: { ... } });
```

## Impact

This fix resolves:
- ✅ Explorer page showing "library not found"
- ✅ Browse functionality now works
- ✅ File listing will display correctly
- ✅ All library-specific operations (rename, delete, etc.)
- ✅ All file operations (view, rename, delete, download)
- ✅ Directory operations (create, rename, move, delete)

## Testing

After the fix is deployed, test the following:

### 1. Navigate to Explorer
```
URL: https://beacon-library.famillelallier.net/libraries/6085777d-c108-450f-960e-00cf4c99d8c4
Expected: See the library name and file list
```

### 2. Check Browser Network Tab
```
Request: GET /api/libraries/{id}
Status: 200 OK (not 404)
```

### 3. Verify File List
```
Should see uploaded files:
- CD via Makefile (Dev maison).md
- Exigences fonctionnelles — Container Docker NGINX.md
```

## Additional Fixes Made in This Session

### 1. Upload Dialog Integration
- Connected the Upload button in Explorer toolbar to UploadDialog component
- Added automatic refresh after upload completion

### 2. Catalog Page Navigation
- Added "View Files" button that appears after successful uploads
- Button navigates directly to Explorer page for the selected library

### 3. Documentation
- Created `NAVIGATION_GUIDE.md` with user instructions
- This `BUG_FIX_SUMMARY.md` for technical details

## Prevention

To prevent this issue in the future:

1. **Standardize API Path Pattern:**
   - All paths in service functions should be relative to `baseURL`
   - Never include `/api/` prefix in individual function calls
   - Document this in code comments

2. **Add Lint Rule:**
   Consider adding an ESLint rule to catch hardcoded `/api/` paths:
   ```js
   // In .eslintrc.js
   {
     "rules": {
       "no-restricted-syntax": ["error", {
         "selector": "Literal[value=/^\\/api\\//]",
         "message": "Don't use /api/ prefix in API calls - it's already in baseURL"
       }]
     }
   }
   ```

3. **Integration Tests:**
   Add tests that verify actual API URLs being called

## Deployment Notes

- Changes are automatically hot-reloaded in development via Vite HMR
- No backend changes required
- No database migrations needed
- No environment variable changes needed

## Verification Commands

```bash
# Check the fixed endpoint works
curl "http://localhost:8181/api/libraries/6085777d-c108-450f-960e-00cf4c99d8c4"

# Check browse endpoint
curl "http://localhost:8181/api/libraries/6085777d-c108-450f-960e-00cf4c99d8c4/browse?path=/"

# Watch backend logs for correct requests
docker compose logs -f backend | grep "GET /api/"
```

## Status

- [x] Issue identified
- [x] Root cause determined
- [x] Fix implemented (12 functions)
- [x] Hot-reload verified
- [ ] User confirmation pending
- [ ] Additional testing recommended

## Date
2026-01-11
