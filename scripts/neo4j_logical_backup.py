from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from neo4j import GraphDatabase

URI = "neo4j://127.0.0.1:7687"
AUTH = ("neo4j", "xjj-dev-neo4j")


def encode(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: encode(item) for key, item in value.items()}
    if isinstance(value, list):
        return [encode(item) for item in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def driver():
    return GraphDatabase.driver(URI, auth=AUTH)


def backup(path: Path) -> dict[str, int]:
    with driver() as db, db.session() as session:
        episode_rows = session.run(
            "MATCH (e:Episodic) "
            "RETURN e.uuid AS uuid, e.name AS name, e.group_id AS group_id, "
            "e.source AS source, e.source_description AS source_description, "
            "e.content AS content, e.valid_at AS valid_at, e.created_at AS created_at"
        ).data()
        edge_rows = session.run(
            "MATCH (a)-[r:RELATES_TO]->(b) "
            "RETURN r.uuid AS uuid, a.uuid AS source, b.uuid AS target, "
            "r.fact AS fact, r.name AS name, r.group_id AS group_id"
        ).data()
    payload = encode(
        {
            "created_at": datetime.now().astimezone().isoformat(),
            "episodes": episode_rows,
            "edges": edge_rows,
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"episodes": len(episode_rows), "edges": len(edge_rows)}


def restore(path: Path, group: str) -> dict[str, int]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    with driver() as db, db.session() as session:
        for row in payload.get("episodes", []):
            session.run(
                "CREATE (e:EpisodicRestore {restore_group: $restore_group, uuid: $uuid, "
                "name: $name, group_id: $group_id, source: $source, "
                "source_description: $source_description, content: $content, "
                "valid_at: $valid_at, created_at: $created_at})",
                restore_group=group,
                uuid=row.get("uuid"),
                name=row.get("name"),
                group_id=row.get("group_id"),
                source=row.get("source"),
                source_description=row.get("source_description"),
                content=row.get("content"),
                valid_at=row.get("valid_at"),
                created_at=row.get("created_at"),
            )
        count = session.run(
            "MATCH (e:EpisodicRestore {restore_group: $restore_group}) RETURN count(e) AS n",
            restore_group=group,
        ).single()["n"]
        session.run(
            "MATCH (e:EpisodicRestore {restore_group: $restore_group}) DETACH DELETE e",
            restore_group=group,
        )
    return {"restored_episodes": int(count), "source_episodes": len(payload.get("episodes", []))}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--restore", type=Path)
    parser.add_argument("--group", default="restore_drill")
    args = parser.parse_args()
    if bool(args.backup) == bool(args.restore):
        raise SystemExit("choose exactly one of --backup or --restore")
    if args.backup:
        print(json.dumps(backup(args.backup), ensure_ascii=False))
    else:
        print(json.dumps(restore(args.restore, args.group), ensure_ascii=False))


if __name__ == "__main__":
    main()