from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
from pathlib import Path
from typing import Any


ALLOWED_TOP_LEVEL = {
    "schemaVersion",
    "target",
    "global",
    "markets",
    "sectors",
    "stages",
    "stocks",
}
FORBIDDEN_DATA_KEYS = {
    "return",
    "returns",
    "rank",
    "ranking",
    "weight",
    "weights",
    "breadth",
    "performance",
    "benchmark",
    "members",
    "membercount",
    "tables",
    "rows",
}


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def commentary_slot(kind: str, *parts: Any) -> str:
    raw = "\x1f".join([kind, *(str(part) for part in parts)])
    slot_id = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]
    return (
        f'<div class="commentary-slot" data-commentary-slot="{esc(kind)}" '
        f'data-commentary-id="{slot_id}"></div>'
    )


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_main_contract(source: str) -> dict[str, str]:
    match = re.search(
        r'<main\s+data-report="([^"]+)"\s+data-as-of="([^"]+)"\s+data-primary="([^"]+)">',
        source,
    )
    if not match:
        raise ValueError("표 HTML에 코멘트 결합용 report/as-of/primary 계약이 없습니다. 표를 먼저 다시 생성하세요.")
    return {"report": html.unescape(match.group(1)), "asOf": html.unescape(match.group(2)), "primary": html.unescape(match.group(3))}


def reject_embedded_table_data(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).casefold() in FORBIDDEN_DATA_KEYS:
                raise ValueError(f"코멘트 JSON에는 표 숫자/순위를 넣을 수 없습니다: {path}.{key}")
            reject_embedded_table_data(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            reject_embedded_table_data(child, f"{path}[{index}]")


def normalize_items(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def render_item(item: Any) -> str:
    if isinstance(item, str):
        title = ""
        body = item
        meta_parts: list[str] = []
        url = ""
    elif isinstance(item, dict):
        unknown = set(item) - {"title", "body", "date", "source", "url", "confidence"}
        if unknown:
            raise ValueError(f"지원하지 않는 코멘트 필드입니다: {sorted(unknown)}")
        title = str(item.get("title") or "").strip()
        body = str(item.get("body") or "").strip()
        meta_parts = [str(item[key]).strip() for key in ("date", "source", "confidence") if item.get(key)]
        url = str(item.get("url") or "").strip()
    else:
        raise TypeError("코멘트는 문자열 또는 객체여야 합니다.")
    if not body:
        raise ValueError("빈 코멘트 본문은 허용하지 않습니다.")
    if url and not re.match(r"^https?://", url, flags=re.IGNORECASE):
        raise ValueError(f"출처 URL은 http(s)만 허용합니다: {url}")
    title_html = f"<strong>{esc(title)}</strong>" if title else ""
    body_html = esc(body).replace("\n", "<br>")
    meta_html_parts = [esc(part) for part in meta_parts]
    if url:
        label = esc(str(item.get("source") or "출처")) if isinstance(item, dict) else "출처"
        meta_html_parts.append(f'<a href="{esc(url)}" target="_blank" rel="noopener noreferrer">{label}</a>')
    meta_html = f'<div class="commentary-meta">{" · ".join(meta_html_parts)}</div>' if meta_html_parts else ""
    return f'<div class="commentary-block">{title_html}<div>{body_html}</div>{meta_html}</div>'


def render_items(value: Any) -> str:
    return "".join(render_item(item) for item in normalize_items(value))


def attach_at(source: str, kind: str, parts: tuple[Any, ...], value: Any) -> tuple[str, int]:
    items = normalize_items(value)
    if not items:
        return source, 0
    token = commentary_slot(kind, *parts)
    occurrences = source.count(token)
    if occurrences == 0:
        label = "/".join(str(part) for part in parts)
        raise KeyError(f"표 HTML에서 코멘트 대상 슬롯을 찾지 못했습니다: {kind}:{label}")
    return source.replace(token, render_items(items)), occurrences


def attach_sector(source: str, payload: dict[str, Any]) -> tuple[str, int]:
    attached = 0
    source, count = attach_at(source, "global", (), payload.get("global"))
    attached += count
    for market, items in payload.get("markets", {}).items():
        source, count = attach_at(source, "market", (market,), items)
        attached += count
    for market, groups in payload.get("sectors", {}).items():
        for sector, items in groups.items():
            source, count = attach_at(source, "sector", (market, sector), items)
            attached += count
    for market, stocks in payload.get("stocks", {}).items():
        for ticker, items in stocks.items():
            source, count = attach_at(source, "stock", (market, ticker), items)
            attached += count
    if payload.get("stages"):
        raise ValueError("sector 보고서에는 stages 코멘트를 사용할 수 없습니다.")
    return source, attached


def attach_ai(source: str, payload: dict[str, Any]) -> tuple[str, int]:
    attached = 0
    source, count = attach_at(source, "global", (), payload.get("global"))
    attached += count
    for stage, items in payload.get("stages", {}).items():
        source, count = attach_at(source, "stage", (stage,), items)
        attached += count
    for ticker, items in payload.get("stocks", {}).items():
        source, count = attach_at(source, "stock", (ticker,), items)
        attached += count
    if payload.get("markets") or payload.get("sectors"):
        raise ValueError("ai 보고서에는 markets/sectors 코멘트를 사용할 수 없습니다.")
    return source, attached


def main() -> None:
    parser = argparse.ArgumentParser(
        description="기존 정량 HTML은 건드리지 않고 지정된 슬롯에 서술 코멘트만 결합합니다."
    )
    parser.add_argument("--base-html", type=Path, required=True)
    parser.add_argument("--commentary-json", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    source = args.base_html.read_text(encoding="utf-8")
    payload = json.loads(args.commentary_json.read_text(encoding="utf-8"))
    unknown = set(payload) - ALLOWED_TOP_LEVEL
    if unknown:
        raise ValueError(f"지원하지 않는 최상위 필드입니다: {sorted(unknown)}")
    if payload.get("schemaVersion") != 1:
        raise ValueError("commentary schemaVersion은 1이어야 합니다.")
    reject_embedded_table_data({key: value for key, value in payload.items() if key != "target"})

    contract = find_main_contract(source)
    target = payload.get("target") or {}
    for key in ("report", "asOf", "primary"):
        if str(target.get(key) or "") != contract[key]:
            raise ValueError(f"코멘트 대상 불일치: {key}={target.get(key)!r}, 표={contract[key]!r}")
    expected_hash = str(target.get("baseSha256") or "").strip().lower()
    actual_hash = file_sha256(args.base_html)
    if expected_hash and expected_hash != actual_hash:
        raise ValueError("코멘트가 참조한 표 HTML과 실제 입력 표가 다릅니다(baseSha256 불일치).")

    if contract["report"] == "sector":
        output, attached = attach_sector(source, payload)
    elif contract["report"] == "ai":
        output, attached = attach_ai(source, payload)
    else:
        raise ValueError(f"지원하지 않는 report 유형입니다: {contract['report']}")
    if attached == 0:
        raise ValueError("결합할 코멘트가 없습니다.")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    temp = args.output.with_name(args.output.name + ".tmp")
    temp.write_text(output, encoding="utf-8")
    os.replace(temp, args.output)
    print(json.dumps({
        "output": str(args.output.resolve()),
        "report": contract["report"],
        "asOf": contract["asOf"],
        "primary": contract["primary"],
        "attachedSlots": attached,
        "baseSha256": actual_hash,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
