# GPU Upgrade Analysis — 1440p, 120+ Hz Gaming (Narrowed)

**Baseline:** GeForce RTX 3080 10 GB (GA102, 8704 CUDA, 320-bit, 760 GB/s, 320 W, Sep 2020)
**Target:** 2560×1440 on a 120 Hz+ display
**Date:** 2026-07-27

### Scoring rules

| Rule | Applied as |
|---|---|
| 1440p only | 1080p and 4K results discarded |
| **Frame generation is worthless** | **Excluded entirely — no card gets any credit for DLSS FG, MFG, or FSR FG** |
| Raster = main focus | weight **0.5** |
| Ray tracing = next to it | weight **0.3** |
| Rendering = weak secondary signal | weight **0.2** |
| Price | still ignored at this stage |
| Cut-off | anything at or under **+10%** composite over the 3080 is dropped |

**Composite score = (0.5 × raster) + (0.3 × ray tracing) + (0.2 × rendering)**, all indexed to RTX 3080 10 GB = 100.

---

## 0. What changed by removing frame generation

Two things, and both matter:

1. **The RTX 50 series lost its structural advantage.** MFG was the only thing Blackwell had that Ada didn't. Judged purely on silicon, the **RTX 4080 Super now outranks the RTX 5070 Ti** (+59% vs +51% composite). The RTX 40 series is back in genuine contention — subject to it being used-market only.
2. **The RTX 5070 lost its entire rationale.** In the previous pass it survived on MFG access alone. On raw silicon it is a +16% raster, 12 GB card. It clears the +10% cut on composite but it is now the weakest thing in the table.

**Assumption I'm making, flag it if wrong:** I've treated *upscaling* (DLSS/FSR Quality) as still acceptable, since it renders real frames and is a different technique from frame generation. If you reject upscaling too, jump to §4 — the qualifying list shrinks to three cards.

---

## 1. Methodology and confidence

Direct fetching of review sites was blocked by this environment's network policy — TechPowerUp, Tom's Hardware, TechSpot, GamersNexus and Blender Open Data all returned proxy denials. Figures are **consolidated from search-surfaced review summaries cross-checked against established aggregate positions**, not scraped first-hand.

- **Rank order is solid.** No source disputes it.
- **Individual percentages carry ~±5 pp.**
- **UserBenchmark-style composites were excluded** — they contradict every real 1440p game suite.
- At 1440p your 3080 is less bottlenecked than at 4K, so **every uplift here is smaller than the same comparison at 4K**. That is the honest framing for your resolution.

---

## 2. Master table — composite ranking

RTX 3080 10 GB = 100 in all index columns. Sorted by composite score.

| # | GPU | VRAM | Raster (0.5) | RT (0.3) | Render (0.2) | **Composite** | Raster+RT only |
|---|---|---|---|---|---|---|---|
| 1 | **RTX 5090** | 32 GB | +127% | +145% | +305% | **+168%** | +133% |
| 2 | **RTX 4090** | 24 GB | +98% | +110% | +195% | **+121%** | +102% |
| 3 | **RTX 5080** | 16 GB | +66% | +80% | +106% | **+78%** | +71% |
| 4 | **RTX 4080 Super** | 16 GB | +48% | +55% | +90% | **+59%** | +51% |
| 5 | **RTX 4080** | 16 GB | +45% | +52% | +88% | **+56%** | +48% |
| 6 | **RTX 5070 Ti** | 16 GB | +41% | +52% | +73% | **+51%** | +45% |
| 7 | **RTX 4070 Ti Super** | 16 GB | +30% | +40% | +43% | **+36%** | +34% |
| 8 | RTX 5070 | 12 GB | +16% | +25% | +27% | +21% | +19% |
| 9 | **RX 9070 XT** | 16 GB | +38% | +32% | **−41%** ⚠ | **+20%** | **+36%** |
| 10 | RTX 4070 Super | 12 GB | +16% | +22% | +25% | +20% | +18% |
| 11 | RTX 3090 Ti | 24 GB | +18% | +18% | +22% | +19% | +18% |
| 12 | RX 7900 XTX | 24 GB | +41% | +18% | **−40%** ⚠ | +18% | +32% |

