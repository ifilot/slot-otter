#!/usr/bin/env bash
# make_hls.sh — encode one movie into an adaptive HLS ladder (H.264 + AAC, MPEG-TS segments).
#
#   ./make_hls.sh SOURCE.mp4 OUTDIR
#
# Output (everything below OUTDIR is uploaded as-is):
#   OUTDIR/master.m3u8              master playlist — the URL the player loads
#   OUTDIR/1080p/index.m3u8         one media playlist per rung...
#   OUTDIR/1080p/seg_00000.ts       ...plus its ~6 s segments
#   OUTDIR/2160p/ OUTDIR/720p/ ...  (only rungs <= source height; never upscaled)
#   OUTDIR/poster.jpg               still frame for <video poster>
#
# Tunables (environment variables):
#   PRESET=slow        x264 speed/efficiency trade-off (medium = ~2x faster, ~5-10% bigger)
#   SEG=6              target segment length in seconds
#   GOP=2              keyframe (IDR) interval in seconds; SEG must be a multiple of GOP
#   AUDIO_KBPS=128     AAC-LC bitrate, identical in every rung
#   POSTER_AT=12       timestamp (s) of the poster frame
#   START_HEIGHT=1080  rung listed first in master.m3u8 = where Safari/iOS start playing
#   LADDER="2160:20:16000 1080:20:6000 720:21:3500 480:22:1500"
#                      height:CRF:maxrate_kbps per rung (see README for how to tune)
set -euo pipefail

SRC=${1:?usage: make_hls.sh SOURCE OUTDIR}
OUT=${2:?usage: make_hls.sh SOURCE OUTDIR}
PRESET=${PRESET:-slow}
SEG=${SEG:-6}
GOP=${GOP:-2}
AUDIO_KBPS=${AUDIO_KBPS:-128}
POSTER_AT=${POSTER_AT:-12}
START_HEIGHT=${START_HEIGHT:-1080}
LADDER=${LADDER:-"2160:20:16000 1080:20:6000 720:21:3500 480:22:1500"}

(( SEG % GOP == 0 )) || { echo "SEG ($SEG) must be a multiple of GOP ($GOP)" >&2; exit 1; }

probe() { ffprobe -v error -select_streams "$1" -show_entries "stream=$2" -of default=nw=1:nk=1 "$SRC" | head -1; }
SRC_W=$(probe v:0 width)
SRC_H=$(probe v:0 height)
SAR=$(probe v:0 sample_aspect_ratio); [[ $SAR =~ ^[1-9][0-9]*:[1-9][0-9]*$ ]] || SAR=1:1
FPS=$(probe v:0 avg_frame_rate)
MATRIX=$(probe v:0 color_space)
HAS_AUDIO=$(probe a:0 codec_type)

# Source YCbCr matrix, so it can be converted to BT.709 (what every HD player assumes).
# Untagged sources get the same guess a player would make: BT.601 below 720 lines, BT.709 above.
case "$MATRIX" in
  bt709|bt470bg|smpte170m) MIN=$MATRIX ;;
  *) if (( SRC_H >= 720 )); then MIN=bt709; else MIN=bt470bg; fi ;;
esac
# Only the matrix changes; primaries/transfer stay sRGB-like BT.709 (no gamut remapping).
CSPACE="colorspace=ispace=$MIN:iprimaries=bt709:itrc=bt709:irange=tv"
CSPACE+=":space=bt709:primaries=bt709:trc=bt709:range=tv:fast=1:format=yuv420p"

