# Homebrew formula for a personal tap. Copy it to Formula/hackterm.rb in a repo
# named Farrooss/homebrew-tap; users then run `brew install farrooss/tap/hackterm`.
class Hackterm < Formula
  desc "Cinematic fake-hacking console for your terminal"
  homepage "https://github.com/Farrooss/hackterm"
  url "https://github.com/Farrooss/hackterm/archive/refs/tags/v0.0.2.tar.gz"
  sha256 "0000000000000000000000000000000000000000000000000000000000000000"
  license "MIT"

  depends_on "python@3.14"

  def install
    rewrite_shebang detected_python_shebang, "hackterm.py"
    bin.install "hackterm.py" => "hackterm"
  end

  test do
    assert_equal "hackterm #{version}", shell_output("#{bin}/hackterm --version").strip
  end
end
