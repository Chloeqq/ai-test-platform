from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
ASSETS_ROOT = PROJECT_ROOT / "assets"
TEST_CASES_ROOT = ASSETS_ROOT / "test-cases"
SMOKE_TEST_CASES_ROOT = TEST_CASES_ROOT / "smoke"
AI_GENERATED_CASES_ROOT = PROJECT_ROOT / "assets/test-cases/ai-generated"
PAGE_OBJECTS_ROOT = ASSETS_ROOT / "page-objects" / "web"
ASSET_TEMPLATES_ROOT = PROJECT_ROOT / "runners" / "web-playwright-python" / "templates"
