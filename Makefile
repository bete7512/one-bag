# One command per job. `make setup` builds a private Python environment in .venv and every target uses it.
# To type `python -m pipeline ...` yourself, first run: source .venv/bin/activate
# On Windows without make: python -m venv .venv, .venv\Scripts\activate, pip install -r requirements.txt,
# then the python command shown on each line.
VENV ?= .venv
SYSPY ?= python3
ifeq ($(OS),Windows_NT)
VPY := $(VENV)/Scripts/python.exe
else
VPY := $(VENV)/bin/python
endif
# the Python of .venv once it exists, the system one before that
PY ?= $(if $(wildcard $(VPY)),$(VPY),$(SYSPY))

.PHONY: doctor review site setup validate plan radio film release qc costs smoke test test-fast mock-film clean-mock

setup:            ## build .venv and install the Python dependencies into it
	@$(SYSPY) -m venv $(VENV) || (echo "Could not create $(VENV). On Ubuntu or Debian: sudo apt install python3-venv" && exit 1)
	$(VPY) -m pip install --quiet --upgrade pip
	$(VPY) -m pip install -r requirements.txt
	@echo "Done. To type python -m pipeline yourself, first run: source $(VENV)/bin/activate"

doctor:           ## check tools, FFmpeg features, packages and keys on this machine
	$(PY) -m pipeline doctor

review:           ## one HTML page to look at and listen to everything
	$(PY) -m pipeline review

site:             ## the film's public page, built from the repository into site/
	$(PY) -m pipeline site

validate:         ## check storyboard.json against the schema and the consent records
	$(PY) -m pipeline validate

plan:             ## what would be regenerated, and why (calls no model)
	$(PY) -m pipeline plan

smoke:            ## call each provider once and log the latency
	$(PY) -m pipeline smoke

radio:            ## radio cut: narration + placeholder music on a black screen
	$(PY) -m pipeline radio

film:             ## THE one command: storyboard.json in, both films out, then the final-cut check
	$(PY) -m pipeline film

release:          ## like film, but refuses drafts, pending consent and a failed final-cut check
	$(PY) -m pipeline film --strict

qc:               ## final-cut check only
	$(PY) -m pipeline qc

costs:            ## measured latency and cost per stage, written into COSTS.md
	$(PY) -m pipeline costs --write

test:             ## unit tests plus a full offline run with mock providers
	$(PY) -m unittest discover -s tests -v

test-fast:        ## unit tests only
	HERITAGE_FAST_TESTS=1 $(PY) -m unittest discover -s tests -v

mock-film:        ## the whole pipeline offline, into outputs_mock/ (no keys, no network)
	$(PY) -m pipeline film --mock

clean-mock:       ## delete the offline test outputs
	$(PY) -c "import shutil; shutil.rmtree('outputs_mock', ignore_errors=True)"