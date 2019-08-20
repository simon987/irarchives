import json
import os
import subprocess
import tempfile
import traceback
from io import BytesIO
from threading import Thread

from PIL import Image

from common import logger, TN_SIZE
from img_util import get_hash, image_from_buffer

CHUNK_LENGTH = 1024 * 24


def feed_buffer_to_process(buffer, p):
    try:
        p.stdin.write(buffer)
        p.stdin.close()
    except:
        pass


def info_from_video_buffer(video_buffer, ext, disk=False):

    if disk:
        logger.info("Temporarily saving to disk because I can't pipe mp4"
                    " that has metadata at the end of the file to ffmpeg")
        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp.file.write(video_buffer)
        tmp.close()

    p = subprocess.Popen([
        "ffmpeg", "-threads", "1", "-i",
        ("pipe:" + ext) if not disk else tmp.name,
        # Extract frame if is multiple of 6 OR is a keyframe
        "-vf", "select=not(mod(n\\,6))+eq(pict_type\\,I)", "-vsync", "0",
        "-f", "image2pipe", "-loglevel", "error",
        "pipe:jpg"
    ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL
    )
    if not disk:
        # Write to stdin in a different thread to avoid deadlock
        feeding_thread = Thread(target=feed_buffer_to_process, args=(video_buffer, p))
        feeding_thread.start()
    try:
        frames = dict()
        image_buffer = BytesIO()
        last_byte_was_marker_byte = False

        image_buffer.write(p.stdout.read(2))  # Skip first jpeg start magic number
        chunk = p.stdout.read(CHUNK_LENGTH)
        while chunk:
            last_image_offset = 0
            for offset, b in enumerate(chunk):
                if b == 0xFF:
                    last_byte_was_marker_byte = True
                    continue
                else:
                    if last_byte_was_marker_byte and b == 0xD9:
                        image_buffer.write(chunk[last_image_offset:offset + 3])

                        im = image_from_buffer(image_buffer.getvalue())
                        im.thumbnail((TN_SIZE, TN_SIZE), Image.ANTIALIAS)

                        frames[get_hash(im)] = im

                        image_buffer = BytesIO()
                        last_image_offset = offset + 1
                    last_byte_was_marker_byte = False

            image_buffer.write(chunk[last_image_offset:])
            chunk = p.stdout.read(CHUNK_LENGTH)

        if not frames and not disk and ext == "mp4":
            return info_from_video_buffer(video_buffer, ext, True)

        # Get media info
        if disk:
            info = get_video_info_disk(tmp.name)
        else:
            info = get_video_info_buffer(video_buffer)

        return frames, info
    except Exception as e:
        logger.error(e)
        logger.error(traceback.format_exc())
    finally:
        p.stdout.close()
        p.terminate()
        if disk:
            try_remove(tmp.name)


def get_video_info_buffer(video_buffer):

    p = subprocess.Popen([
        "ffprobe", "-v", "quiet", "-print_format", "json=c=1", "-show_format", "-show_streams", "pipe:"
    ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL
    )

    feeding_thread = Thread(target=feed_buffer_to_process, args=(video_buffer, p))
    feeding_thread.start()

    result = p.stdout.read()
    j = json.loads(result.decode())
    return j


def flatten_video_info(info):

    result = dict()

    for stream in info["streams"]:
        if stream["codec_type"] == "video":
            result["codec"] = stream["codec_name"]
            result["width"] = stream["width"]
            result["height"] = stream["height"]

            result["bitrate"] = int(stream["bit_rate"]) if "bit_rate" in stream else 0
            result["frames"] = int(stream["nb_frames"]) if "nb_frames" in stream else 0

            if "duration" in stream:
                result["duration"] = int(float(stream["duration"]))
            elif "duration" in info["format"]:
                result["duration"] = int(float(info["format"]["duration"]))
            else:
                result["duration"] = 0
            break

    result["format"] = info["format"]["format_long_name"]
    return result


def get_video_info_disk(filename):
    p = subprocess.Popen([
        "ffprobe", "-v", "quiet", "-print_format", "json=c=1", "-show_format", "-show_streams", filename
    ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        # stderr=subprocess.DEVNULL
    )

    result = p.stdout.read()
    j = json.loads(result.decode())
    return j


def try_remove(name):
    try:
        os.remove(name)
    except:
        pass
