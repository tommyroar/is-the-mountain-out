variable "session_id" {
  type    = string
  default = ""
}

job "mountain-capture-single" {
  datacenters = ["dc1"]
  type        = "batch"

  group "capture" {
    count = 1
    
    task "run-once" {
      driver = "raw_exec"

      env {
        PATH = "/Users/tommydoerr/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
      }

      config {
        command = "/bin/bash"
        args    = [
          "-c",
          "cd /Users/tommydoerr/dev/is-the-mountain-out && SID=\"${var.session_id}\" && if [ -z \"$SID\" ]; then SID=\"manual-$(date +%s)\"; fi && uv run collect once --session-id $SID"
        ]
      }

      resources {
        cpu    = 200
        memory = 256
      }
    }
  }
}
