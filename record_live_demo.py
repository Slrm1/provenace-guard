"""Record real browser interaction with the running Flask API.

Requires: pip install -r requirements.txt -r video-requirements.txt, and
an installed Chromium browser. Set PLAYWRIGHT_CHROMIUM to its chrome.exe path
if Playwright cannot find one automatically.
"""

import os
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

import imageio_ffmpeg
from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server

from app import create_app


ROOT = Path(__file__).parent


def main():
    tests = subprocess.run(
        [os.sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    print(tests.stdout + tests.stderr)
    with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
        app = create_app({"DATABASE": str(Path(temporary) / "browser-demo.db")})
        server = make_server("127.0.0.1", 0, app)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with sync_playwright() as playwright:
                executable = os.getenv("PLAYWRIGHT_CHROMIUM")
                kwargs = {"headless": True}
                if executable:
                    kwargs["executable_path"] = executable
                browser = playwright.chromium.launch(**kwargs)
                context = browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    device_scale_factor=1,
                    record_video_dir=temporary,
                    record_video_size={"width": 1280, "height": 800},
                )
                page = context.new_page()
                page.goto(f"http://127.0.0.1:{server.server_port}/demo")
                page.locator("#health").get_by_text("HTTP 200").wait_for()
                page.wait_for_timeout(4500)

                def click_and_show(selector, delay=6000):
                    page.locator(selector).click()
                    page.wait_for_timeout(delay)

                click_and_show("#submit", 7500)
                page.get_by_role("button", name="Casual sample").click()
                click_and_show("#submit", 6500)
                page.get_by_role("button", name="Short poem").click()
                click_and_show("#submit", 6000)
                page.get_by_role("button", name="AI-style sample").click()
                click_and_show("#submit", 6500)
                click_and_show("#appeal", 6500)
                page.locator("#log").click()
                page.locator("#audit").scroll_into_view_if_needed()
                page.wait_for_timeout(7500)
                page.locator("#rate").click()
                page.locator("#rate-result").scroll_into_view_if_needed()
                page.wait_for_timeout(9000)
                assert "429" in page.locator("#rate-result").inner_text()
                assert "appeal" in page.locator("#audit").inner_text()
                page.wait_for_timeout(3000)
                video_path = page.video.path()
                context.close()
                browser.close()

            webm = ROOT / "demo_live.webm"
            shutil.copyfile(video_path, webm)
            mp4 = ROOT / "demo_walkthrough.mp4"
            subprocess.run([
                imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-i", str(webm),
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", str(mp4),
            ], check=True, stdout=subprocess.DEVNULL)
            print(f"Recorded live browser demo: {mp4}")
        finally:
            server.shutdown()
            thread.join(timeout=5)


if __name__ == "__main__":
    main()
