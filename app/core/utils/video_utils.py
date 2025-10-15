import subprocess
import tempfile
from pathlib import Path


def trim_to_seconds(input_video: str, output_video: str, seconds: int = 30):
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        "0",
        "-t",
        str(seconds),
        "-i",
        input_video,
        "-c",
        "copy",
        output_video,
    ]
    subprocess.run(cmd, check=True)


def add_watermark(
    input_video: str,
    output_video: str,
    watermark_path: str,
    position: str = "top-right",
    margin: int = 10,
):
    pos_map = {
        "top-left": f"{margin}:{margin}",
        "top-right": f"W-w-{margin}:{margin}",
        "bottom-left": f"{margin}:H-h-{margin}",
        "bottom-right": f"W-w-{margin}:H-h-{margin}",
        "center": "(W-w)/2:(H-h)/2",
    }
    overlay = pos_map.get(position, pos_map["top-right"])
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        input_video,
        "-i",
        watermark_path,
        "-filter_complex",
        f"[0:v][1:v]overlay={overlay}",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "copy",
        output_video,
    ]
    subprocess.run(cmd, check=True)


def scale_to_720p(input_video: str, output_video: str, fps: int = 30):
    vf = f"scale=-2:720,setsar=1,fps={fps}"
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        input_video,
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "copy",
        output_video,
    ]
    subprocess.run(cmd, check=True)


def remove_audio(input_video: str, output_video: str, reencode: bool = False):
    if reencode:
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            input_video,
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-pix_fmt",
            "yuv420p",
            "-an",
            output_video,
        ]
    else:
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            input_video,
            "-c:v",
            "copy",
            "-an",
            output_video,
        ]
    subprocess.run(cmd, check=True)


def add_image_intro_outro(
    image_path: str,
    input_video: str,
    output_video: str,
    seconds: int = 3,
    w: int = 1280,
    h: int = 720,
    fps: int = 30,
):
    image = Path(image_path)
    inp = Path(input_video)
    out = Path(output_video)
    out.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as td:
        intro = Path(td) / "intro.mp4"
        outro = Path(td) / "outro.mp4"
        mid_with_audio = Path(td) / "mid_with_audio.mp4"

        # intro
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-loop",
                "1",
                "-t",
                str(seconds),
                "-i",
                str(image),
                "-f",
                "lavfi",
                "-t",
                str(seconds),
                "-i",
                "anullsrc=channel_layout=stereo:sample_rate=48000",
                "-vf",
                f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
                f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,format=yuv420p,fps={fps}",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-shortest",
                str(intro),
            ],
            check=True,
        )

        # outro
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-loop",
                "1",
                "-t",
                str(seconds),
                "-i",
                str(image),
                "-f",
                "lavfi",
                "-t",
                str(seconds),
                "-i",
                "anullsrc=channel_layout=stereo:sample_rate=48000",
                "-vf",
                f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
                f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,format=yuv420p,fps={fps}",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-shortest",
                str(outro),
            ],
            check=True,
        )

        # garantizar que el segmento medio tenga una pista de audio (silencio)
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(inp),
                "-f",
                "lavfi",
                "-i",
                "anullsrc=channel_layout=stereo:sample_rate=48000",
                "-shortest",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                str(mid_with_audio),
            ],
            check=True,
        )

        # concat intro + video (con audio silencioso) + outro
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(intro),
                "-i",
                str(mid_with_audio),
                "-i",
                str(outro),
                "-filter_complex",
                "[0:v][0:a][1:v][1:a][2:v][2:a]concat=n=3:v=1:a=1[v][a]",
                "-map",
                "[v]",
                "-map",
                "[a]",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-shortest",
                str(out),
            ],
            check=True,
        )
