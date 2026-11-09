---
name: katana
description: Discover and run Higgsfield Katana presets (Higgsfield and Community catalogs) for short form video.
---

# Katana

Keep replies brief.

1. With no arguments, call get_preset_instructions with the preset omitted for Katana discovery. Katana is a catalog, so query and initial_inputs are not supported on get_presets with source "katana". Use katana_source "higgsfield" or "community" to filter.
2. When the user picks a preset, call get_preset_instructions with that preset and follow its recipe. Call get_katana_config if it asks for it.
3. Upload any reference media with media_upload, a curl PUT, then media_confirm. Use only confirmed media IDs.
4. Show the price and wait for explicit approval before generating. Browsing never authorizes generation.
5. After a Katana video completes, verify it, then call show_result with action "katana_video" and the media_id or url.
6. Never post anything online without explicit confirmation.
