job "mountain-detector" {
  datacenters = ["dc1"]
  type        = "batch"

  periodic {
    crons            = ["*/15 * * * *"]
    prohibit_overlap = true
    time_zone        = "America/Los_Angeles"
  }

  group "detector" {
    count = 1

    reschedule {
      attempts  = 2
      interval  = "10m"
      delay     = "30s"
      unlimited = false
    }

    task "infer" {
      driver = "raw_exec"

      env {
        PATH = "/Users/tommydoerr/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
      }

      config {
        command = "/bin/bash"
        args    = [
          "-c",
          "cd /Users/tommydoerr/dev/is-the-mountain-out && uv run python tools/detect_mountain.py check --config mountain.toml"
        ]
      }

      resources {
        cpu    = 500
        memory = 1024
      }
    }
  }
}