**Dropped by the +10% composite cut:**

| GPU | Composite | Why |
|---|---|---|
| RX 7900 XT | +7% | Weak RT plus rendering regression sinks it below the line |
| RX 9070 | +6% | Same — the 0.2 rendering weight is what kills it |
| RTX 3080 Ti | +9% | Same generation, no gain worth having |
| RTX 4070 / 3090 / 5060 Ti / RX 9060 XT | ≤ +5% or negative | Not in class |

---

## 3. The 0.2 rendering coefficient is decisive for AMD — read this before you act

Compare the last two columns for the Radeon cards. This is the most important thing in the table:

| GPU | Composite (with 0.2 render) | Raster+RT only | Rank swing |
|---|---|---|---|
| RX 9070 XT | +20% → **9th** | +36% → **6th** | **−3 places** |
| RX 7900 XTX | +18% → 12th | +32% → 8th | −4 places |
| RX 9070 | +6% → **cut** | +19% → survives | **cut entirely** |

**Why this happens:** the rendering coefficient is small, but AMD's rendering figure is *negative* — the RX 9070 XT is ~41% **slower than your current RTX 3080** in Blender. A small weight on a large negative still drags hard. Every NVIDIA card in the table has rendering as a *bonus*; for AMD it's a penalty.

**My read, stated plainly:** you said you don't render much. A 0.2 coefficient is a meaningful weight — it's one fifth of the total score — and it is currently the single factor removing the RX 9070 XT from your shortlist. On pure gaming merit the 9070 XT is a legitimate 6th-place card at +36%, essentially tied with the RTX 5070 Ti in raster. **If "not much rendering" really means "almost never," 0.2 is too high and you should look at the Raster+RT column instead.** I've kept both columns so the choice is yours rather than buried in a formula.

---

## 4. Hitting 120+ fps at 1440p without frame generation

With FG off the table, the bar is materially higher. These are the honest thresholds:

| Path | Requirement | Cards that qualify |
|---|---|---|
| **Native 1440p ultra, 120 fps sustained** | ≈ +60% raster | **RTX 5080, RTX 4090, RTX 5090** — and nothing else |
| **DLSS/FSR Quality upscaling, 120 fps** | ≈ +35% raster | + RTX 4080/4080 Super, RTX 5070 Ti, RX 9070 XT |
| **Path-traced titles at 120 fps** | not achievable | No card in this list does this without MFG |

Your 3080 currently averages ~70–85 fps at 1440p ultra (~60–70 in heavy titles). Going native-120 needs roughly **+60%**, which is why the qualifying list is so short.

**The 10 GB buffer is still the sharpest problem** and it's independent of the fps question. Every card in the table above carries 16 GB or more except the two 12 GB entries. Doom: The Dark Ages and Indiana Jones — both with mandatory hardware RT — already force texture-pool compromises on 10 GB at 1440p. That category only grows. Expect the frame-buffer upgrade to improve 1% lows and streaming stalls by more than the average-fps numbers suggest.

---

## 5. Which specific card to buy — manufacturer models

Board partner choice barely affects performance (5070 Ti models sit within 57 MHz / 2–3 fps of each other). **Buy on cooling, noise, and physical size.**

### RTX 5080 — the native-120 pick

| Model | Verdict |
|---|---|
| **MSI Suprim SOC** | ✅ **Best overall.** Among the strongest cooling tested, whisper-quiet |
| **ASUS TUF OC** | ✅ **Best value pick.** ~60–62 °C at 1100 rpm, low noise, cheaper than Suprim |
| **Gigabyte Aorus Master** | ✅ Top-tier cooling, on par with Suprim |
| **Zotac Solid OC** | ✅ Cheapest better-than-reference — **the full 3.5-slot version, not the Slim** |
| Founders Edition | ⚪ Compact 2-slot, fine, but harder to find |
| ASUS ROG Astral OC | ❌ **Avoid.** Single-digit gains, higher power draw, *louder* than the FE, big premium |

