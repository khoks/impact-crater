"""HTTP + WebSocket API surface (mounted in `impact_crater.app.create_app`).

Routers:
  - setup     /api/setup/...      first-time-setup wizard
  - settings  /api/settings/...   API keys, caps, cast / privacy settings
  - projects  /api/projects/...   project CRUD
  - jobs      /api/jobs/...       headless / render / async submit, poll, and the
                                  job-progress WebSocket `/api/jobs/ws/{job_id}`
  - folder    /api/folder/...     folder scan
  - effort    /api/...            effort-level estimate
  - snapshots /api/snapshots/...  plan, render, refine, publish-preview data
  - media     /api/media/...      thumbnails and renditions
  - feedback  /api/feedback/...   decision-level feedback (A-023)
  - workplan  /api/workplan/...   in-app tracker + priority overrides (A-024)
  - persons   /api/persons/...    person library (N-008)
  - publish   /api/...            publish + connector status + audit
  - profile   /api/profile/...    cross-project profile (N-010, no emitters yet)
"""
