"""Seed page objects from YAML asset files into the database.

Usage:
    python scripts/tools/seed_page_objects.py
    python scripts/tools/seed_page_objects.py --project myproject --client web
    python scripts/tools/seed_page_objects.py --dry-run
    python scripts/tools/seed_page_objects.py --force
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_UI_ROOT = REPO_ROOT / "apps" / "web-ui-service"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(WEB_UI_ROOT) not in sys.path:
    sys.path.insert(0, str(WEB_UI_ROOT))

YAML_ROOT = REPO_ROOT / "assets" / "page-objects" / "web"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed YAML page objects into the database")
    parser.add_argument("--project", default="atp", help="Project code (default: atp)")
    parser.add_argument("--client", default="web", help="Client type (default: web)")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without writing to DB")
    parser.add_argument("--force", action="store_true", help="Update existing page objects instead of skipping")
    return parser.parse_args()


def _load_yaml_file(path: Path) -> dict:
    import yaml

    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"Expected dict in {path}, got {type(data).__name__}")
    return data


def _seed_one(
    db: "Session",
    *,
    page_code: str,
    yaml_data: dict,
    project_code: str,
    client: str,
    force: bool,
    dry_run: bool,
) -> str:
    from sqlalchemy import select

    from app.models.page_object import PageElement, PageObject

    page_name = yaml_data.get("page", page_code)
    elements = yaml_data.get("elements", {})
    if not isinstance(elements, dict):
        return f"  SKIP {page_code}: no valid elements mapping"

    existing = db.execute(
        select(PageObject).where(
            PageObject.project_code == project_code,
            PageObject.client == client,
            PageObject.page_code == page_code,
        )
    ).scalar_one_or_none()

    if existing and not force:
        return f"  SKIP {page_code}: already exists (id={existing.id}, {existing.element_count} elements). Use --force to update."

    if dry_run:
        action = "UPDATE" if existing else "CREATE"
        return f"  DRY-RUN {action} {page_code}: {len(elements)} elements"

    if existing:
        page_obj = existing
        page_obj.page_name = str(page_name)
        page_obj.description = str(yaml_data.get("description", "")).strip()
        page_obj.status = "published"
        action = "UPDATED"
    else:
        page_obj = PageObject(
            project_code=project_code,
            client=client,
            page_code=page_code,
            page_name=str(page_name),
            element_count=len(elements),
            status="published",
            created_by="seed_page_objects",
        )
        db.add(page_obj)
        db.flush()
        action = "CREATED"

    existing_elements = {
        str(item.element_code).strip(): item
        for item in db.execute(
            select(PageElement).where(PageElement.page_object_id == page_obj.id)
        ).scalars().all()
        if str(item.element_code).strip()
    }
    for element_code, element_meta in elements.items():
        if not isinstance(element_meta, dict):
            continue
        locator_type = str(element_meta.get("locator_type", "css")).strip()
        locator_value = str(element_meta.get("locator_value", "")).strip()
        role = str(element_meta.get("role", "")).strip()
        element_name = str(element_meta.get("element_name") or element_meta.get("name") or element_code).strip()
        elem = existing_elements.get(str(element_code).strip())
        if elem is None:
            db.add(
                PageElement(
                    page_object_id=page_obj.id,
                    element_code=str(element_code).strip(),
                    element_name=element_name,
                    locator_type=locator_type,
                    locator_value=locator_value,
                    role=role,
                    status="active",
                )
            )
            continue
        elem.element_name = element_name
        elem.locator_type = locator_type
        elem.locator_value = locator_value
        elem.role = role
        elem.status = "active"

    page_obj.element_count = int(
        db.query(PageElement).filter(PageElement.page_object_id == page_obj.id).count() or 0
    )
    db.flush()
    return f"  {action} {page_code}: {page_obj.element_count} elements (id={page_obj.id})"


def main() -> None:
    args = _parse_args()

    yaml_files = sorted(YAML_ROOT.glob("*.page-object.yaml"))
    if not yaml_files:
        print(f"No YAML page object files found in {YAML_ROOT}")
        sys.exit(1)

    print(f"Seeding {len(yaml_files)} page objects from {YAML_ROOT}")
    print(f"  project={args.project}  client={args.client}  force={args.force}  dry_run={args.dry_run}")
    print()

    if args.dry_run:
        for yaml_file in yaml_files:
            page_code = yaml_file.stem.replace(".page-object", "")
            yaml_data = _load_yaml_file(yaml_file)
            elements = yaml_data.get("elements", {})
            print(f"  DRY-RUN CREATE {page_code}: {len(elements) if isinstance(elements, dict) else 0} elements")
        print("\nDry run complete. No database changes made.")
        return

    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        for yaml_file in yaml_files:
            page_code = yaml_file.stem.replace(".page-object", "")
            yaml_data = _load_yaml_file(yaml_file)
            result = _seed_one(
                db,
                page_code=page_code,
                yaml_data=yaml_data,
                project_code=args.project,
                client=args.client,
                force=args.force,
                dry_run=False,
            )
            print(result)
        db.commit()
        print("\nSeed complete.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
