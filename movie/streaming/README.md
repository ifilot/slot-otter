# Adaptive streaming (HLS)

Turns a finished movie into an ad-free, self-hosted HLS stream that browsers switch between
4K / 1080p / 720p / 480p automatically as the connection changes.

| File | What it does |
|---|---|
| [make_hls.sh](make_hls.sh) | source MP4 → `master.m3u8` + one playlist and ~6 s segments per rung + `poster.jpg` |
| [check_hls.sh](check_hls.sh) | proves the rungs are switch-safe (same boundaries, every segment starts on a keyframe) |
| [player.html](player.html) | the player page (published as `watch.html`): native HLS where the browser has it, hls.js otherwise |

## 1. Why the existing MP4s are re-encoded

`build/slot-otter-classic-voiceover*.mp4` cannot simply be cut into HLS segments:

* **Keyframes are irregular.** The 2160p file has an IDR every 250 frames (x264's default,
  4.17 s), restarting at every scene join; the 1080p file every ~2.97 s. A segment must start
  on a keyframe, so cutting either file gives segments of different lengths at different times
  in each rung. A player switching rung mid-movie then lands mid-GOP or repeats/skips frames:
  visible glitches, stalls, or decode errors. Keyframes cannot be added without re-encoding.
* **720p and 480p do not exist,** and the 1080p file (NVENC) carries no colour tags.

So every rung is encoded fresh from the 2160p master, from one ffmpeg process with one decode,
with keyframes forced on the same timestamps in every rung.

## 2. Encoding

Runs on any Linux machine with ffmpeg ≥ 7 (built with libx264); timings below are for a
64-core workstation with Debian's ffmpeg 7.1. Set `HOST` to your encoding machine's SSH login:

```sh
HOST=user@encode-host
ssh $HOST 'mkdir -p ~/hls/src ~/hls/out'
scp ../build/slot-otter-classic-voiceover-2160p-clean.mp4 $HOST:hls/src/
scp make_hls.sh check_hls.sh $HOST:hls/

ssh $HOST
cd ~/hls
nohup ./make_hls.sh src/slot-otter-classic-voiceover-2160p-clean.mp4 out/slot-otter-classic \
      > out/slot-otter-classic.log 2>&1 &          # 4K60 source: ~22 min for 1080/720/480, ~50 min more for 2160p
./check_hls.sh out/slot-otter-classic              # must end in "OK: all rungs aligned"
exit

# bring the result back
mkdir -p ../build/hls
scp -r $HOST:hls/out/slot-otter-classic ../build/hls/
cp ../build/publish/slot-otter-classic.vtt ../build/hls/slot-otter-classic/captions.en.vtt
```

What `make_hls.sh` does, and why:

| Choice | Setting | Reason |
|---|---|---|
| Ladder | 2160p, 1080p, 720p, 480p, only rungs ≤ source height | never upscales; a source below 480p gets one rung at its own size |
| Aspect ratio | width = height × display aspect, rounded to even; `setsar=1` | 16:9 → 1920×1080, 1280×720, 854×480; anamorphic sources come out square-pixel |
| Frame rate | untouched (60 fps here) | no `-r`, no `fps` filter |
| Keyframes | `-force_key_frames expr:gte(t,n_forced*2)`, `-sc_threshold 0` | an IDR every 2.000 s at the same timestamp in every rung; no extra scene-cut keyframes that would differ between rungs |
| Segments | `-hls_time 6` | cut at the keyframe at 6, 12, 18 s… → identical 6.000 s segments in all rungs (3 GOPs each; Apple recommends ≤2 s GOPs and 6 s segments) |
| Video | libx264 High, levels 5.2 / 4.2 / 3.2 / 3.1, `yuv420p`, `-preset slow` | 1080p and below play on effectively every device since ~2013; 4K (level 5.2) only where the device can decode it — hls.js drops it automatically elsewhere. Levels pinned because `-preset slow` would otherwise make 1080p level 5.0 |
| Rate control | capped CRF (see §3) | constant quality, peaks bounded so the advertised bandwidth is honest |
| Colour | BT.601 → BT.709 matrix conversion, fully tagged BT.709 | the renderer's RGB→YUV used ffmpeg's default BT.601 matrix; HD players assume BT.709, so without conversion some show shifted reds/greens |
| Audio | AAC-LC 128 kb/s, 48 kHz, mono (as source), identical in every rung | muxed into each rung, so switching never touches audio |
| Container | MPEG-TS segments | broadest player support (old Android, smart TVs, every hls.js version) |
| Master | `BANDWIDTH` (measured peak), `AVERAGE-BANDWIDTH`, `CODECS`, `RESOLUTION`, `FRAME-RATE` | ffmpeg measures the first two from the real segments; `FRAME-RATE` is added afterwards |

The scalers run as one `-filter_complex` per rung so ffmpeg 7 puts them on separate threads.
Memory: the 2160p rung alone peaked at 8.5 GB RSS (x264 lookahead and frame threads at 4K); all
four rungs in one run should need roughly 12–16 GB (estimate, not measured), fine on the 64 GB workstation.
The limit is x264 itself (~36 fps for 1080p60 at `slow`). `PRESET=medium` is ~25% faster at
~5–10% more bits for the same quality.

