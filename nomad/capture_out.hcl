job "mountain-capture-out" {
  datacenters = ["dc1"]
  type        = "batch"

  group "capture" {
    count = 1

    task "run-out-captures" {
      driver = "raw_exec"

      env {
        PATH = "/Users/tommydoerr/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
      }

      config {
        command = "/bin/bash"
        args    = [
          "-c",
          "cd /Users/tommydoerr/dev/is-the-mountain-out && python3 tools/capture_out.py"
        ]
      }

      resources {
        cpu    = 200
        memory = 256
      }
    }
  }
}
