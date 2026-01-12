# MinIO Connectivity Fix - Summary

## Problem
Backend was unable to upload files to MinIO, resulting in the error:
```
botocore.exceptions.EndpointConnectionError: Could not connect to the endpoint URL: "http://beacon-minio1:9000/..."
```

## Root Cause
The **MinIO containers** and **Beacon-Library backend** were not on the same Docker network:
- **Beacon-Library backend**: Connected to `beacon_minio_net` network ✅
- **MinIO containers** (beacon-minio1/2/3): Only on `beacon_monitoring_net` and `beacon_nginx_net` ❌

The MinIO containers could not be reached by the backend because they weren't connected to the `beacon_minio_net` network.

## Solution
Updated the Beacon project's `docker-compose.yml` to:

1. **Added minio_net network definition:**
   ```yaml
   minio_net:
     external: true
     name: beacon_minio_net
   ```

2. **Connected MinIO containers to minio_net:**
   ```yaml
   minio1:
     networks:
       - monitoring_net
       - nginx_net
       - minio_net  # ← Added
   ```
   (Same for minio2 and minio3)

3. **Restarted MinIO containers:**
   ```bash
   docker-compose --profile monitoring up -d minio1 minio2 minio3
   ```

## Testing Results

### Before Fix:
```
❌ EndpointConnectionError: Could not connect to beacon-minio1:9000
```

### After Fix:
```bash
$ docker-compose exec backend curl http://beacon-minio1:9000/minio/health/live
✅ 200 OK
```

## Verification

### Check MinIO networks:
```bash
$ docker inspect beacon-minio1 --format '{{range $k, $v := .NetworkSettings.Networks}}{{$k}} {{end}}'
beacon_minio_net beacon_monitoring_net beacon_nginx_net  ✅
```

### Check Backend can reach MinIO:
```bash
$ docker-compose exec backend curl http://beacon-minio1:9000/minio/health/live
✅ HTTP 200
```

## Architecture

```
┌─────────────────────────────────────────────┐
│ Beacon Project (Infrastructure)             │
│                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │ minio1   │  │ minio2   │  │ minio3   │ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘ │
│       │            │            │         │
│       └────────────┴────────────┘         │
│                    │                       │
│         ┌──────────┴───────────┐          │
│         │   beacon_minio_net   │◄─────────┼─────┐
│         └──────────────────────┘          │     │
└─────────────────────────────────────────────┘     │
                                                    │
┌───────────────────────────────────────────────────┤
│ Beacon-Library Project                            │
│                                                    │
│  ┌──────────────────────────┐                     │
│  │  Backend (FastAPI)       │─────────────────────┘
│  │  - Uploads files         │
│  │  - Connects to MinIO     │
│  └──────────────────────────┘
│
└─────────────────────────────────────────────┘
```

## Files Modified

1. **`/Users/nicolaslallier/GIT/Beacon/docker-compose.yml`**:
   - Added `minio_net` network definition (external)
   - Added `minio_net` to minio1, minio2, minio3 networks

## How to Upload Files

### Via Frontend:
1. Open http://localhost:8181
2. Navigate to the Library page
3. Click "Upload File"
4. Select a file and upload

### Via API:
```bash
# Initialize upload
curl -X POST 'http://localhost:8181/api/files/upload/init' \
  -H 'Content-Type: application/json' \
  -d '{
    "library_id": "6085777d-c108-450f-960e-00cf4c99d8c4",
    "filename": "test.txt",
    "size_bytes": 18,
    "mime_type": "text/plain"
  }'
```

## Current Status

✅ **Backend** → **MinIO** connectivity working  
✅ **MinIO cluster** (3 nodes) running and healthy  
✅ **File uploads** ready to work  
✅ **Network configuration** correct  

## Next Steps

The file upload functionality should now work properly! You can test it by:
1. Opening the frontend at http://localhost:8181
2. Navigating to a library
3. Uploading a file

The file will be stored in the MinIO cluster and metadata will be saved to the PostgreSQL database.

## Troubleshooting

### If uploads still fail:

1. **Check MinIO health:**
   ```bash
   docker-compose exec backend curl http://beacon-minio1:9000/minio/health/live
   ```
   Should return: `200`

2. **Check MinIO cluster status:**
   ```bash
   cd /Users/nicolaslallier/GIT/Beacon
   docker-compose --profile monitoring ps | grep minio
   ```
   All should be "Up"

3. **Check backend logs:**
   ```bash
   docker-compose logs --tail=50 backend | grep -i minio
   ```

4. **Verify network connectivity:**
   ```bash
   docker inspect beacon-minio1 --format '{{range $k, $v := .NetworkSettings.Networks}}{{$k}} {{end}}'
   ```
   Should include: `beacon_minio_net`

## MinIO Access

- **Console UI**: Available through Beacon nginx proxy
- **S3 API**: `http://beacon-minio1:9000` (internal)
- **Credentials**: 
  - Access Key: `minioadmin` (default)
  - Secret Key: `minioadmin` (default)

Change these in production via environment variables in the Beacon `.env` file.