### Output layout (upload this folder as is)

```
slot-otter-classic/
├── master.m3u8          ← the URL the player loads
├── poster.jpg
├── captions.en.vtt      (copied in by hand, optional)
├── 2160p/index.m3u8  2160p/seg_00000.ts … seg_00101.ts
├── 1080p/index.m3u8  1080p/seg_00000.ts …
├── 720p/index.m3u8   720p/seg_00000.ts  …
└── 480p/index.m3u8   480p/seg_00000.ts  …
```

All playlist URIs are relative, so the folder works under any bucket prefix.

## 3. Bitrates and how to tune them

Each rung is `height:CRF:maxrate` in `LADDER`; `bufsize` is always 2 × maxrate.

| Rung | CRF | maxrate | bufsize | Measured on this movie (average / peak 6 s segment) |
|---|---|---|---|---|
| 2160p60 | 20 | 16000 kb/s | 32000 kb/s | 4.15 / 9.76 Mb/s |
| 1080p60 | 20 | 6000 kb/s | 12000 kb/s | 1.73 / 4.02 Mb/s |
| 720p60 | 21 | 3500 kb/s | 7000 kb/s | 0.98 / 2.18 Mb/s |
| 480p60 | 22 | 1500 kb/s | 3000 kb/s | 0.58 / 1.21 Mb/s |

*Measured figures are the master playlist's `AVERAGE-BANDWIDTH` / `BANDWIDTH`, including
audio and TS overhead.*

* **CRF sets quality.** Lower = better and bigger; ±6 roughly doubles/halves the size. 18–23 is
  the sensible range for H.264. Each lower rung gets +1 because small pictures hide less.
* **maxrate caps the peak.** Pick it from the slowest connection the rung must serve. Animated
  diagrams like this movie mostly stay far below it (static scenes cost almost nothing), so
  here it only bites on busy transitions. Live-action camera footage hits the cap much more.
* **bufsize** is how long a burst above maxrate may last: 2× maxrate = 2 s. Smaller is
  smoother on the network, larger is better quality on hard scenes.
* Typical starting points for live-action content: 60 fps — 6000 / 3500 / 1500 kb/s;
  30 fps or less — 5000 / 2800 / 1200 kb/s.
* The default ladder is `"2160:20:16000 1080:20:6000 720:21:3500 480:22:1500"`; rungs above the
  source height are skipped. Lower rung for mobile data: append `360:23:800`.
* `master.m3u8` lists `START_HEIGHT` (default 1080) first: Safari/iOS start playback on the first
  listed rung, and ffmpeg would list 4K first. hls.js ignores the order.

```sh
LADDER="1080:19:8000 720:21:3500 480:23:1200" PRESET=medium ./make_hls.sh in.mp4 out/name
```

## 4. Publishing

The output folder and the player page are published side by side on any static host (deployment
itself is kept outside this repository):

```
slot-otter-classic/
├── watch.html     ← player.html; the link in the READMEs
└── v1/            ← the folder make_hls.sh produced, uploaded as is
```

Public page: <https://movies.filotcdn.org/slot-otter-classic/watch.html>

What the host must serve:

| File | Content-Type | Cache-Control |
|---|---|---|
| `.ts` | `video/mp2t` | `public, max-age=31536000, immutable` |
| `.m3u8` | `application/vnd.apple.mpegurl` | `public, max-age=3600` |
| `.vtt` | `text/vtt; charset=utf-8` | `public, max-age=86400` |
| `.jpg` | `image/jpeg` | `public, max-age=86400` |
| `watch.html` | `text/html; charset=utf-8` | `public, max-age=300` |

The content types matter: guessed from the extension, `.ts` often becomes
`video/vnd.dlna.mpeg-tts`, `text/vnd.trolltech.linguist` or TypeScript, and Safari refuses it.
Upload segments first and playlists and the page last, so nothing points at a missing file.

**Re-encoding:** publish to `v2/`, change `v1/` → `v2/` in [player.html](player.html) (three places),
publish the page again. Segment names repeat between encodes and old ones may still be cached, so
never overwrite `v1/` in place. The page URL, and so every README link, stays the same.

**No CORS** is needed while the page is served from the same host as the video. Embedding the
player on another site needs a CORS rule on the host allowing that site's origin (`GET`, `HEAD`).

## 5. Webpage

[player.html](player.html), published as `watch.html`. All URLs are relative (`v1/master.m3u8`,
`v1/poster.jpg`, `v1/captions.en.vtt`). Logic:

* `canPlayType('application/vnd.apple.mpegurl')` true → the URL goes straight into `<video>`
  (Safari on macOS/iOS/iPadOS, and newer Chrome builds that have native HLS).
