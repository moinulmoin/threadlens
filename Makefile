SMOKE_DIR ?= /private/tmp/threadlens-smoke

.PHONY: verify python raycast smoke doctor clean

verify: python raycast smoke doctor

python:
	python3 -B -m py_compile threadlens/*.py
	python3 -B -m unittest discover -s tests

raycast:
	npm --prefix raycast exec -- tsc --project raycast/tsconfig.json --noEmit
	NPM_CONFIG_CACHE=/private/tmp/threadlens-npm-cache npm --prefix raycast run lint
	NPM_CONFIG_CACHE=/private/tmp/threadlens-npm-cache npm --prefix raycast audit --json

smoke:
	mkdir -p $(SMOKE_DIR)
	python3 -B -m threadlens \
		--db $(SMOKE_DIR)/index.sqlite \
		--config $(SMOKE_DIR)/sources.json \
		sources add demoagent \
		--path eval/custom-source.example.jsonl \
		--session-key session.id \
		--message-key message.id \
		--role-key message.role \
		--text-key message.content \
		--timestamp-key createdAt \
		--cwd-key cwd \
		--title-key title \
		--resume-template "cd {cwd} && demoagent resume {session_id}"
	python3 -B -m threadlens \
		--db $(SMOKE_DIR)/index.sqlite \
		--config $(SMOKE_DIR)/sources.json \
		refresh --source demoagent --force
	python3 -B -m threadlens \
		--db $(SMOKE_DIR)/index.sqlite \
		--config $(SMOKE_DIR)/sources.json \
		eval eval/custom-source.eval.json

doctor:
	python3 -B -m threadlens doctor --json

clean:
	rm -rf build threadlens.egg-info
	find threadlens tests -type d -name __pycache__ -prune -exec rm -rf {} +
	find threadlens tests -type f -name '*.pyc' -delete
