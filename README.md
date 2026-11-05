# Waymark

**Teach an indoor route once. Verify its landmarks on the way back.**

Waymark turns operator-recorded indoor observations into an evidence-linked topological graph. Meta Muse Spark Open reads static visual landmarks and signage, then compares a new observation against learned reference images. A deterministic verifier holds the location unless the expected landmark has sufficient visual support, matching learned signage, and two distinct image observations.

Built for the Meta Global AI Developer Hackathon, Indie Developer / Build for Your World, November 4, 2026. Intended direction: indoor spaces without reliable GPS, such as offices, event venues and airport interiors. No airport deployment or navigation accuracy is claimed.

## Run

Python 3.10+; no Python packages required for the app.

```sh
export FIREWORKS_API_KEY=your_existing_key
python3 server.py
```

Open http://127.0.0.1:8881. The Meta model is `accounts/fireworks/models/muse-spark-open` through Fireworks' OpenAI-compatible inference endpoint. There is no alternate-model fallback or canned model response. Requests consume your provider account's credits. The app can alternatively read a private `.env` containing FIREWORKS_API_KEY. On the author's Mac it can reuse the sibling Mentra prototype's private .env without copying its contents.

## Try the workflow

1. Choose **Teach demo route**. This makes three real Meta vision calls on authored illustrated scene fixtures: Atrium, East lifts, Quiet lounge.
2. Verify **Lifts · east wing**. The first supported observation requests confirmation; it does not advance the route.
3. Verify the exact same image again. The image fingerprint blocks it from counting as a second distinct observation.
4. Choose **Lifts · wrong wing** and verify. The West Wing text contradicts the reference; the location should stay held. Model decisions remain fallible, so inspect the evidence.
5. Choose East lifts again, then its second view. When Meta supports both distinct images, the route advances to East lifts.
6. Close a taught link. The planner finds an available taught path or reports that no route is available; it never invents a corridor.
7. Export the route and evidence as JSON. The exported file includes reference images. Review it before sharing.

The seven fixtures are original programmatic illustrations, not camera captures or photos. The second-view fixtures are cropped versions of their original illustration. Their role is to exercise the distinct-image gate and real Meta visual matching; they do not establish independent physical observations or real-world robustness. Hardware-independent replay is clearly labeled in the interface.

## Mentra Live

Connect a Mentra Live by USB, allow the accessory on macOS, install FFmpeg, and choose **Mentra USB camera**. The inherited AVFoundation adapter selects the exact `Mentra Camera` name, captures 1280×720, shares a 10 fps preview, rejects frames older than two seconds and keeps a bounded 30-frame RAM buffer. There is no automatic laptop camera fallback. Selecting the camera starts capture; leaving that source releases it once the stream disconnects.

The new Waymark workflow has not been tested with physical glasses: the hardware was unavailable during this build. Speech, microphone, obstacle avoidance, turn-by-turn directions, SLAM, metric localization, accessibility certification and autonomous airport mapping are not implemented. The UI runs on the connected Mac; Mentra Live has no in-lens display.

## Architecture and verification

`Image / USB frame → Meta static-landmark observation → learned-reference comparison → deterministic evidence gate → route state → graph planner → evidence trail`

- Meta reads signs, distinctive cues, candidate reference ID, uncalibrated match confidence and evidence rationale.
- The local gate rejects an unknown candidate, a candidate other than the next checkpoint, confidence below 0.85, absent exact learned signage, repeated identical image, or a second image arriving more than 120 seconds after the first.
- Uncertain evidence clears any pending confirmation. A first supported image creates a pending confirmation; a second distinct supported image advances one checkpoint.
- Edges are operator-recorded traversal assertions, never inferred from image similarity. The graph uses unweighted shortest paths over open recorded links. Its layout is schematic, not a reconstructed floor plan.
- A selected starting point is an explicit operator assertion, labeled as such in the trail.
- Confidence is a model judgment, not a calibrated probability. Two images are not proof of physical location. Shared signs, stale images and model mistakes remain limitations.

```sh
python3 -m unittest -v test_waymark
```

Tests cover closed edges, reverse routes, alternate routes, unknown/wrong candidates, confidence without signage, repeated images, uncertain-view reset, malformed JSON, file traversal and invalid image payloads. These deterministic tests mock the model; live Meta evidence is reported separately in `evidence/live-verification.json` when present.

## Privacy and scope

Server binds to loopback only, validates Host and Origin, and requires a per-run request token for changes. Keys stay server-side. Reference images and graph state remain in RAM until cleared or the process exits. Images are sent to Fireworks for Meta inference on explicit Remember/Verify actions. Provider retention is governed by its terms; this is not a claim of end-to-end private inference. Export is an explicit local download containing images. Never collect bystanders or restricted venue imagery without permission.

## Original contributions and provenance

New during this event (November 4): the Waymark app, route graph, Meta adapter and structured observation prompt, reference-image matching, two-image/signage gate, closed-link planning, evidence trail/export, illustrated replay fixtures, UI, tests and submission/demo materials.

Pre-existing: `live_camera.py` is reused from the author's Mentra Look prototype built in late October. It is camera transport scaffolding only; it is not presented as a new Waymark invention. No game mode or earlier DeepSeek/Gemma assistant is included in this entry.

UI direction: Taste framed-sheet, seed 680891324; teal route data on a neutral white work surface. IBM Plex Sans is loaded from Google Fonts; offline fallback is the system sans-serif. All scene art is original; no stock photographs or unlicensed media.

## Why this matters

Indoor assistance needs memory of a specific space and a way to admit uncertainty. Waymark combines a learned route, visual reference memory and a conservative progress gate. Its strongest demonstration is a wrong-wing image that looks similar but cannot advance the wearer. A real deployment needs independent scene data, venue permission, calibrated localization, accessibility testing and physical hardware validation.

MIT License.
