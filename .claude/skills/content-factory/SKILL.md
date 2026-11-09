---
name: content-factory
description: Turn one topic into a batch of short form vertical videos (TikTok, Reels, Shorts) with captions and hashtags, generated with the Higgsfield tools.
---

# Content Factory

Batch version of short-studio. Keep replies brief.

1. Ask only what is missing: topic, platform, number of videos (default 5), tone, length (default 15 to 30s).
2. Propose N distinct angles on the topic (for example tip, myth, story, list, question). Each gets a hook, 3 to 5 beats, a call to action, a caption, and hashtags.
3. Show the angles table and the total credit estimate. Wait for approval, and let the user drop or edit angles.
4. Generate in 9:16 with the Higgsfield batch tools: generate_image_batch, generate_video_batch, generate_audio_batch. Call get_workflow_instructions first for multi step videos. Use jobs_wait to poll, then show all results together with show_generation_by_ids.
5. Return a summary: each video with its caption, hashtags, and a suggested posting order.
6. Never post anything online without explicit user confirmation.
