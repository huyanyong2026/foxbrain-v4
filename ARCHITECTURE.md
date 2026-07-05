# Architecture

FoxBrain is currently a cloud-deployable Python portal with Docker Compose infrastructure.

## Runtime

- `foxbrain-web`: main web portal.
- `foxbrain-api`: API process using the same application image.
- `foxbrain-worker`: scheduled background jobs.
- `postgres`: production database foundation.
- `redis`: cache and job foundation.
- `minio`: document storage foundation.
- `qdrant`: vector search foundation.
- `nginx`: public HTTP/HTTPS entry.
- Optional: n8n, Dify placeholder, Wiki.js, Ollama.

## Application Layers

- Login and role permissions.
- Archive objects.
- Knowledge center.
- SAP sync.
- AI CEO, Jarvis and agent framework.
- Workflow, task, reporting, memory and graph engines.
- V5/V6 operating system layer, action board and autonomous worker.

## Safety Rule

AI can draft and suggest. Sensitive business actions require human approval.

