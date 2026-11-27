Place exactly one matching chapter pair in this folder:

    input/chapter.cbz
    input/chapter.txt

Rules
-----
* Only one archive (.cbz or .zip) and one narration file (.txt) per run.
* Extensions are matched case-insensitively, so Chapter.CBZ also works.
* This README is documentation and is ignored by the pipeline.
* The base filenames do not need to match.
* Keep the TXT in the panel format shown in
  examples/narration-template.txt, or documentation in docs/.

Before pushing, check the pair locally if you can:

    python scripts/run_pipeline.py --validate

Copyright and privacy
---------------------
Only commit material you have permission to store and distribute. Large or
sensitive chapters can be kept out of Git entirely; see "Keeping chapters out
of Git" in the top-level README.
