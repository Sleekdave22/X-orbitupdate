"""Bounded camera-evidence decoding; this module does not establish authenticity.

New submissions are 3–10 seconds. Previously accepted recordings may still be
reviewed with the historical 60-second bound so a policy change never discards
someone's pending proof. Ordinary Vibe/media-editor limits are independent.
"""

import base64
import io
import math

MIN_SECONDS = 3
MAX_SECONDS = 10
LEGACY_MAX_SECONDS = 60
MAX_BYTES = 20 * 1024 * 1024


def inspect(raw, frames=False, max_seconds=MAX_SECONDS):
    """Validate video bytes and optionally extract three proportional JPEG frames.

    Args:
        raw (bytes): Private recording, never written to a temporary file.
        frames (bool): Whether to decode first/middle/last representative frames.
        max_seconds (int): Server-selected bound; 60 only for stored legacy proof.
    Returns:
        dict: Normalized MIME, duration in seconds, and base64 JPEG samples.
    Raises:
        ValueError: Invalid, oversized, short, long or non-monotonic recording.
        av.error.FFmpegError: Malformed container/decoder errors (caller sanitizes).
    """
    import av

    if not isinstance(raw, bytes) or not 1 <= len(raw) <= MAX_BYTES:
        raise ValueError('Record a video up to 20 MB')
    if max_seconds not in (MAX_SECONDS, LEGACY_MAX_SECONDS):
        raise ValueError('Unsupported evidence duration policy')
    start = None
    last = -1.0
    duration = 0.0
    count = 0
    with av.open(io.BytesIO(raw)) as container:
        if len(container.streams.video) != 1:
            raise ValueError('Record one camera video')
        stream = container.streams.video[0]
        if not stream.width or not stream.height or stream.width * stream.height > 1920 * 1080:
            raise ValueError('Use a recording up to 1080p')
        name = container.format.name
        mime = ('video/webm' if 'webm' in name or 'matroska' in name else
                'video/mp4' if 'mp4' in name or 'mov' in name else None)
        if mime is None:
            raise ValueError('Use an MP4 or WebM recording')
        rate = float(stream.average_rate) if stream.average_rate else 30.0
        if not math.isfinite(rate) or rate <= 0 or rate > 120:
            raise ValueError('Use a recording up to 120 frames per second')
        for frame in container.decode(stream):
            count += 1
            if count > max_seconds * 120 + 2 or frame.time is None:
                raise ValueError('Recording exceeds the supported duration')
            timestamp = float(frame.time)
            if not math.isfinite(timestamp):
                raise ValueError('Recording has invalid timestamps')
            if start is None:
                start = timestamp
            elapsed = timestamp - start
            if elapsed < last or elapsed > max_seconds:
                raise ValueError('Recording has invalid timestamps or is too long')
            last = elapsed
            frame_length = float(frame.duration * frame.time_base) if frame.duration else 1 / rate
            if not math.isfinite(frame_length) or frame_length <= 0:
                raise ValueError('Recording has invalid frame durations')
            duration = elapsed + frame_length
            if duration > max_seconds + .05:
                raise ValueError('Record up to ' + str(max_seconds) + ' seconds')
    if count < 3 or duration < MIN_SECONDS - .05:
        raise ValueError('Record at least 3 seconds showing navigation and the result')
    return {'mime': mime, 'duration': duration,
            'frames': sample_frames(raw, last) if frames else []}


def sample_frames(raw, last_timestamp):
    """Return first/middle/final representative frames without retaining the clip.

    Args:
        raw (bytes): Already validated camera recording.
        last_timestamp (float): Last frame's relative time in seconds from inspect.
    Returns:
        list[str]: Three base64 JPEGs selected at 0%, 50% and 90% of the clip.
    Raises:
        ValueError: The recording cannot supply all required samples.
        av.error.FFmpegError: Decoder failure, propagated to the review worker.

    A second bounded decode handles phone WebM files without duration headers.
    Proportional targets avoid the old five-second spacing rejecting short clips.
    """
    import av

    targets = (0, last_timestamp * .5, last_timestamp * .9)
    samples = []
    start = None
    with av.open(io.BytesIO(raw)) as container:
        for frame in container.decode(video=0):
            if start is None:
                start = float(frame.time)
            if float(frame.time) - start + .001 < targets[len(samples)]:
                continue
            image = frame.to_image()
            image.thumbnail((1280, 720))
            output = io.BytesIO()
            image.save(output, format='JPEG', quality=85)
            samples.append(base64.b64encode(output.getvalue()).decode())
            if len(samples) == len(targets):
                return samples
    raise ValueError('Recording did not contain all required review frames')
