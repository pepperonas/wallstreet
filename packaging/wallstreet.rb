class Wallstreet < Formula
  desc "Fill your console with Wall Street-like news and stats"
  homepage "https://github.com/dustinkirkland/hollywood"
  url "file:///Users/martin/claude/wallstreet", using: :git, branch: "main", revision: "64e21e476d6e41b3fa94879106c766a03f4a57b4"
  version "1.27"
  license "Apache-2.0"
  head "file:///Users/martin/claude/wallstreet", using: :git, branch: "main"

  depends_on "jp2a"
  depends_on "libcaca"
  depends_on "newsboat"
  depends_on "tmux"
  uses_from_macos "python"

  def install
    bin.install "bin/wallstreet"
    (lib/"wallstreet").install Dir["lib/wallstreet/*"]
    (share/"wallstreet").install Dir["share/wallstreet/*"]
    man1.install "share/man/man1/wallstreet.1"
  end

  test do
    system "bash", "-n", bin/"wallstreet"
    assert_match "usage", shell_output("#{share}/wallstreet/wsdata 2>&1", 2).downcase
  end
end
