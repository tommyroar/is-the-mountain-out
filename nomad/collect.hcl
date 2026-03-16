job "mountain-collector" {
  datacenters = ["dc1"]
  type        = "service"

  group "collector" {
    count = 1

    restart {
      attempts = 3
      interval = "5m"
      delay    = "25s"
      mode     = "delay"
    }

    task "tray" {
      driver = "raw_exec"

      env {
        PATH = "/Users/tommydoerr/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
      }

      config {
        command = "/bin/bash"
        args    = [
          "-c",
          "export SESSION_ID=$(uuidgen | cut -c1-8) && cd /Users/tommydoerr/dev/is-the-mountain-out && uv run collect tray --config mountain.toml --session-id $SESSION_ID"
        ]
      }

      resources {
        cpu    = 200
        memory = 256
      }
    }
  }
}