### RTX 5070 Ti — the balance pick

| Model | Verdict |
|---|---|
| **ASUS TUF Gaming OC** | ✅ 58 °C, ~2716 MHz sustained, marginally louder than Gigabyte |
| **MSI Gaming Trio** | ✅ Large design, best thermal tier |
| **Gigabyte Gaming OC / Windforce OC** | ✅ 65 °C — warmest of the group but still cool and quiet |
| **MSI Ventus 3X OC** | ✅ **Best if space is tight.** Compact, clean, easy install, +45 MHz |
| Gigabyte Eagle OC Ice SFF | ⚪ SFF option if the build demands it |

### RX 9070 XT — only if you drop the rendering weight (see §3)

| Model | Verdict |
|---|---|
| **Sapphire Nitro+** | ✅ Top performance tier |
| **ASRock Taichi** | ✅ Top performance tier |
| **XFX Mercury** | ✅ Top performance tier |
| **PowerColor Red Devil** | ✅ **Best thermals.** Joint-best noise-normalised; hits the noise floor out of the box |
| Sapphire Pure / Gigabyte Elite / ASUS TUF | ⚪ Solid mid-tier |
| XFX Swift, XFX Quicksilver, Sapphire Pulse | ❌ Weakest performers in the 14-card roundup |

### RTX 5090 — only if 4K or rendering is a real second use case

| Model | Verdict |
|---|---|
| **MSI Suprim Liquid SOC** | ✅ Quiet, excellent GPU + VRAM temps, dumps 600 W outside the case |
| **Gigabyte Aorus Master / Waterforce** | ✅ Very good temps, pump inaudible |
| **ASUS ROG Astral OC** | ✅ PTM7950 compound, quad-fan, holds OC records — but expensive |

### RTX 4080 Super / 4080 / 4070 Ti Super

Used market only — discontinued. Model choice is whatever arrives in good condition; prioritise a triple-fan card with verifiable history over a specific brand. Note these have **no warranty runway**, which is the real cost of their strong composite scores.

---

## 6. Timing — the SUPER refresh is ~3 months out

Leaks point to **October 2026**, with NVIDIA reportedly EOL'ing the non-Super 5080 and 5070 Ti at launch:

| Card | Change |
|---|---|
| RTX 5080 SUPER | 10752 CUDA, 32 Gbps GDDR7, 415 W, **24 GB** (+50%), +9–16% perf |
| RTX 5070 Ti SUPER | 8960 CUDA, 28 Gbps GDDR7, 350 W, **24 GB** (+50%), +7–11% perf |
| RTX 5070 SUPER | **18 GB** (+50%) |

Leak-quality, so directional only. The +7–16% performance bump fails your own cut-off rule on its own — **the 16 → 24 GB jump is the part that matters**, since the upgrade case rests as much on frame buffer as on throughput. The two cards at the top of your shortlist are the two being replaced, one quarter out.

---

## 7. Conclusions

**Buy one of these three:**

1. **RTX 5080 — +78% composite.** The only current-gen card that sustains native 120 fps at 1440p ultra with no upscaling dependency. Best model: **MSI Suprim SOC** or **ASUS TUF OC**.
2. **RTX 5070 Ti — +51% composite.** Clears 120 fps with DLSS Quality in essentially everything, 16 GB, full warranty. Best model: **ASUS TUF Gaming OC** or **MSI Ventus 3X OC** if space is tight.
3. **RTX 4080 Super — +59% composite.** Outranks the 5070 Ti on silicon now that FG is excluded. Only worth it at a real used-market discount, and accept the warranty risk.

