# Third-party notices

Impact Crater is licensed under the [Business Source License 1.1](./LICENSE). It depends on third-party software and — now or in the planned future — on third-party machine-learning models whose licences differ from the project's. This file records them so a self-hoster, a contributor or a future hosted-service operator can see what applies. Adding a model, weight file, cascade or hosted generative model to the app requires a row in the **ML assets** table (D-059; see [`CONTRIBUTING.md`](./CONTRIBUTING.md)).

Licence names below are as declared by each project on 2026-10-25. The authoritative text is each project's own licence file; run `pip-licenses` in the project virtualenv and `npx license-checker` in `frontend/` for the machine-generated list of the exact installed versions.

## ML assets: models, weights, cascades and hosted generative models

| Asset | Used by | Ships / downloads / planned | Licence | Notes |
|---|---|---|---|---|
| OpenCV Haar cascade `haarcascade_frontalface_default.xml` | `media/_face_detect.py` fallback — the face detector that runs on current installs (privacy blur, trip cast) | Ships inside whichever OpenCV wheel is installed (`cv2.data.haarcascades`); the lock currently pins `opencv-python` + `opencv-contrib-python` | Apache-2.0 (OpenCV) | D-044 |
| mediapipe face detection (legacy `mp.solutions`) | `media/_face_detect.py` first choice | Declared dependency; the API is absent in the locked mediapipe 0.10.35, so it never runs | Apache-2.0 | Removal is part of the Phase 3 detector decision |
| insightface `buffalo_l` pack (SCRFD-10GF detector + ResNet-50 ArcFace recogniser, WebFace600K) | `media/face_embed.py::InsightFaceEmbedder` — **opt-in**, `cast_backend=insightface` | Not a declared dependency — the user installs `insightface` (MIT) and `onnxruntime` (MIT) by hand; the `buffalo_l` weights are then downloaded on first use into the user's insightface home directory; never in the repo | Code: MIT. **Model pack: non-commercial research use only** per the insightface model zoo; commercial use needs a licence from insightface | Stays opt-in and off by default (D-059). Do not use for commercial or hosted-service deployments without clearance |
| Google Gemini models (`gemini-2.5-flash`, `gemini-embedding-001`) and Anthropic Claude models | every routed AI operation (`config/llm-routing.yaml`) | Remote APIs, the user's own keys | Provider terms of service | No model weights are stored locally |
| `gemini-2.5-flash-image` **outputs** (title-card background) | `pipeline/stage6_title_card.py` — opt-in per job | Generated at run time, stored in the snapshot | Gemini API Additional Terms of Service + Google's Generative AI Prohibited Use Policy. Google states it does not claim ownership of generated content; **all generated images carry a SynthID watermark**; the user is responsible for how the output is used and shared, and applicable law may require attribution | Opt-in only; the preview copy should say the card is AI-generated (S-3.1.4) |
| Pillow default bitmap / Aileron font (`ImageFont.load_default`) | title card and collage text when no system font is found; `collage.py` tries the system `arial.ttf` first | Ships with Pillow | Pillow's licence file covers the bundled font | No fonts are vendored in this repo |
| **Planned —** BeatNet (beat + downbeat tracking) | `media/music.py` `MusicAnalyzer` swap, with E-3.1 (torch) | Not yet a dependency | BeatNet repo: **CC BY 4.0** (attribution required here). It depends on madmom, whose bundled models are CC BY-NC-SA 4.0 — the adoption story must confirm BeatNet uses only madmom's BSD-licensed decoder code, not its models | ADR-0012 amendment 2026-10-25 |
| **Planned —** open_clip / SigLIP image embedder checkpoint | `media/image_embed.py::LocalClipImageEmbedder` (stub today), S-2.10.8 | Not yet; weights would be downloaded to the user's cache at first use | open_clip code: MIT. LAION-trained CLIP checkpoints: MIT. SigLIP WebLI checkpoints: Apache-2.0 per their Hugging Face model cards. DataComp / DFN checkpoints carry their own terms | Pin one checkpoint and record it here before the flag flips (ADR-0018) |
| **Candidate —** OpenCV Zoo YuNet `face_detection_yunet_*.onnx` | detector upgrade, Phase 3 (plan §4.3 #14) | Not yet | MIT (model directory); OpenCV Zoo overall Apache-2.0 | Permissive replacement for the Haar cascade |
| **Candidate —** OpenCV Zoo SFace `face_recognition_sface_*.onnx` | permissive identity-embedding alternative to insightface | Not yet | Per its OpenCV Zoo model-directory licence (Apache-2.0 at last check — verify on adoption) | Preferred over insightface for any non-research deployment (D-059) |

## Runtime dependencies (Python, `pyproject.toml`)

| Package | Licence |
|---|---|
| fastapi | MIT |
| uvicorn | BSD-3-Clause |
| pydantic, pydantic-settings | MIT |
| aiosqlite, aiofiles | MIT / Apache-2.0 |
| cryptography | Apache-2.0 OR BSD-3-Clause |
| anthropic (SDK) | MIT |
| google-genai (SDK) | Apache-2.0 |
| tenacity | Apache-2.0 |
| jinja2 | BSD-3-Clause |
| pyyaml | MIT |
| numpy | BSD-3-Clause |
| pillow | MIT-CMU (HPND) |
| pillow-heif | BSD-3-Clause; wheels bundle libheif (LGPL-3.0) and HEVC / AV1 codecs under their own licences (x265 is GPL-2.0 where an encoder is bundled) — verify per pinned version before redistributing |
| imagehash | BSD-2-Clause |
| scenedetect (PySceneDetect) with opencv-python-headless | BSD-3-Clause; OpenCV Apache-2.0 |
| ffmpeg-python | Apache-2.0 |
| librosa | ISC |
| soundfile | BSD-3-Clause; wheels bundle libsndfile (LGPL-2.1) |
| piexif | MIT |
| mediapipe | Apache-2.0 |
| google-auth-oauthlib, google-api-python-client | Apache-2.0 |

## Runtime dependencies (frontend, `frontend/package.json`)

React, React Router, Vite, Tailwind CSS and the other npm packages are MIT; TypeScript is Apache-2.0. The built bundle under `frontend/dist/` (and the packaged `impact_crater/frontend_dist/`) contains their code.

## External tools the user installs

| Tool | Licence | Notes |
|---|---|---|
| ffmpeg / ffprobe | LGPL-2.1-or-later or GPL-2.0-or-later depending on the build; the Gyan.FFmpeg Windows builds the setup guide points at are GPL | Invoked as a subprocess; not bundled or linked |

## Content and conduct

`CODE_OF_CONDUCT.md` is adapted from the Contributor Covenant 2.1 (CC BY 4.0). The documentation site is built with MkDocs Material (MIT).
