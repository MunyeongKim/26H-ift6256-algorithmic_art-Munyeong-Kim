# HW3

## Ideation Notes

Keep the scribble energy. Just translate it.

> maybe there is a day when two very distant places still end up looking at the same sun.  
> one side sunrise, the other side sunset. that feels better than moon.  
> moon is not quite it. sun has the stronger meaning.  
> write the date on it. it should feel seasonal, rare, a little surprising.  
> not flat-earth stuff. more like: people very far apart still share one moment.  
> maybe church / school / home kinds of places. places people emotionally attach to.  
> the fun part is not "same local time" but "same absolute instant".  
> one place morning, one place evening, but still the same UTC moment.  
> then show both places as drawings, and let the sun feeling connect them.  

## Overview

HW3 is a pipeline for finding pairs of distant locations where sunrise at one place nearly coincides with sunset at another in UTC time. The project matches candidate dates, downloads aligned Google Street View images, transforms them into minimal line-sketch renderings, and composes the two views into a single image.

The current matching pipeline uses the MET Norway Sunrise API for sunrise/sunset times and azimuths. Google Maps APIs are used for Street View and optional reverse geocoding. OpenAI image generation is used for the sketch rendering stages.

## What The Code Actually Does

1. Parse two locations from Google Maps URLs or latitude/longitude inputs.
2. Fetch sunrise/sunset times and azimuths from the MET Norway Sunrise API.
3. Search for near-simultaneous UTC instants where one place is sunrise and the other is sunset.
4. Download Street View images aligned to the matched sun azimuth.
5. Optionally reverse-geocode and normalize location labels.
6. Transform the Street View images into line-sketch images with OpenAI.
7. Compose the two images side by side with labels and timestamps.

The default match tolerance is `+-10 minutes`.

## Main Files

- `HW3/main.py`
  End-to-end structured pipeline.
- `HW3/find_shared_sun_instants.py`
  UTC matching logic for sunrise/sunset pairs.
- `HW3/find_and_fetch_sun_streetview.py`
  One-shot script for `match -> heading -> Street View`.
- `HW3/fetch_streetview_pair.py`
  Download two Street View images when headings are already known.
- `HW3/openai_transform_sketch.py`
  v1 two-step OpenAI sketch transform for independent images.
- `HW3/openai_transform_sketch_v7.py`
  v7 multi-reference transform pipeline.
- `HW3/openai_transform_sketch_v9.py`
  Experimental standalone prompt variant. This is not wired into `main.py`.
- `HW3/juxtapose_images.py`
  Final side-by-side composition utility.
- `HW3/utils/met_sun.py`
  MET Norway Sunrise API client used by the matching pipeline.
- `HW3/utils/open_meteo_sun.py`
  Alternative Open-Meteo utility. It exists, but it is not the default source used by `main.py`.
- `HW3/utils/reverse_geocode.py`
  Google reverse geocoding helper.
- `HW3/utils/normalize_address_llm.py`
  Optional address-label normalization with OpenAI text models.

## Requirements

- Python 3.11+
- Google Maps API key for Street View
- Google Geocoding API enabled if you want reverse-geocoded labels
- OpenAI API key if you want image transforms or address normalization

## Setup

Copy the template:

```bash
cp HW3/.env.example HW3/.env
```

Then fill in:

```env
GOOGLE_MAPS_API_KEY=...
OPENAI_API_KEY=...
```

Notes:

- `GOOGLE_MAPS_API_KEY` is required for Street View downloads.
- `OPENAI_API_KEY` is required for OpenAI image transforms.
- If you run `main.py` with `--skip-transform` and without `--normalize-addresses`, OpenAI is not required.

## Matching Only

Use the MET-based matcher directly:

```bash
python HW3/find_shared_sun_instants.py \
  --name-a KTH \
  --lat-a 59.3470612 --lon-a 18.0720447 \
  --event-a sunrise --tz-a Europe/Stockholm \
  --name-b CSU \
  --lat-b 40.57766 --lon-b -105.08177 \
  --event-b sunset --tz-b America/Denver \
  --start 2025-01-01 --end 2025-12-31 \
  --tol-min 10
```

This script prints sorted matches and can also save a CSV.

Sort behavior:

- past matches before future matches
- latest year first
- smaller time difference first
- if the difference ties, more recent instant first

## Street View Pair Only

If you already know the camera headings:

```bash
python HW3/fetch_streetview_pair.py \
  --name-a Montreal --lat-a 45.5017 --lon-a -73.5673 --heading-a 120 --pitch-a 0 \
  --name-b Beijing --lat-b 39.9042 --lon-b 116.4074 --heading-b 260 --pitch-b 0 \
  --size 640x640 --fov 90 --radius 50 \
  --outdir HW3/streetview_outputs
```

