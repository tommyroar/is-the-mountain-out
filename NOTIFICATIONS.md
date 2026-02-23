# NOTIFICATIONS.md - System Notifications

This project uses **ntfy.sh** to deliver real-time push notifications to mobile devices (iOS/Android).

## Setup
1. Install the **ntfy** app on your device.
2. Subscribe to the private topic UUID stored in `ntfy.key` (this file is ignored by git to maintain privacy).
3. Ensure `ntfy.key` exists in the root directory.

## Notification Schema

### 🏔️ Collection Plan
- **Event:** Plan Started
  - **Message:** "Starting new collection plan with [N] steps."
  - **Title:** "🏔️ Collection Started"
- **Event:** Progress Update (Every 10 steps)
  - **Message:** "Progress: [X]/[N] captures complete."
  - **Title:** "🏔️ Collection Update"
- **Event:** Plan Complete
  - **Message:** "✅ Collection plan complete! [N] steps processed."
  - **Title:** "🏔️ Collection Finished"
  - **Priority:** High

### 🏔️ Detection (Future)
- **Event:** Mountain is OUT
  - **Message:** "Mount Rainier is visible! Confidence: [X]%"
  - **Title:** "🏔️ THE MOUNTAIN IS OUT"
  - **Priority:** Urgent
