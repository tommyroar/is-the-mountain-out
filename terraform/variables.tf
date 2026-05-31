variable "cloudflare_api_token" {
  description = "Cloudflare API token with R2 permissions"
  type        = string
  sensitive   = true
}

variable "cloudflare_account_id" {
  description = "Cloudflare account ID"
  type        = string
}

# ---------- Inference Worker + Container ----------

variable "github_owner" {
  description = "GitHub owner that backs the container image registry (ghcr.io)"
  type        = string
  default     = "tommyroar"
}

variable "github_repo" {
  description = "GitHub repo that publishes the inference container image to GHCR"
  type        = string
  default     = "is-the-mountain-out"
}

variable "inference_image_tag" {
  description = "Container image tag (typically a git SHA) for ghcr.io/<owner>/<repo>/inference"
  type        = string
  default     = "latest"
}

variable "r2_access_key_id" {
  description = "R2 S3-API access key ID. Pushed to the Worker as a secret; the container reads it as an env var to pull the latest checkpoint from R2 on startup."
  type        = string
  sensitive   = true
}

variable "r2_secret_access_key" {
  description = "R2 S3-API secret access key. Pushed to the Worker as a secret; the container reads it as an env var to pull the latest checkpoint from R2 on startup."
  type        = string
  sensitive   = true
}

variable "ntfy_topic" {
  description = "ntfy.sh topic UUID the Worker publishes mountain-out notifications to. Pushed to the Worker as a secret. The topic value is the secret on ntfy.sh — anyone who knows it can publish to or subscribe from it."
  type        = string
  sensitive   = true
}