* Otherwise hls.js 1.7.4 is loaded from jsDelivr (with SRI hash), only on those browsers.
* `capLevelToPlayerSize` stops hls.js fetching 1080p for a small player.
* **Quality menu** under the video: *Auto* (shows the current rung, e.g. "Auto (720p)") or a
  fixed 2160p (4K) / 1080p / 720p / 480p; the choice is remembered per browser (`localStorage`).
  With hls.js it sets `hls.currentLevel` (immediate switch) or `hls.loadLevel = -1` (back to
  automatic). Native HLS (Safari, iOS, current Chrome) has no API to pick a rendition, so the page
  reads `master.m3u8` itself and loads that rung's own playlist, resuming at the same time and
  play state; *Auto* loads the master again. In the iOS fullscreen player the menu is not
  visible: viewers choose before going fullscreen.
* The forward buffer is capped at 60 s (`maxMaxBufferLength`), so a viewer who leaves early has
  not downloaded the whole movie, and a manual switch has little to throw away.
* `?debug` shows engine, current rung, bandwidth estimate and buffer under the video;
  `?engine=hlsjs` / `?engine=native` forces a path for testing.

## 6. Testing

**Before uploading (local, same layout as the bucket):**

```sh
mkdir -p /tmp/preview && cp player.html /tmp/preview/watch.html
ln -sfn "$PWD/../build/hls/slot-otter-classic" /tmp/preview/v1
cd /tmp/preview && python3 -m http.server 8000    # open http://localhost:8000/watch.html?debug
```

**After uploading:**

```sh
U=https://movies.filotcdn.org/slot-otter-classic
for f in watch.html v1/master.m3u8 v1/720p/index.m3u8 v1/720p/seg_00000.ts v1/poster.jpg v1/captions.en.vtt; do
  echo "== $f"; curl -sI $U/$f | grep -iE '^(HTTP|content-type|cache-control|cf-cache-status)'
done
ffprobe -v error -show_entries format=duration:stream=width,height -of compact $U/v1/master.m3u8
```

Expected: `200` and the content types in the table; ffprobe lists the four rungs and 609 s.

**Automatic switching, desktop (Chrome/Edge/Firefox → hls.js):** open the page with `?debug`,
maximise the window (see `capLevelToPlayerSize`), DevTools → Network → filter `m3u8|ts`.
Play, then set throttling to *Fast 4G*, then *Slow 4G*/3G or a custom 1000 kb/s profile.
Within one or two segments the requests move from `1080p/` to `720p/` to `480p/`, and the
debug line follows; remove throttling and it climbs back. There should be no stall or visible
glitch at the switch.

**Desktop Safari (native):** Web Inspector → Network shows the same rung folders. Throttle with
macOS *Network Link Conditioner* (Xcode "Additional Tools" download), which slows the whole
Mac. The debug line shows the decoded size after each switch. Safari starts on the first rung
in the master playlist (1080p) and steps down if needed; hls.js starts from a cautious
bandwidth estimate and steps up — both are normal.

**Mobile:** iPhone/iPad — *Settings → Developer → Network Link Conditioner* (after enabling
Developer Mode via Xcode), or walk away from Wi-Fi / switch to mobile data; inspect from a Mac's
Safari → Develop menu. Android Chrome — `chrome://inspect` from desktop Chrome, which gives the
same Network panel and throttling for the phone's tab. Check portrait and fullscreen, and
that the video plays inline (`playsinline`).

**Seeking:** jump to unbuffered positions (7:33, 9:53, near the end), scrub back and forth.
Expect playback within about one segment fetch, one segment request per seek, and captions in
sync. **Validation:** `./check_hls.sh`, plus Apple's `mediastreamvalidator` on a Mac if you have it.

## 7. Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| Chrome/Firefox: "blocked by CORS policy"; Safari fine | the page is not on the same host as the video (e.g. opened from another site or `file://`): serve it next to `v1/`, or add a CORS rule for that exact origin (scheme + host, no slash) and purge the cache |
| Safari: spinner forever / "operation could not be completed", Chrome fine | wrong `Content-Type` on `.m3u8` or `.ts` — check with `curl -I`, re-upload with the types in §4 |
| 404 on `…/720p/seg_00012.ts` | folder not uploaded intact or wrong prefix in the page; playlists use relative paths |
| Never goes above 480p/720p | small player (`capLevelToPlayerSize`) — maximise; or slow link; with hls.js the first segment or two start low by design |
| Frozen frames / glitch / audio pop exactly when quality changes | misaligned rungs — `./check_hls.sh` fails; re-encode with `make_hls.sh`, never mix in segments from other encodes |
| Plays the old encode or a mix after re-encoding | cached segments — upload to a new version folder (`v2/`) and repoint `watch.html` |
| Mixed-content error | page on `https://` loading the video over `http://` |
| Colours slightly off vs the MP4 | a player ignoring colour tags; the HLS output is BT.709 which is what they assume |
| iPhone forces fullscreen / autoplay blocked | needs `playsinline`; autoplay only works with `muted` |
| hls.js `bufferStalledError` on slow links | expected warnings, not fatal; persistent stalls → add a 360p rung |
