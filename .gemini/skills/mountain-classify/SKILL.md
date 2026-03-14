# Mountain Classify

This skill provides a high-reliability workflow for launching and managing the interactive React-based classifier used to label webcam captures of Mount Rainier.

## Workflow

### 1. Check for Active Server
Before launching a new instance, check if the classifier is already running.
- Use `mcp_bash-mcp_list_background` to look for processes named `classifier-backend` or `classifier-frontend`.
- If found, provide the URL: http://localhost:5173

### 2. Launching the Classifier
If no server is active, perform the following steps:

1.  **Resolve Data Root**: Ask the user for the data directory or use the default `data/`.
2.  **Nuclear Cleanup**: Ensure ports 8000 (backend) and 5173 (frontend) are clear.
    - `lsof -ti:8000,5173 | xargs kill -9`
3.  **Launch via bash-mcp**:
    - **Backend**: 
        - name: `classifier-backend`
        - command: `MOUNTAIN_DATA_ROOT="<data_root>" .venv/bin/python tools/classifier_server.py`
    - **Frontend**:
        - name: `classifier-frontend`
        - command: `npm run dev -- --port 5173 --strictPort`
        - cwd: `ui/`

### 3. Verification
After launching, verify the backend is responsive.
- Polling: Use `curl -I http://localhost:8000/api/stats` until successful (status 200).
- Provide the link to the user: http://localhost:5173

### 4. Progress Reporting
Read `labels.yaml` in the data root to report current progress.
- Path: `<data_root>/labels.yaml`
- Display: Total labeled images and counts for Full (1), Partial (2), and Not Out (0).

## Commands

### Start Classifier
`uv run classify start [data_folder]`

### Stop Classifier
`uv run classify stop`

## Success Criteria
- Both FastAPI and Vite servers are managed by `bash-mcp`.
- The user is provided with a clickable local link: http://localhost:5173
- Progress statistics are displayed to the user.
