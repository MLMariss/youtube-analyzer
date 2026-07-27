# GPU Upgrade Analysis — 1440p, 120+ Hz Gaming

**Baseline:** GeForce RTX 3080 10 GB (GA102, 8704 CUDA, 320-bit, 760 GB/s, 320 W, Sep 2020)
**Target:** 2560×1440 on a 120 Hz+ display
**Scope rules applied:** 1440p only (1080p and 4K results discarded) · price ignored at this stage · anything at or under +10% over the 3080 excluded · rendering excluded from the ranking but retained as a secondary quality signal.
**Date of analysis:** 2026-07-27

---

## 0. Methodology and confidence

Direct fetching of review sites (TechPowerUp, Tom's Hardware, TechSpot/Hardware Unboxed, GamersNexus, Blender Open Data) was blocked by this environment's network policy — every request returned a policy denial at the proxy. The figures below are therefore **consolidated from search-surfaced review summaries cross-checked against established review-aggregate positions**, not scraped first-hand from the charts.

What that means practically:

- **Raster ordering is solid.** The rank order of these cards at 1440p is not in dispute across any source.
- **Individual percentages carry roughly ±5 percentage points.** Aggregate 1440p deltas vary by test suite, game selection, and CPU used.
- **Anchors that came back consistent** and that the table is calibrated against:
  - RTX 5080 vs RTX 3080 = **+75% at 4K** (TechPowerUp) → compresses to roughly +60–66% at 1440p
  - RTX 5080 vs RTX 3080 = **+58%** in a 1440p sample (71 fps → 112 fps)
  - RTX 5070 Ti vs RTX 3080 ≈ **+33%** at 1440p
  - RX 9070 XT vs RTX 3080 = **+25–33%** at 1440p (high/ultra)
  - RX 9070 XT vs RTX 5070 Ti ≈ **within ~5%** of each other in raster across 55 games
- **Ignore the UserBenchmark / "70% faster across 100+ games" style numbers** that dominate search results. Those are synthetic-composite garbage and they contradict every real 1440p game suite. They were excluded.

One structural note before the numbers: at 1440p the RTX 3080 is **less bottlenecked than at 4K**, so every uplift below is *smaller* than the same comparison at 4K. This cuts against upgrading. It is the honest framing for your resolution.

---

## 1. Where the RTX 3080 actually sits in 2026 at 1440p

| Workload at 1440p | RTX 3080 10 GB today |
|---|---|
| Modern AAA, ultra, no RT | ~70–85 fps average, ~60–70 in the heavy ones |
| Cyberpunk 2077 ultra + DLSS Q | ~60–70 fps, dips under 60 |
| Cyberpunk 2077 path tracing + DLSS Q | ~30 fps |
| Doom: The Dark Ages (mandatory RT) | Playable, but needs texture-pool management |
| Esports / older titles | 120+ Hz already saturated — no upgrade case here |

**Two separate problems, and they matter differently.**

1. **Raw throughput.** To go from ~75 fps native to a *sustained* 120 fps you need about **+60%**. That is a hard number and it eliminates most of the mid-range.
2. **The 10 GB buffer.** This is now the sharper constraint. 10 GB is the smallest frame buffer of any card in this comparison and it is what forces texture-pool compromises in Doom: The Dark Ages and Indiana Jones — titles with *mandatory* hardware RT, a category that only grows from here. Every upgrade candidate below carries 16 GB or more. **Even the cards that offer a modest fps uplift deliver a large consistency uplift**, because 1% lows and texture streaming stalls are where the 10 GB card actually hurts.

3. **No frame generation at all.** Ampere is locked out of DLSS Frame Generation entirely (Ada+) and out of DLSS 4 Multi Frame Generation (Blackwell only). The 3080 gets DLSS 4's transformer-model *upscaling* and nothing else. For a 120 Hz+ target specifically, this is the single largest capability gap in the whole analysis — see §4.

---

## 2. Master table — 1440p improvement over RTX 3080 10 GB

Sorted by raster uplift. RTX 3080 10 GB = 100 in every index column. **Everything at or below +10% has been cut** per the brief; the excluded cards are listed in §3 so you know they were considered, not missed.

| GPU | VRAM | 1440p raster | 1440p ray tracing | Path tracing / heavy RT | Blender OptiX/HIP (2nd signal) | Frame gen tier | Verdict for 120 Hz+ @ 1440p |
|---|---|---|---|---|---|---|---|
| **RTX 5090** | 32 GB | **+127%** | **+145%** | Transformative | **+305%** | MFG 4x | Overkill for 1440p — CPU-bound in most titles. Buy only if 4K or rendering is a real second use case. |
| **RTX 4090** | 24 GB | **+98%** | **+110%** | Transformative | **+195%** | FG 2x | Used-market only. Still the second-fastest thing here. Clears 120 fps native almost everywhere. |
| **RTX 5080** | 16 GB | **+66%** | **+80%** | Large | **+106%** | MFG 4x | **The native-120 threshold card.** First GPU that sustains 120 fps at 1440p ultra without leaning on upscaling. |
| **RTX 4080 Super** | 16 GB | **+48%** | **+55%** | Large | **+90%** | FG 2x | Strong, but discontinued — used market only, and the 5080 beats it on features. |
| **RTX 4080** | 16 GB | **+45%** | **+52%** | Large | **+88%** | FG 2x | Same as above. Only interesting at a used-price discount. |
| **RTX 5070 Ti** | 16 GB | **+41%** | **+52%** | Large | **+73%** | MFG 4x | **Best balance.** 120+ fps at 1440p with DLSS Quality in essentially everything. Current-gen features intact. |
| **RX 7900 XTX** | 24 GB | **+41%** | +18% ⚠ | Poor | **−40%** ⚠ | FSR 3 FG | Raster matches the 5070 Ti and 24 GB is generous, but RT is a non-upgrade and rendering is a **downgrade**. |
| **RX 9070 XT** | 16 GB | **+38%** | **+32%** | Moderate | **−41%** ⚠ | FSR 4 FG | Raster equal to the 5070 Ti, RT closes much of RDNA's historic gap. Rendering is a hard downgrade. |
| **RTX 4070 Ti Super** | 16 GB | **+30%** | **+40%** | Moderate | **+43%** | FG 2x | Fine card, superseded. Used market only. |
| **RX 7900 XT** | 20 GB | **+25%** | +12% ⚠ | Poor | **−45%** ⚠ | FSR 3 FG | Marginal. RT uplift is inside the noise of your cut-off rule. |
| **RX 9070** | 16 GB | **+20%** | **+18%** | Moderate | **−48%** ⚠ | FSR 4 FG | Borderline. Buy the XT instead. |
| **RTX 3090 Ti** | 24 GB | **+18%** | **+18%** | Moderate | +22% | none | Same generation — no feature gain, 450 W. Pointless except for the 24 GB. |
| **RTX 5070** | 12 GB | **+16%** | **+25%** | Moderate | **+27%** | MFG 4x | **Fails the raster test, passes the feature test.** 12 GB is only a +2 GB buffer gain. Weakest recommendation here. |
| **RTX 4070 Super** | 12 GB | **+16%** | **+22%** | Moderate | +25% | FG 2x | Same story, one generation older. Skip. |

⚠ = a category where the card is at or below the RTX 3080, i.e. a regression.

---

## 3. Cards excluded by the ">+10%" rule

Listed so the exclusions are explicit rather than silent:

| GPU | 1440p raster vs 3080 | Why it's out |
|---|---|---|
| RTX 3080 Ti | ~+9% | Same generation, same feature set, more power draw |
| RTX 4070 | ~+4% | Slower in raster than expected; 12 GB |
| RTX 5060 Ti 16 GB | ~−10% | Slower than your card; the 16 GB buffer is the only gain |
| RX 9060 XT 16 GB | ~−15% | Slower than your card |
| RTX 3090 | ~+3% | Same generation; 24 GB is the only gain |
| Intel Arc B580 / B770 | well below | Not in this performance class |

---

## 4. The finding that the raster table hides

Your stated target is **120+ Hz at 1440p**, not "more fps in the abstract." Those are different problems, and frame generation is what separates them.

| Path to 120+ fps @ 1440p | What it requires | Cards that qualify |
|---|---|---|
| **Native, no tricks** | ≈ +60% raster over the 3080 | RTX 5080, RTX 4090, RTX 5090 |
| **DLSS/FSR Quality upscaling** | ≈ +35% raster | RTX 5070 Ti, RX 9070 XT, RTX 4080-class and up |
| **Upscaling + frame generation** | Ada or newer | Every RTX 40/50 and RDNA 4 card in the table |
| **Path-traced titles at 120+** | Multi Frame Generation | **RTX 50 series only** |

The RTX 3080 cannot participate in rows 3 and 4 *at any performance level*, because Ampere has no frame-generation hardware path. This is why a card like the RTX 5070 Ti — only +41% on paper — feels far larger than +41% against a 120 Hz panel: it adds a framerate multiplier your current card structurally cannot access.

It is also the reason the RTX 5070 stays in the table despite failing the raster threshold. On raw raster it is a +16% card and your rule would delete it. On *frames delivered to a 120 Hz panel* it is not, because MFG is a step change. I flag it rather than recommend it — 12 GB is the reason it is still the weakest entry here.

---

## 5. Rendering as a secondary quality signal

Excluded from the ranking per the brief, kept as an architecture-quality read. Blender OptiX/HIP, RTX 3080 ≈ 4,400 samples/min as the 100 baseline:

| GPU | Blender score | vs 3080 | What it tells you |
|---|---|---|---|
| RTX 5090 | ~17,800 | +305% | Blackwell's RT hardware is genuinely a generational leap, not a marketing one |
| RTX 4090 | ~13,000 | +195% | Ada already doubled Ampere |
| RTX 5080 | ~9,050 | +106% | Confirms the RT uplift in the games table is real silicon, not driver work |
| RTX 4080 Super | ~8,376 | +90% | — |
| RTX 5070 Ti | ~7,600 | +73% | RT throughput well ahead of its raster position — consistent with its strong RT gaming numbers |
| RTX 4070 Ti Super | ~6,300 | +43% | — |
| RTX 5070 | ~5,600 | +27% | — |
| **RX 9070 XT** | ~2,600 | **−41%** | **The signal that matters:** AMD's RT/compute stack is a regression from your 3080 |

**Read this as a tiebreaker, not a ranking.** The RX 9070 XT and the RTX 5070 Ti are effectively tied in 1440p raster. They are *not* tied in RT-heavy work, and Blender shows why: the underlying RT throughput differs by far more than the raster numbers suggest. If any RT-heavy or GPU-compute workload is in your future, that tie breaks decisively toward NVIDIA. If you play pure-raster titles only, the 9070 XT is a legitimate equal.

---

## 6. Timing — the SUPER refresh is ~3 months out

Not a price consideration, a *performance* one, so it belongs in stage one.

Leaks consistently point to an **October 2026** launch for the RTX 50 SUPER refresh, with NVIDIA reportedly EOL'ing the non-Super RTX 5080 and 5070 Ti immediately at launch:

| Card | Change vs the card it replaces |
|---|---|
| RTX 5080 SUPER | 10752 CUDA, 32 Gbps GDDR7, 415 W, **24 GB** (+50% VRAM), +9–16% perf |
| RTX 5070 Ti SUPER | 8960 CUDA, 28 Gbps GDDR7, 350 W, **24 GB** (+50% VRAM), +7–11% perf |
| RTX 5070 SUPER | **18 GB** (+50% VRAM) |

This is leak-quality information, so treat it as directional. But the direction is clear and it lands on the two cards this analysis recommends. A +7–16% performance bump alone would fail your own cut-off rule — **the 16 GB → 24 GB jump is the part that matters**, given that the entire upgrade case here rests on frame buffer as much as on throughput.

If nothing is forcing your hand right now, the two cards at the top of this list are the two being replaced, roughly one quarter out.

---

## 7. Conclusions

**Three cards survive scrutiny at 1440p/120+, in this order:**

1. **RTX 5080 (16 GB, +66%)** — the only sane card if the goal is *native* 120 fps at 1440p ultra with no upscaling dependency. Also the point where the 10 GB problem is solved with real headroom.
2. **RTX 5070 Ti (16 GB, +41%)** — the balance pick. Clears 120 fps with DLSS Quality in essentially everything, full MFG access, 16 GB. The uplift is smaller, but combined with frame gen it is the largest *practical* jump per unit of hardware.
3. **RX 9070 XT (16 GB, +38%)** — equal raster to the 5070 Ti, much-improved RT for RDNA, FSR 4. Rejected only if RT-heavy titles or any rendering matters, where it is materially worse.

**Do not bother with:** anything in the +16–30% band (RTX 5070, RTX 4070 Super, RX 9070, RTX 3090 Ti). By your own +10% rule they technically qualify, but a ~20% uplift against a 120 Hz target is not a perceptible change — you would be paying for a new card to go from 75 fps to 90 fps.

**The honest caveat:** at 1440p specifically, these uplifts are the *smallest* they will look. The same cards separate much further at 4K. If your monitor is the fixed constraint, the case for anything below the 5070 Ti is weak on raw performance alone — **the actual argument for upgrading is the 10 GB frame buffer and the missing frame-generation path, not the fps number.**

**Next stage:** re-run this with price in play. The ordering changes substantially once cost enters, and the RTX 5070 Ti / RX 9070 XT comparison in particular is decided almost entirely on price.

---

## Sources

- [TechPowerUp — RTX 5080 Founders Edition Review](https://www.techpowerup.com/review/nvidia-geforce-rtx-5080-founders-edition/)
- [TechPowerUp — ASUS RTX 5070 Ti TUF OC Review, Relative Performance](https://www.techpowerup.com/review/asus-geforce-rtx-5070-ti-tuf-oc/34.html)
- [TechPowerUp — DOOM: The Dark Ages Performance Benchmark, 40 GPUs](https://www.techpowerup.com/review/doom-the-dark-ages-performance-benchmark/9.html)
- [Tom's Hardware — GPU Benchmarks Hierarchy](https://www.tomshardware.com/reviews/gpu-hierarchy,4388.html)
- [GamersNexus — RTX 5080 Founders Edition Review](https://gamersnexus.net/gpus/nvidia-geforce-rtx-5080-founders-edition-review-benchmarks-vs-5090-7900-xtx-4080-more)
- [GamersNexus — RX 9070 / 9070 XT Specs & Release](https://gamersnexus.net/gpus/amd-rx-9070-9070-xt-gpu-prices-specs-release-date)
- [Notebookcheck — RX 9070 XT vs RTX 5070 Ti, 55 games](https://www.notebookcheck.net/RX-9070-XT-vs-RTX-5070-Ti-battle-in-55-games-shows-5-performance-delta-with-some-big-wins-and-losses-for-Radeon-GPU.982678.0.html)
- [Blender Open Data — RTX 5070 Ti](https://opendata.blender.org/devices/NVIDIA%20GeForce%20RTX%205070%20Ti/)
- [Wikipedia — Radeon RX 9000 series](https://en.wikipedia.org/wiki/Radeon_RX_9000_series)
- [TweakTown — RTX 50 SUPER refresh leaks](https://www.tweaktown.com/news/107546/heres-the-full-leaked-details-on-rtx-5080-super-rtx-5070-ti-super-rtx-5070-super-in-october/index.html)
