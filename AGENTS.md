# AGENTS.md

This is **RssHub lite** (`astrbot_plugin_rsshub_lite`), based directly on the original AstrBot RSSHub plugin. It retains subscription management, polling, reliable pushes, media, history, and Plugin Pages. Content processors, LLM tools, and knowledge-base integrations have been removed; legacy database columns are compatibility data only and must not execute AI. Preserve the upstream authorship and source references in `NOTICE.md` and `UPSTREAM.json`.

## Build, Test, and Lint

Useful checks from the AstrBot project root:

```bash
uv run ruff format data/plugins/astrbot_plugin_rsshub_lite
uv run ruff check data/plugins/astrbot_plugin_rsshub_lite
uv run python -m pytest data/plugins/astrbot_plugin_rsshub_lite/tests/ -v
```

Fast checks from the plugin directory:

```bash
python tests/run_tests.py --category unit
python tests/run_tests.py --category integration
./tests/run_tests.sh --category unit
./tests/run_tests.sh --category integration
```

See `docs/dev/testing.md` for the regression matrix and when to run narrower suites.

## Project Layout

- `_conf_schema.json` - AstrBot plugin configuration schema shown in the host UI
- `metadata.yaml` - AstrBot plugin metadata
- `main.py` / `bootstrap.py` - AstrBot lifecycle entry and runtime composition
- `src/` - Python domain, application, infrastructure, and interface code
- `pages/` - Plugin Pages frontend
- `docs/` - project, usage, and maintenance documentation
- `tests/` - unit, integration, frontend, fixtures, and mocks
- `scripts/` - maintenance and diagnostic helpers

Read `docs/project/architecture.md` for detailed layer responsibilities and data flow.

## Where to Look

- Maintenance rules: `docs/dev/maintenance.md`
- Configuration and domain semantics: `docs/project/domain-model.md`
- Commands, user settings, push history: `docs/project/application.md`
- Platforms, media, cache, proxies: `docs/project/platforms.md`
- Web API and Plugin Pages: `docs/project/web_api.md`
