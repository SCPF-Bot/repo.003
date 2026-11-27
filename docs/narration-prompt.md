# Prompt for generating a narration TXT

Copy everything between the markers into a chat model together with your CBZ
chapter, then save the returned file as `input/<chapter>.txt`.

The prompt is written to produce output that `src/narration_parser.py` accepts:
sequential page/panel numbering, one `CROP` per panel with normalized
coordinates, and no Markdown scaffolding.

---

```
I have uploaded a manhwa chapter in CBZ format. I want you to prepare a complete narration TXT file that I can use with my Manhwa Narrator video-generation repository.

Follow these instructions carefully:

1. Analyze every page and panel

- Read every page in the CBZ archive.
- Identify every individual panel.
- Do not skip, summarize away, or combine panels.
- Follow the correct manhwa reading order.
- Preserve the original sequence of events.
- Include dialogue, character reactions, important expressions, actions, scene changes, and sound effects when relevant.
- If text or artwork is unclear, do not invent details. Mark uncertain content for review.

2. Write the narration

- Language: English.
- Style: Cinematic, immersive, dramatic, and natural.
- Make the narration sound like a professional manhwa storyteller.
- Convert visual events into engaging spoken narration.
- Keep narration concise enough for video pacing while covering every panel.
- Do not add events, dialogue, or details that are not supported by the artwork.
- Make narration flow naturally from one panel to the next.

3. Identify panel coordinates

For every panel, provide its crop coordinates relative to the original page.

Use this exact format:

CROP: x,y,width,height

Coordinate rules:

- Use normalized values from 0.0 to 1.0.
- Origin (0,0) is the top-left corner.
- x and y identify the panel's top-left position.
- width and height identify its size.
- Keep the crop inside the page boundaries.
- Include all visible content belonging to that panel.
- Do not use the entire page as a panel crop unless it genuinely contains one panel.

4. Follow this exact TXT structure

[PAGE 001]
[PANEL 001]
CROP: 0.00,0.00,0.50,0.33
NARRATION: Your cinematic narration goes here.

[PANEL 002]
CROP: 0.50,0.00,0.50,0.33
NARRATION: Your cinematic narration goes here.

Continue until every panel on every page has been covered.

5. Important compatibility requirements

- Use sequential page numbers and panel numbers.
- Every panel must have exactly one CROP entry.
- Every panel must have narration.
- Do not omit panels, even if they contain little or no dialogue.
- Preserve the correct reading order.
- Make sure the TXT is valid for my repository's "src/narration_parser.py".
- Do not include Markdown headings, explanations, or commentary inside the final TXT file.

6. Final deliverables

1. Generate a downloadable ".txt" file containing the complete narration and crop coordinates.
2. Name it using the chapter filename, for example "chapter-001.txt".
3. Verify that every CBZ page and panel has been accounted for.
4. Report the total number of pages and panels processed.
5. Clearly identify any panels whose text or crop boundaries need manual review.

IMPORTANT: I need the actual downloadable TXT file, not just narration displayed in the chat. The TXT will be placed alongside the original CBZ file in my GitHub repository's "/input" folder. GitHub Actions will then generate the narrated portrait 9:16 cinematic MP4 using Kokoro TTS and FFmpeg.
```

---

## After the model answers

1. Save the TXT next to the CBZ in `input/`.
2. Run `python scripts/run_pipeline.py --validate` for a fast format check
   before spending a full render.
3. If validation complains about a page or panel, ask the model to re-emit the
   whole file rather than patching lines by hand — numbering gaps are the most
   common failure.
