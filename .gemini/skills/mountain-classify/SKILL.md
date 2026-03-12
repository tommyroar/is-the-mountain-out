---
name: mountain-classify
description: Launch and manage the interactive mountain visibility classification notebook. Use when the user wants to 'classify' images, label the mountain as out/not out, or resume a labeling session. Leverages bash-mcp for persistent server management.
---

# Mountain Classify

This skill provides a high-reliability workflow for launching and managing the interactive classification notebook (`classify.ipynb`) used to label webcam captures of Mount Rainier.

## Workflow

### 1. Check for Active Server
Before launching a new instance, always check if a server is already running on port 8890.
- Use `mcp_bash-mcp_list_background` to look for a process named `mountain-classifier`.
- If found, provide the URL: http://127.0.0.1:8890/notebooks/classify.ipynb

### 2. Launching the Server
If no server is active, perform the following steps:

1.  **Resolve Data Root**: Ask the user for the data directory or use the default `data/`.
2.  **Nuclear Cleanup**: Ensure port 8890 is clear by running `pkill -9 -f notebook` and `lsof -ti:8890 | xargs kill -9` using `run_shell_command`.
3.  **Launch via bash-mcp**: Use `mcp_bash-mcp_run_background` with:
    - **name**: `mountain-classifier`
    - **command**: `MOUNTAIN_DATA_ROOT="<data_root>" .venv/bin/python -m notebook --no-browser --port=8890 --ServerApp.token='' --ServerApp.password='' --ServerApp.ip=0.0.0.0`
    - **cwd**: Current project root.

### 3. Verification
After launching, verify the server is responsive before providing the link to the user.
- Polling: Use `run_shell_command` to execute a `curl -I http://127.0.0.1:8890/tree` every second for up to 15 seconds.
- Status: A status code of `200` or `405` indicates success.

### 4. Resuming the Session
Read the `classifier_state.json` file in the selected data root to determine the current progress.
- Path: `<data_root>/classifier_state.json`
- Information: Display the `last_index` value to the user so they know where they are resuming from.

## Commands

### Stop the Classifier
To stop the server and cleanup:
1.  Use `mcp_bash-mcp_kill_background` with name `mountain-classifier`.
2.  Optionally run `pkill -9 -f notebook` to be certain.

## Success Criteria
- The server is managed by `bash-mcp`.
- The user is provided with a clickable link: http://127.0.0.1:8890/notebooks/classify.ipynb
- The user knows their total progress and resume point.
