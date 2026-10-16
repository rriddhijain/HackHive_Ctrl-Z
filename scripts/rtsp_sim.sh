#!/usr/bin/env bash
# ffmpeg 8.0.1 has no RTSP listen mode ('-f rtsp -rtsp_flags listen' tries to CONNECT and dies: Connection refused) and
# no RTSP server (mediamtx, VLC) is installed, so rtsp_sim.py is the server: ffmpeg loops the clip into RTP, Python serves it.
cd "$(dirname "$0")/.." && exec uv run python scripts/rtsp_sim.py "${1:-data/dev/fighting/v011.avi}" "${@:2}"