**The AMD question:** the **RX 9070 XT** is 6th on gaming merit (+36% raster+RT) and 9th once your 0.2 rendering weight applies (+20%). It is a genuinely good raster card knocked out by one fifth of the scoring formula. Decide whether 0.2 reflects how little you actually render — if it doesn't, it belongs back on the shortlist, with the **Sapphire Nitro+** or **PowerColor Red Devil**.

**Don't buy:** RTX 5070, RTX 4070 Super, RTX 3090 Ti, RX 9070, RX 7900 XT. A ~20% uplift against a 120 Hz panel is not perceptible — you'd be paying to go from 75 fps to 90 fps.

**The honest caveat, unchanged:** at 1440p these uplifts are the smallest they will ever look, and without frame generation there is no multiplier to fall back on. **The real argument for upgrading is the 10 GB frame buffer, not the fps number** — anything below the 5070 Ti is hard to justify on throughput alone.

**Next stage:** re-run with price. The 5070 Ti vs 4080 Super vs 9070 XT ordering is decided almost entirely on cost.

---

## Sources

- [TechSpot — RTX 5070 Ti Roundup, 9 cards tested](https://www.techspot.com/review/3108-nvidia-geforce-rtx-5070-ti-roundup/)
- [TechSpot — RX 9070 XT Roundup, 14 cards tested](https://www.techspot.com/review/3015-amd-radeon-9070-xt-roundup/)
- [TechPowerUp — MSI RTX 5080 Suprim SOC, Temperatures & Noise](https://www.techpowerup.com/review/msi-geforce-rtx-5080-suprim-soc/39.html)
- [TechPowerUp — ASUS RTX 5080 TUF OC, Temperatures & Noise](https://www.techpowerup.com/review/asus-geforce-rtx-5080-tuf-oc/39.html)
- [TechPowerUp — RTX 5080 Founders Edition Review](https://www.techpowerup.com/review/nvidia-geforce-rtx-5080-founders-edition/)
- [TechPowerUp — DOOM: The Dark Ages, 40 GPUs](https://www.techpowerup.com/review/doom-the-dark-ages-performance-benchmark/9.html)
- [KitGuru — PowerColor RX 9070 XT Red Devil Review](https://www.kitguru.net/components/graphic-cards/dominic-moass/powercolor-rx-9070-xt-red-devil-review/all/1/)
- [PC Gamer — ASUS TUF Gaming RTX 5070 Ti OC Review](https://www.pcgamer.com/hardware/graphics-cards/asus-tuf-gaming-rtx-5070-ti-oc-edition-review/)
- [Notebookcheck — MSI RTX 5070 Ti Ventus 3X OC Review](https://www.notebookcheck.net/MSI-GeForce-RTX-5070-Ti-16G-Ventus-3X-OC-Review-Near-perfect-mainstream-Blackwell-GPU-provided-you-can-get-one-at-749-MSRP.964050.0.html)
- [Notebookcheck — ASUS ROG Astral RTX 5080 OC Review](https://www.notebookcheck.net/Asus-ROG-Astral-GeForce-RTX-5080-OC-Edition-Review-Beautiful-bulky-and-bewilderingly-expensive.1066249.0.html)
- [Notebookcheck — RX 9070 XT vs RTX 5070 Ti, 55 games](https://www.notebookcheck.net/RX-9070-XT-vs-RTX-5070-Ti-battle-in-55-games-shows-5-performance-delta-with-some-big-wins-and-losses-for-Radeon-GPU.982678.0.html)
- [GamersNexus — RTX 5080 Founders Edition Review](https://gamersnexus.net/gpus/nvidia-geforce-rtx-5080-founders-edition-review-benchmarks-vs-5090-7900-xtx-4080-more)
- [Blender Open Data](https://opendata.blender.org/devices/NVIDIA%20GeForce%20RTX%205070%20Ti/)
- [TweakTown — RTX 50 SUPER refresh leaks](https://www.tweaktown.com/news/107546/heres-the-full-leaked-details-on-rtx-5080-super-rtx-5070-ti-super-rtx-5070-super-in-october/index.html)