# Keep rungs that do not upscale. A source smaller than every rung gets one rung at its own size.
RUNGS=()
for r in $LADDER; do (( ${r%%:*} <= SRC_H )) && RUNGS+=("$r"); done
(( ${#RUNGS[@]} )) || RUNGS=("$(( SRC_H / 2 * 2 )):22:1500")

echo "source: ${SRC_W}x${SRC_H} SAR $SAR @ $FPS fps, matrix ${MATRIX:-unknown} (treated as $MIN) -> bt709, audio: ${HAS_AUDIO:-none}"

# One -filter_complex per rung: ffmpeg 7 runs each graph in its own thread, so the
# 4K->1080/720/480 scalers work in parallel instead of in series (~3x faster here).
GRAPHS=(); MAPS=(); ENC=(); VSM=()
for i in "${!RUNGS[@]}"; do
  IFS=: read -r H CRF MAXR <<<"${RUNGS[$i]}"
  # Width from the *display* aspect ratio (handles anamorphic sources), rounded to the nearest even.
  NUM=$(( H * SRC_W * ${SAR%:*} )); DEN=$(( 2 * SRC_H * ${SAR#*:} ))
  W=$(( (2 * NUM + DEN) / (2 * DEN) * 2 ))
  # Pin the H.264 level: x264's -preset slow uses 5 reference frames, which would push
  # 1080p to level 5.0 — some older Android decoders refuse that. 4.2 caps refs at 4.
  if   (( H <= 480 ));  then LEVEL=3.1
  elif (( H <= 720 ));  then LEVEL=3.2
  elif (( H <= 1080 )); then LEVEL=4.2
  else LEVEL=5.2; fi              # 2160p60 needs 5.2
  NAME="${H}p"
  echo "rung $NAME: ${W}x${H}, level $LEVEL, CRF $CRF, maxrate ${MAXR}k, bufsize $((2 * MAXR))k"
  GRAPHS+=(-filter_complex "[0:v]scale=$W:$H:flags=lanczos,$CSPACE,setsar=1[v$i]")
  MAPS+=(-map "[v$i]")
  ENC+=(-crf:v:$i "$CRF" -maxrate:v:$i "${MAXR}k" -bufsize:v:$i "$((2 * MAXR))k" -level:v:$i "$LEVEL")
  if [[ -n $HAS_AUDIO ]]; then
    MAPS+=(-map 0:a:0)
    VSM+=("v:$i,a:$i,name:$NAME")
  else
    VSM+=("v:$i,name:$NAME")
  fi
  mkdir -p "$OUT/$NAME"
done

AUDIO=()
[[ -n $HAS_AUDIO ]] && AUDIO=(-c:a aac -b:a "${AUDIO_KBPS}k" -ar 48000)

set -x
ffmpeg -hide_banner -y -i "$SRC" \
  "${GRAPHS[@]}" "${MAPS[@]}" \
  -c:v libx264 -preset "$PRESET" -profile:v high -pix_fmt yuv420p "${ENC[@]}" \
  -force_key_frames "expr:gte(t,n_forced*$GOP)" -sc_threshold 0 \
  -colorspace bt709 -color_primaries bt709 -color_trc bt709 -color_range tv \
  "${AUDIO[@]}" \
  -max_muxing_queue_size 4096 \
  -f hls -hls_time "$SEG" -hls_playlist_type vod -hls_list_size 0 \
  -hls_flags independent_segments -hls_segment_type mpegts \
  -hls_segment_filename "$OUT/%v/seg_%05d.ts" \
  -master_pl_name master.m3u8 \
  -var_stream_map "${VSM[*]}" \
  "$OUT/%v/index.m3u8"

# ffmpeg measures BANDWIDTH/AVERAGE-BANDWIDTH and writes CODECS, but not FRAME-RATE
# (which Apple's HLS spec asks for, especially above 30 fps). Add it.
RATE=$(awk -F/ '{ printf "%.3f", $1 / ($2 ? $2 : 1) }' <<<"$FPS")
sed -i -E "s/(RESOLUTION=[0-9]+x[0-9]+)/\1,FRAME-RATE=$RATE/" "$OUT/master.m3u8"

# Native HLS players (Safari, iOS) start with the first variant listed, and ffmpeg lists the
# highest first. List START_HEIGHT first so phones don't begin in 4K; hls.js ignores the order.
awk -v re="RESOLUTION=[0-9]+x${START_HEIGHT}," '
  /^#EXT-X-STREAM-INF/ { inf = $0; getline uri; e = inf "\n" uri "\n\n"
                         if (inf ~ re && first == "") first = e; else rest = rest e; next }
  NF { head = head $0 "\n" }
  END { printf "%s%s%s", head, first, rest }' "$OUT/master.m3u8" > "$OUT/master.m3u8.tmp"
mv "$OUT/master.m3u8.tmp" "$OUT/master.m3u8"

ffmpeg -hide_banner -loglevel error -y -ss "$POSTER_AT" -i "$SRC" -frames:v 1 \
  -vf "scale=1280:-2:flags=lanczos" -q:v 3 "$OUT/poster.jpg"
{ set +x; } 2>/dev/null
echo "done: $OUT/master.m3u8"
