# Port Feasibility Assessment: <Game Title> (`<TITLE_ID>`)

- **Date:** YYYY-MM-DD
- **Source Dump:** `private/dumps/<filename>.iso` (SHA-256: `<hash>`)
- **Primary XBE:** `default.xbe` (`Retail | Debug | Chihiro`, Base `<addr>`, Entry `<addr>`)
- **Secondary XBEs:** `<none or list>`

## 1. XDK & Middleware Fingerprint
- **XDK Build(s):** `<e.g., D3D8 1.0.5849, DSOUND 1.0.5849, XAPILIB 1.0.5849>`
- **LTCG Detected:** `Yes / No` (`D3D8LTCG`)
- **Engine / Middleware:** `<e.g., RenderWare 3.6, Unreal Engine 2, Custom>`
- **Audio / Video:** `<e.g., XWB/XSB + Xbox ADPCM, Bink (.bik) / XMV (.xmv)>`
- **Kernel Imports:** `<count>` ordinals (list any unusual or Xbox Live/XNet ordinals)

## 2. Feasibility Rubric (1 = Hardest / Unknown, 5 = Easiest / Best Documented)
| Criterion | Score (1–5) | Evidence / Notes |
|---|---|---|
| Engine & Community RE Knowledge | | |
| Statically Linked XDK Matchability | | |
| GPU / Shader Complexity (FFP vs. Custom Combiners/LTCG) | | |
| Control Flow (No SMC/JIT/Heavy Overlays) | | |
| Audio & Video Complexity | | |
| Executable & File Layout Simplicity | | |
| **Total Score** | **/ 30** | |

## 3. Recommended Strategy & Target Tiers
- **Recommended Framework:** `<XboxXBERecomp (D3D12) | xboxrecomp (D3D11/NV2A) | Custom Clean-Room>`
- **Reasoning:** `<1-paragraph justification grounded in XBE library versions & D3D match rate>`
- **Tier 0 Goal:** Boot natively to title screen, 10 min stability.
- **Tier 1 Goal:** First playable level with rendering, audio, and input.
- **Tier 2 Goal:** Full game, saves (`TDATA`/`UDATA`), FMVs, multi-XBE transitions.
- **Tier 3 Goal (Deferred):** Resolution scaling, widescreen, uncapped FPS.
