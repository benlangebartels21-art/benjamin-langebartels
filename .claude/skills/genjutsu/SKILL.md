---
name: genjutsu
description: Browse and run Higgsfield Genjutsu motion presets, which copy motion from a driving video onto the user's character image or replace a subject in a video.
---

# Genjutsu

Keep replies brief.

1. With no arguments, call get_presets with source "genjutsu" and category "genjutsu-trending" (also "genjutsu" or "genjutsu-new"; "genjutsu-styles" for looks that redraw the user's video). List preset names only.
2. When the user picks a preset or describes a custom request, call get_preset_instructions with preset "genjutsu" first.
3. Motion transfer (copy actions or camera movement) uses hf_mult_motion_control. Object or subject replacement uses hf_mult_replace_object. Both run through generate_video.
4. Need the user's reference image. Upload it with media_upload, a curl PUT, then media_confirm. Use only confirmed media IDs.
5. Show the price and wait for explicit approval before generating. Browsing never authorizes generation.
6. Poll with jobs_wait, then show the result. Never post anything online without explicit confirmation.