Outputs include:

- `*.jpg` Street View images
- `*_request.json`
- `*_metadata.json`

## One-Shot Match + Street View

Use `find_and_fetch_sun_streetview.py` when you want matching plus aligned Street View in one script:

```bash
python HW3/find_and_fetch_sun_streetview.py \
  --name-a PohangSunrise \
  --maps-url-a "YOUR_GOOGLE_MAPS_URL_A" \
  --event-a sunrise --tz-a Asia/Seoul \
  --name-b MontrealSunset \
  --maps-url-b "YOUR_GOOGLE_MAPS_URL_B" \
  --event-b sunset --tz-b America/Toronto \
  --match-index 1 \
  --radius 50 \
  --outdir HW3/streetview_outputs/pohang_montreal
```

Notes:

- This script accepts either `--maps-url-*` or `--lat-* / --lon-*`.
- It uses the MET Norway Sunrise API for matching.
- It computes the sunrise/sunset azimuth for the selected match and points Street View there.
- Reverse geocoding is optional in practice. Use `--address-lang-a none --address-lang-b none` if you do not want label lookup.

## End-to-End Pipeline

`main.py` is the main structured entry point.

```bash
python HW3/main.py \
  --name-a PohangSunrise \
  --maps-url-a "YOUR_GOOGLE_MAPS_URL_A" \
  --event-a sunrise --tz-a Asia/Seoul \
  --name-b MontrealSunset \
  --maps-url-b "YOUR_GOOGLE_MAPS_URL_B" \
  --event-b sunset --tz-b America/Toronto \
  --normalize-addresses
```

What it does:

- parse inputs
- find shared sunrise/sunset instants
- download Street View
- optionally reverse-geocode and normalize labels
- run OpenAI rendering
- compose the final side-by-side image

Output folder layout:

```text
HW3/runs/<run_id>/
  00_inputs/
  01_parsed/
  02_match/
  03_streetview/
  04_geocode/
  05_render/
  06_compose/
  manifest.json
```

Useful flags:

- `--start`, `--end`
- `--allow-future-matches`
- `--skip-transform`
- `--skip-compose`
- `--normalize-addresses`
- `--dry-run-openai`
- `--transform-pipeline {v1,v7}`

Important:

- `main.py` currently supports `v1` and `v7`.
- The default transform pipeline in `main.py` is `v7`.
- `v9` is currently standalone and not connected to `main.py`.

## OpenAI Transform: v1

`openai_transform_sketch.py` runs a two-step transform per image:

1. black-and-white sketch base
2. red sun / light overlay

Example:

```bash
python HW3/openai_transform_sketch.py \
  --input \
    HW3/streetview_outputs/pohang_montreal/PohangSunrise_streetview.jpg \
    HW3/streetview_outputs/pohang_montreal/MontrealSunset_streetview.jpg \
  --sun-events sunrise sunset \
  --outdir HW3/streetview_outputs/pohang_montreal/openai_sketches_v1
```

## OpenAI Transform: v7

`openai_transform_sketch_v7.py` is the multi-reference path used by default in `main.py`.

```bash
python HW3/openai_transform_sketch_v7.py \
  --style-reference-step1 HW3/style_reference_oratory.png \
  --style-reference-step2 HW3/style_reference_pohang.png \
  --input-first HW3/streetview_outputs/pohang_montreal/PohangSunrise_streetview.jpg \
  --event-first sunrise \
  --input-second HW3/streetview_outputs/pohang_montreal/MontrealSunset_streetview.jpg \
  --event-second sunset \
  --outdir HW3/streetview_outputs/pohang_montreal/openai_sketches_v7
```

v7 characteristics:

- uses multiple reference inputs
- keeps the first input as the actual edit target
- tries to preserve the original composition more strictly
- runs as a four-stage pipeline across the two locations

The standalone v7 script only handles rendering. Final juxtaposition is still done separately by `main.py` or `juxtapose_images.py`.

## OpenAI Transform: v9

`openai_transform_sketch_v9.py` is an experimental standalone variant with a different atmosphere-focused prompt design.

```bash
python HW3/openai_transform_sketch_v9.py \
  --input HW3/streetview_outputs/example.jpg \
  --sun-events sunrise \
  --outdir HW3/streetview_outputs/openai_sketches_v9
```

This variant is available as a separate script, but it is not yet selectable through `main.py`.

## Notes And Limitations

- Street View availability depends on Google coverage at the chosen coordinates.
- Matching is only as good as the upstream sunrise/sunset data and the chosen tolerance.
- The project currently uses the MET Norway Sunrise API for the main matching path, not a generic weather API.
- Open-Meteo support exists as a utility, but it is not the default source for the main pipeline.
- `runs/` and `streetview_outputs/` are output folders, not the core source of truth for the pipeline.
