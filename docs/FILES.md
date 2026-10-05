# Files and object storage

The application uses an object-storage abstraction for files, attachments, thumbnails, and previews. MinIO is the self-hosted default and is designed to expose the S3-compatible interface.

## Security requirements

- file size controls and MIME validation
- checksum verification
- signed URLs for uploads/downloads
- private buckets for sensitive collections
- authorization enforcement before exposing file metadata or content

Large binary workloads are isolated from FastAPI request handling and processed asynchronously through workers.
