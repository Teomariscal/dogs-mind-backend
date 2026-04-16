"""
Video frame extractor for clinical analysis.

Extracts a representative set of frames from a video file and returns
them as base64-encoded JPEG strings suitable for Claude's vision API.

Primary method  : OpenCV (cv2)
Fallback method : ffmpeg subprocess (if cv2 is unavailable)

Frame strategy:
  • Up to MAX_FRAMES frames sampled evenly across the full video duration.
  • Each frame is resized to ≤ MAX_WIDTH px wide (keeps aspect ratio).
  • JPEG quality 82 — good balance between visual fidelity and token usage.
"""

from __future__ import annotations

import base64
import logging
import os
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

MAX_FRAMES = 8
MAX_WIDTH  = 768
JPEG_QUALITY = 82


# ── OpenCV implementation ────────────────────────────────────────────────────

def _extract_with_cv2(video_path: str, max_frames: int) -> list[str]:
    import cv2  # type: ignore

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"OpenCV could not open video: {video_path}")

    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total <= 0:
        raise RuntimeError("Could not determine frame count")

    # Evenly spaced frame indices
    indices = [int(total * i / max_frames) for i in range(max_frames)]

    frames_b64: list[str] = []
    for idx in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, frame = cap.read()
        if not ok:
            continue

        h, w = frame.shape[:2]
        if w > MAX_WIDTH:
            scale = MAX_WIDTH / w
            new_w, new_h = int(w * scale), int(h * scale)
            frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)

        encode_params = [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
        ok2, buf = cv2.imencode(".jpg", frame, encode_params)
        if not ok2:
            continue
        frames_b64.append(base64.b64encode(buf.tobytes()).decode("utf-8"))

    cap.release()
    return frames_b64


# ── ffmpeg fallback ──────────────────────────────────────────────────────────

def _extract_with_ffmpeg(video_path: str, max_frames: int) -> list[str]:
    """
    Uses ffmpeg to extract evenly spaced frames to a temp directory.
    Requires ffmpeg to be installed and in PATH.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Extract frames using select filter (evenly spaced)
        out_pattern = os.path.join(tmpdir, "frame_%03d.jpg")
        cmd = [
            "ffmpeg", "-y", "-i", video_path,
            "-vf", f"select=not(mod(n\\,1)),scale={MAX_WIDTH}:-2",
            "-vframes", str(max_frames * 10),   # grab more, then subsample
            "-q:v", "4",                         # JPEG quality (1=best, 31=worst)
            out_pattern,
            "-loglevel", "error",
        ]
        subprocess.run(cmd, check=True, capture_output=True)

        # Pick evenly spaced subset
        all_frames = sorted(Path(tmpdir).glob("frame_*.jpg"))
        if not all_frames:
            raise RuntimeError("ffmpeg produced no frames")

        step = max(1, len(all_frames) // max_frames)
        selected = all_frames[::step][:max_frames]

        frames_b64: list[str] = []
        for fpath in selected:
            data = fpath.read_bytes()
            frames_b64.append(base64.b64encode(data).decode("utf-8"))

        return frames_b64


# ── Public API ───────────────────────────────────────────────────────────────

def extract_frames(video_path: str, max_frames: int = MAX_FRAMES) -> list[str]:
    """
    Extract up to *max_frames* representative frames from *video_path*.

    Returns a list of base64-encoded JPEG strings.
    Tries OpenCV first; falls back to ffmpeg if cv2 is not installed.
    Raises RuntimeError if neither method succeeds.
    """
    try:
        frames = _extract_with_cv2(video_path, max_frames)
        logger.info("Extracted %d frames with OpenCV from %s", len(frames), video_path)
        return frames
    except ImportError:
        logger.warning("cv2 not available — falling back to ffmpeg")
    except Exception as e:
        logger.warning("OpenCV extraction failed (%s) — trying ffmpeg", e)

    try:
        frames = _extract_with_ffmpeg(video_path, max_frames)
        logger.info("Extracted %d frames with ffmpeg from %s", len(frames), video_path)
        return frames
    except Exception as e:
        raise RuntimeError(
            f"Could not extract frames from video. "
            f"Install opencv-python or ensure ffmpeg is in PATH. Error: {e}"
        ) from e
