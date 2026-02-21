class MountainTrainer < Formula
  desc "Iterative LoRA training for Mount Rainier"
  homepage "https://github.com/tommyroar/is-the-mountain-out"
  url "file://#{Dir.pwd}"
  version "0.1.0"

  depends_on "uv"

  def install
    libexec.install Dir["*"]
  end

  service do
    run ["uv", "run", "--project", libexec/"train", "training", "live", "--config", libexec/"train/config.toml", "--mountain", libexec/"mountain.toml"]
    run_type :interval
    interval 1800
    working_dir libexec
    log_path "/tmp/mountain_trainer.out"
    error_log_path "/tmp/mountain_trainer.err"
  end

  def caveats
    <<~EOS
      To install this local service, run:
        brew install --formula ./mountain-trainer.rb
      
      To start the training loop:
        brew services start mountain-trainer
    EOS
  end
end
