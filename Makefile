# Build configuration
# -------------------

APP_NAME := `sed -n 's/^ *name.*=.*"\([^"]*\)".*/\1/p' pyproject.toml`
APP_VERSION := `sed -n 's/^ *version.*=.*"\([^"]*\)".*/\1/p' pyproject.toml`
GIT_REVISION = `git rev-parse HEAD`

# Introspection targets
# ---------------------

.PHONY: help
help: header targets

.PHONY: header
header:
	@echo "\033[34mEnvironment\033[0m"
	@echo "\033[34m---------------------------------------------------------------\033[0m"
	@printf "\033[33m%-23s\033[0m" "APP_NAME"
	@printf "\033[35m%s\033[0m" $(APP_NAME)
	@echo ""
	@printf "\033[33m%-23s\033[0m" "APP_VERSION"
	@printf "\033[35m%s\033[0m" $(APP_VERSION)
	@echo ""
	@printf "\033[33m%-23s\033[0m" "GIT_REVISION"
	@printf "\033[35m%s\033[0m" $(GIT_REVISION)
	@echo "\n"

.PHONY: targets
targets:
	@echo "\033[34mDevelopment Targets\033[0m"
	@echo "\033[34m---------------------------------------------------------------\033[0m"
	@perl -nle'print $& if m{^[a-zA-Z_-]+:.*?## .*$$}' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-22s\033[0m %s\n", $$1, $$2}'

# Development targets
# -------------
#
# 所有目标都走 `uv run`：它会按 uv.lock 解析出正确的环境再执行，
# 不依赖调用者有没有先 `source .venv/bin/activate`。
# 少了这一层，make test 会捡到 PATH 里的另一个 pytest（比如 homebrew 装的那个），
# 报一个与本项目无关的 ModuleNotFoundError。

.PHONY: install
install: ## Install dependencies
	uv sync


.PHONY: run
run: start

.PHONY: start
start: ## Starts the server
	uv run python run.py

# Check, lint and format targets
# ------------------------------

.PHONY: check
check: check-format lint

.PHONY: check-format
check-format: ## Dry-run code formatter
	uv run black ./ --check
	uv run isort ./ --profile black --check

.PHONY: lint
lint: ## Run ruff
	uv run ruff check ./app 
 
.PHONY: format
format: ## Run code formatter
	uv run black ./
	uv run isort ./ --profile black


.PHONY: test
test: ## Run the test suite
	$(eval include .env)
	$(eval export $(sh sed 's/=.*//' .env))
	uv run pytest -vv -s --cache-clear ./

.PHONY: clean-db
clean-db: ## 删除本地 sqlite 数据库文件（不动 migrations/）
	# 这里曾有一行 `find . -type d -name "migrations" -exec rm -rf {} +`。
	# 迁移文件现已纳入版本控制、且是 schema 的唯一来源，那行的效果变成了
	# 「递归删除版本控制里的文件」（连 .worktrees/*/migrations 一起），已移除。
	# 确实要重建基线时，请显式地手工删除并走评审，不要藏在一个 make 目标背后。
	rm -f db.sqlite3 db.sqlite3-shm db.sqlite3-wal

.PHONY: migrate
migrate: ## 运行aerich migrate命令生成迁移文件
	uv run aerich migrate

.PHONY: upgrade
upgrade: ## 运行aerich upgrade命令应用迁移
	uv run aerich upgrade