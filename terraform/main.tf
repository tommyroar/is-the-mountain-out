terraform {
  required_providers {
    nomad = {
      source  = "hashicorp/nomad"
      version = "~> 2.0"
    }
  }
}

provider "nomad" {
  address = "http://127.0.0.1:4646"
}

resource "nomad_job" "training" {
  jobspec = <<EOT
job "mountain-training" {
  datacenters = ["dc1"]
  type        = "batch"
  
  group "ml" {
    task "train" {
      driver = "raw_exec"
      
      config {
        command = "/bin/bash"
        args    = ["-c", "cd /Users/tommydoerr/dev/is-the-mountain-out && uv run training batch --labels data/labels.yaml --epochs 10 --fresh"]
      }
      
      env {
        # Optional: any necessary environment variables
      }
      
      resources {
        cpu    = 4000
        memory = 8192
      }
    }
  }
}
EOT
}
