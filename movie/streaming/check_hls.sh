#!/usr/bin/env bash
# check_hls.sh OUTDIR — verify an HLS ladder made by make_hls.sh is safe for ABR switching:
#   * every rung has the same number of segments with the same durations,
#   * every segment starts with a keyframe, at the same timestamp in every rung,
#   * every segment decodes on its own without errors, with the same frame count in every rung,
#   * no segment exceeds EXT-X-TARGETDURATION.
set -euo pipefail
OUT=${1:?usage: check_hls.sh OUTDIR}
cd "$OUT"
fail=0

echo "== master.m3u8"; cat master.m3u8; echo
mapfile -t RUNGS < <(grep -v '^#' master.m3u8 | grep . | xargs -n1 dirname)

ref=""
for r in "${RUNGS[@]}"; do
  pl="$r/index.m3u8"
  td=$(sed -n 's/#EXT-X-TARGETDURATION://p' "$pl")
  durs=$(sed -n 's/#EXTINF:\([0-9.]*\),.*/\1/p' "$pl")
  n=$(wc -l <<<"$durs")
  maxd=$(sort -g <<<"$durs" | tail -1)
  size=$(du -sh "$r" | cut -f1)
  # first video packet of every segment: "pts_time,flags"
  starts=$(for s in $(grep -v '^#' "$pl"); do
             ffprobe -v error -select_streams v:0 -show_entries packet=pts_time,flags \
                     -read_intervals '%+#1' -of csv=p=0 "$r/$s"
           done)
  nonkey=$(grep -vc ',K' <<<"$starts" || true)
  # Decode every segment on its own, as a player does right after switching rung:
  # it must decode cleanly with no reference to the previous segment. Count its frames.
  frames=$(grep -v '^#' "$pl" | sed "s#^#$r/#" | xargs -P "$(nproc)" -I{} sh -c \
    'o=$(ffprobe -v error -select_streams v:0 -count_frames -show_entries stream=nb_read_frames \
         -of csv=p=0 "$1" 2>&1)
     n=$(printf "%s\n" "$o" | grep -m1 -x "[0-9][0-9]*")   # TS repeats the stream under its program
     if [ -z "$n" ] || printf "%s\n" "$o" | grep -qvx "[0-9]*"; then echo "$1 ${n:-?} ERR"; else echo "$1 $n"; fi' _ {} \
    | sort)
  decerr=$(grep -c ' ERR$' <<<"$frames" || true)
  printf '%-6s %4d segments, longest %ss (target %s), %s on disk, non-keyframe starts: %s, decode errors: %s\n' \
         "$r" "$n" "$maxd" "$td" "$size" "$nonkey" "$decerr"
  (( nonkey == 0 && decerr == 0 )) || fail=1
  awk -v m="$maxd" -v t="$td" 'BEGIN{exit !(m <= t + 0.5)}' || { echo "  segment longer than target"; fail=1; }
  sig=$(paste -d' ' <(echo "$durs") <(cut -d, -f1 <<<"$starts") <(awk '{print $2}' <<<"$frames"))
  if [[ -z $ref ]]; then ref=$sig; refname=$r
  elif [[ $sig != "$ref" ]]; then
    echo "  MISALIGNED vs $refname:"; diff <(echo "$ref") <(echo "$sig") | head; fail=1
  fi
done

(( fail == 0 )) && echo "OK: all rungs aligned — identical segment boundaries and frame counts, each segment starts on a keyframe and decodes on its own." \
                || { echo "FAILED"; exit 1; }
