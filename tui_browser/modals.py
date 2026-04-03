"""Modal screens for displaying multimedia (Images, Videos) in the TUI Browser."""

import io
import time
import requests

from PIL import Image
import cv2
import yt_dlp

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, Static

from .constants import REQUEST_TIMEOUT

class ImageViewerModal(ModalScreen[None]):
    """A modal popup to view high-resolution ASCII representation of an image."""

    CSS = """
    ImageViewerModal {
        align: center middle;
        background: $background 50%;
    }

    #img-container {
        width: 100%;
        height: 100%;
        padding: 1 2;
        background: $panel;
        align: center middle;
    }

    #image-label {
        width: auto;
        height: auto;
    }
    """

    BINDINGS = [
        Binding("escape,q,enter", "close_viewer", "Close Image", show=True),
    ]

    def __init__(self, img_url: str, session: requests.Session) -> None:
        super().__init__()
        self.img_url = img_url
        self._session = session

    def compose(self) -> ComposeResult:
        with Vertical(id="img-container"):
            yield Label("[Esc / q] Close Image", classes="text-center")
            yield Static("⏳ Downloading image...", id="image-label")

    def on_mount(self) -> None:
        self.fetch_and_render_image()

    def action_close_viewer(self) -> None:
        try:
            lbl = self.query_one("#image-label", Static)
            lbl.update("[Closing...]")
        except Exception:
            pass
        self.dismiss()

    @work(thread=True)
    def fetch_and_render_image(self) -> None:
        try:
            resp = self._session.get(self.img_url, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()

            # Load image with Pillow
            img = Image.open(io.BytesIO(resp.content))
            img = img.convert("RGBA")

            # Fast native rendering mapping exactly to terminal dimensions minus borders.
            # No excessive memory cache or segments, directly stringified to standard ansi.
            try:
                term_w = self.app.size.width
                term_h = self.app.size.height
            except Exception:
                term_w, term_h = 100, 40

            max_w = max(40, term_w - 6)
            max_h = max(20, term_h - 6) * 2

            img.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
            new_w, new_h = img.size

            ESC = chr(27)
            output_lines = []

            pixels = img.load()
            for y in range(0, new_h, 2):
                line_chars = []
                for x in range(new_w):
                    r_t, g_t, b_t, a_t = pixels[x, y]
                    if y + 1 < new_h:
                        r_b, g_b, b_b, a_b = pixels[x, y + 1]
                    else:
                        r_b, g_b, b_b, a_b = (0, 0, 0, 255)

                    if a_t < 128: r_t, g_t, b_t = 0, 0, 0
                    if a_b < 128: r_b, g_b, b_b = 0, 0, 0

                    fg_esc = f"{ESC}[38;2;{r_t};{g_t};{b_t}m"
                    bg_esc = f"{ESC}[48;2;{r_b};{g_b};{b_b}m"
                    line_chars.append(f"{fg_esc}{bg_esc}▀{ESC}[0m")

                output_lines.append("".join(line_chars))

            ascii_art = "\n".join(output_lines)

            from rich.text import Text
            self.app.call_from_thread(self._update_label, Text.from_ansi(ascii_art, no_wrap=True))

        except Exception as e:
            self.app.call_from_thread(self._update_label, f"Error displaying image:\n{e}")

    def _update_label(self, markupOrStr):
        try:
            lbl = self.query_one("#image-label", Static)
            lbl.update(markupOrStr)
        except Exception:
            pass


class VideoViewerModal(ModalScreen[None]):
    """A modal popup to view high-resolution ASCII video streams."""

    CSS = """
    VideoViewerModal {
        align: center middle;
        background: $background 50%;
    }
    #vid-container {
        width: 100vw;
        height: 100vh;
        padding: 1 2;
        background: $panel;
        align: center middle;
    }
    #video-label {
        width: auto;
        height: auto;
        content-align: center middle;
    }
    """

    BINDINGS = [
        Binding("escape,q,enter", "close_viewer", "Close Video", show=True),
    ]

    def __init__(self, vid_url: str) -> None:
        super().__init__()
        self.vid_url = vid_url
        self.playing = False
        self.frame_pending = False

    def compose(self) -> ComposeResult:
        with Vertical(id="vid-container"):
            yield Label("[Esc / q] Close Video", classes="text-center", id="top-label")
            yield Static("⏳ Starting video stream...", id="video-label")

    def on_mount(self) -> None:
        self.playing = True
        self.fetch_and_play()

    def action_close_viewer(self) -> None:
        self.playing = False
        try:
            lbl = self.query_one("#video-label", Static)
            lbl.update("[Stopping stream...]")
        except Exception:
            pass
        self.dismiss()

    def _update_video(self, renderable):
        self.frame_pending = False
        try:
            self.query_one("#video-label", Static).update(renderable)
        except Exception:
            pass

    @work(thread=True)
    def fetch_and_play(self) -> None:
        try:
            video_url = self.vid_url
            if "youtube.com" in video_url or "youtu.be" in video_url:
                self.app.call_from_thread(self._update_video, "⏳ Resolving YouTube stream (yt-dlp)...")
                # Grab a higher quality stream so subtitles are readable before downsampling
                ydl_opts = {'format': 'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480]/best', 'quiet': True}
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(video_url, download=False)
                    video_url = info['url']

            cap = cv2.VideoCapture(video_url)
            if not cap.isOpened():
                self.app.call_from_thread(self._update_video, "❌ Error: Cannot open video stream.")
                return

            fps = cap.get(cv2.CAP_PROP_FPS)
            fps = float(fps) if fps else 30.0

            # Allow higher framerates for smoother terminal video playback (up to 60fps)
            if fps > 60: fps = 60.0
            frame_time = 1.0 / fps

            try:
                term_w = self.app.size.width
                term_h = self.app.size.height
            except Exception:
                term_w, term_h = 100, 48

            max_w = max(40, term_w - 4)
            max_h = max(20, term_h - 4) * 2

            from rich.segment import Segment
            from rich.style import Style
            from rich.color import Color

            line_seg = Segment.line()
            char_block = "▀"
            style_cache = {}

            class PixelArtRenderable:
                def __init__(self, segs):
                    self.segs = segs
                def __rich_console__(self, console, options):
                    yield from self.segs

            while self.playing:
                start_t = time.time()
                ret, frame = cap.read()
                if not ret:
                    break

                h_orig, w_orig = frame.shape[:2]
                scale = min(max_w / w_orig, max_h / h_orig)
                new_w = max(1, int(w_orig * scale))
                new_h = max(1, int(h_orig * scale))

                # Smooth downsampling (INTER_AREA) to keep small subtitle pixels readable
                frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                segments = []
                for y in range(0, new_h, 2):
                    for x in range(new_w):
                        r_t, g_t, b_t = frame[y, x]
                        if y + 1 < new_h:
                            r_b, g_b, b_b = frame[y+1, x]
                        else:
                            r_b, g_b, b_b = (0, 0, 0)

                        key = (r_t, g_t, b_t, r_b, g_b, b_b)
                        if key not in style_cache:
                            style_cache[key] = Style(
                                color=Color.from_rgb(r_t, g_t, b_t),
                                bgcolor=Color.from_rgb(r_b, g_b, b_b),
                            )
                        segments.append(Segment(char_block, style_cache[key]))
                    segments.append(line_seg)

                # Wait if the UI thread is still drawing the previous frame (prevents freezing)
                wait_start = time.time()
                while self.frame_pending and self.playing and (time.time() - wait_start < 0.5):
                    time.sleep(0.005)

                fast_pixel_art = PixelArtRenderable(segments)
                self.frame_pending = True
                self.app.call_from_thread(self._update_video, fast_pixel_art)

                elapsed = time.time() - start_t
                sleep_time = frame_time - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)

            cap.release()
            if self.playing:
                self.app.call_from_thread(self._update_video, "Playback Finished. [Esc / q] to close.")

        except Exception as exc:
            self.app.call_from_thread(self._update_video, f"❌ Error loading video:\n{exc}")