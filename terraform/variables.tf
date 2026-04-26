variable "cloudflare_api_token" {
  description = "Cloudflare API token with R2 permissions"
  type        = string
  sensitive   = true
}

variable "cloudflare_account_id" {
  description = "Cloudflare account ID"
  type        = string
}

# ---------- Inference Worker + Container (Phase 1) ----------

variable "github_owner" {
  description = "GitHub owner that backs the repo the Worker pushes inference results to"
  type        = string
  default     = "tommyroar"
}

variable "github_repo" {
  description = "GitHub repo the Worker pushes inference results to"
  type        = string
  default     = "is-the-mountain-out"
}

variable "github_branch" {
  description = "Branch the Worker commits state.json + history.jsonl to"
  type        = string
  default     = "main"
}

variable "github_pat" {
  description = "Fine-grained GitHub PAT with Contents: read+write on the target repo. Stored as a Worker secret."
  type        = string
  sensitive   = true
}

variable "inference_image_tag" {
  description = "Container image tag (typically a git SHA) for ghcr.io/<owner>/<repo>/inference"
  type        = string
  default     = "latest"
}
