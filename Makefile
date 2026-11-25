# Heritage Short -- one command per stage, `make film` for everything.
PY := uv run python -m

.PHONY: help install smoke validate draft narration radio keyframes refs shots music \
        assemble film kaggle-wan kaggle-wan-wait kaggle-music kaggle-music-wait costs \
        test lint clean-assembly

help:            ## list targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-18s %s\n", $$1, $$2}'

install:         ## install Python deps (needs uv) -- FFmpeg must be on PATH
	uv sync
	@command -v ffmpeg >/dev/null || echo "!! install FFmpeg: brew install ffmpeg / apt install ffmpeg"

smoke:           ## call every provider once and log latency
	$(PY) pipeline.smoke

validate:        ## validate storyboard.json against schema + consent gate
	$(PY) pipeline.storyboard

draft:           ## draft storyboard.draft.json from story/brief.md with Gemini
	$(PY) pipeline.script story/brief.md

narration:       ## Gemini TTS, one WAV per shot (cached)
	$(PY) pipeline.narration

radio:           ## radio cut: narration + placeholder music on black, with subtitles
	$(PY) pipeline.run --radio

refs:            ## style reference + character sheets only
	$(PY) pipeline.keyframes --refs-only

keyframes:       ## reference sheet, then one keyframe per shot (cached)
	$(PY) pipeline.keyframes

shots:           ## list Wan clips ready/pending, write outputs/wan/jobs.json
	$(PY) pipeline.shots

music:           ## list score candidates ready/pending, write outputs/music/jobs.json
	$(PY) pipeline.music

assemble:        ## cut, duck, subtitle, loudness, end card -> both aspect ratios
	$(PY) pipeline.assemble

film:            ## THE ONE COMMAND: validate -> narration -> keyframes -> shots -> music -> assemble
	$(PY) pipeline.run

kaggle-wan:      ## push pending Wan 2.2 clips to a Kaggle T4 kernel
	$(PY) pipeline.kaggle_jobs push wan

kaggle-wan-wait: ## wait for the Wan kernel and pull clips into outputs/wan
	$(PY) pipeline.kaggle_jobs wait wan

kaggle-music:    ## push pending ACE-Step candidates to a Kaggle kernel
	$(PY) pipeline.kaggle_jobs push music

kaggle-music-wait: ## wait for the music kernel and pull candidates into outputs/music
	$(PY) pipeline.kaggle_jobs wait music

costs:           ## summarise runs.jsonl into COSTS.md
	$(PY) pipeline.costs

test:            ## unit tests with coverage
	uv run pytest --cov=pipeline --cov-report=term-missing -q

lint:
	uv run ruff check pipeline tests kaggle

clean-assembly:  ## delete rendered segments/mixes (generated media is kept)
	rm -rf outputs/assembly
