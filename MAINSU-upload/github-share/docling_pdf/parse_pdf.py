"""Local PDF -> Docling JSON + event-ready JSON. Python 3.11/3.12."""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import importlib.metadata
import json
import logging
from pathlib import Path
import re
from statistics import median
import sys
import unicodedata


def normalized(text):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text))


def overlap(a, b):
    """Intersection / smaller area: only spatially coincident duplicates."""
    area = lambda r: max(0, r[2] - r[0]) * max(0, r[3] - r[1])
    intersection = [max(a[0], b[0]), max(a[1], b[1]),
                    min(a[2], b[2]), min(a[3], b[3])]
    denominator = min(area(a), area(b))
    return area(intersection) / denominator if denominator else 0


def clean_pdf_glyphs(text):
    """Collapse duplicate compatibility glyph runs, not normal repeated words.

    E.g. PDF text '潛⽔水' and '年年' contain two Unicode glyph encodings
    for a single visible character. Keep ordinary '水水', '看看', '人人'.
    """
    def canonical(char):
        value = ord(char)
        special = (0x2E80 <= value <= 0x2FFF or 0xF900 <= value <= 0xFAFF
                   or 0x2F800 <= value <= 0x2FA1F)
        return (unicodedata.normalize("NFKC", char) if special else char), special
    result = []
    index = 0
    while index < len(text):
        char, special = canonical(text[index])
        end, has_special = index+1, special
        while end < len(text):
            following, following_special = canonical(text[end])
            if following != char:
                break
            has_special = has_special or following_special
            end += 1
        if has_special and len(char) == 1:
            # Preserve multiple visible copies: R N R N encodes two glyphs,
            # while R N C is one radical/base/compatibility glyph cluster.
            run = text[index:end]
            pos = 0
            while pos < len(run):
                _, is_special = canonical(run[pos])
                if is_special:
                    pos += 1
                    if pos < len(run) and not canonical(run[pos])[1]:
                        pos += 1
                else:
                    pos += 1
                if pos < len(run) and (0xF900 <= ord(run[pos]) <= 0xFAFF or
                                      0x2F800 <= ord(run[pos]) <= 0x2FA1F):
                    pos += 1
                result.append(char)
        else:
            result.append(text[index:end])
        index = end
    # Drop extraction control bytes, retaining line breaks and tabs.
    return "".join(c for c in "".join(result)
                   if unicodedata.category(c) != "Cc" or c in "\n\r\t")


def table_markdown(data, headers=None, combine_from=None):
    """Place cells by row/column indices, never by extraction-list order.

    Spanned cell text is written only at its anchor; spans remain in JSON.
    """
    rows, cols = int(data.get("num_rows", 0)), int(data.get("num_cols", 0))
    if rows <= 0 or cols <= 0:
        return ""
    grid = [["" for _ in range(cols)] for _ in range(rows)]
    for cell in data.get("table_cells", []):
        r, c = cell["start_row_offset_idx"], cell["start_col_offset_idx"]
        if 0 <= r < rows and 0 <= c < cols:
            grid[r][c] = clean_text(cell.get("text", ""))
    if combine_from is not None:
        grid = [row[:combine_from]+["；".join(s for s in row[combine_from:] if s)] for row in grid]
        cols = combine_from+1
    # A generated header keeps the first data row intact.
    if headers is None:
        header_cells = [c for c in data.get("table_cells", [])
                        if c.get("start_row_offset_idx") == 0]
        if header_cells and all(c.get("column_header") for c in header_cells):
            headers, grid = grid[0], grid[1:]
        else:
            headers = [f"欄 {i+1}" for i in range(cols)]
    if len(headers) != cols:
        raise ValueError("Table header count does not match displayed columns")
    def row_md(row):
        return "| " + " | ".join(s.replace("|", "\\|").replace("\r", "").replace("\n", "<br>") for s in row) + " |"
    return "\n".join([row_md(headers),row_md(["---"]*cols)]+[row_md(row) for row in grid])


def clean_table_data(data):
    result = deepcopy(data)
    for cell in result.get("table_cells", []):
        cell["text"] = clean_text(cell.get("text", ""))
    for row in result.get("grid", []):
        for cell in row:
            if isinstance(cell, dict):
                cell["text"] = clean_text(cell.get("text", ""))
    return result


def simplify(raw):
    pages = raw.get("pages", {})
    page_sizes = {int(k): v["size"] for k, v in pages.items()}
    records, duplicates = [], []
    dedup_candidates = {}
    seen_refs = set()
    candidates = []

    def resolve(ref):
        obj = raw
        for part in ref.removeprefix("#/").split("/"):
            obj = obj[int(part)] if isinstance(obj, list) else obj[part]
        return obj

    def walk(item):
        ref = item.get("self_ref")
        if ref in seen_refs:
            return
        if ref:
            seen_refs.add(ref)
        if item.get("text") or "table_cells" in item.get("data", {}):
            candidates.append(item)
        for child in item.get("children", []):
            walk(resolve(child["$ref"]))

    # Preserve Docling's document tree reading order, including picture children.
    walk(raw.get("body", {}))
    walk(raw.get("furniture", {}))
    for item in candidates:
        is_table = "table_cells" in item.get("data", {})
        text = item.get("text", "")
        if is_table:
            text = "\n".join(c.get("text", "") for c in
                             item.get("data", {}).get("table_cells", []))
        locations = []
        for prov in item.get("prov", []):
            page = int(prov["page_no"])
            box = prov["bbox"]
            origin = str(box.get("coord_origin", "BOTTOMLEFT")).upper()
            height = page_sizes[page]["height"]
            if "BOTTOMLEFT" in origin:
                coords = [box["l"], height - box["t"], box["r"], height - box["b"]]
            elif "TOPLEFT" in origin:
                coords = [box["l"], box["t"], box["r"], box["b"]]
            else:
                raise ValueError(f"Unknown coordinate origin: {origin}")
            locations.append({"page": page, "bbox": coords,
                              "charspan": prov.get("charspan")})
        record = {"id": f"block_{len(records)+1:06d}",
                  "docling_ref": item.get("self_ref"),
                  "type": "table" if is_table else item.get("label"), "text": text,
                  "source_label": item.get("label"),
                  "locations": locations,
                  "extraction_source": "native_or_ocr_unresolved"}
        if is_table:
            record["table"] = item.get("data", {})
        duplicate = None
        dedup_key = (record["type"],normalized(text))
        # Never remove matching strings at distinct locations or across pages.
        for prior in dedup_candidates.get(dedup_key,[]) if dedup_key[1] else []:
            if is_table and prior.get("table") != record.get("table"):
                continue
            if locations and len(locations) == len(prior["locations"]) and all(
                a["page"] == b["page"] and overlap(a["bbox"], b["bbox"]) >= .9
                for a, b in zip(locations, prior["locations"])
            ):
                duplicate = prior["id"]
                break
        if duplicate:
            duplicates.append({"removed_ref": record["docling_ref"],
                               "kept_id": duplicate, "reason": "same_text_and_location"})
        else:
            record["reading_order"] = len(records)
            records.append(record)
            dedup_candidates.setdefault(dedup_key,[]).append(record)
    picture_groups = []
    for picture in raw.get("pictures", []):
        child_refs = {c["$ref"] for c in picture.get("children", [])}
        children = [b for b in records if b["docling_ref"] in child_refs
                    and b["type"] != "table" and len(b["locations"]) == 1]
        children.sort(key=lambda b: (b["locations"][0]["page"],
                                    b["locations"][0]["bbox"][1]))
        groups = []
        for block in children:
            loc = block["locations"][0]
            box = loc["bbox"]
            match = None
            for group in reversed(groups):
                prev = group[-1]["locations"][0]
                a = prev["bbox"]
                width = min(a[2]-a[0], box[2]-box[0])
                x_overlap = max(0, min(a[2], box[2])-max(a[0], box[0]))
                gap = box[1]-a[3]
                height = min(a[3]-a[1], box[3]-box[1])
                if (loc["page"] == prev["page"] and width > 0 and height > 0
                        and x_overlap / width >= .8 and 0 <= gap <= height * .6):
                    match = group
                    break
            if match is None:
                groups.append([block])
            else:
                match.append(block)
        for group in groups:
            text = group[0]["text"].strip()
            for block in group[1:]:
                following = block["text"].strip()
                separator = "" if (text and following and
                    re.match(r"[\u3400-\u9fff]", text[-1]) and
                    re.match(r"[\u3400-\u9fff]", following[0])) else " "
                text += separator + following
            boxes = [b["locations"][0]["bbox"] for b in group]
            picture_groups.append({"picture_ref": picture["self_ref"],
                "text": text, "block_ids": [b["id"] for b in group],
                "page": group[0]["locations"][0]["page"],
                "bbox": [min(b[0] for b in boxes), min(b[1] for b in boxes),
                         max(b[2] for b in boxes), max(b[3] for b in boxes)],
                "method": "aligned_adjacent_lines", "requires_review": True})
    return {"schema_version": "1.1", "coordinate_system": {
        "origin": "top_left", "unit": "PDF point (1/72 inch)",
        "bbox_order": ["left", "top", "right", "bottom"],
        "page_numbering": "1-based"},
        "pages": [{"page": k, **v} for k, v in sorted(page_sizes.items())],
        "blocks": records, "picture_text_groups": picture_groups, "duplicates": duplicates}


def clean_text(text):
    # PDF visual line wrapping introduces spaces inside Chinese words.
    return re.sub(r"(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])", "", clean_pdf_glyphs(text)).strip()


def union(boxes):
    return [min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes)]


def xy_order(units):
    """Recursive whitespace cuts; keep each picture/table atomic."""
    if len(units) < 2:
        return units
    for axis in (1, 0):
        spans = sorted((u["bbox"][axis], u["bbox"][axis+2]) for u in units)
        end = spans[0][1]
        gaps = []
        for lo, hi in spans[1:]:
            if lo-end > (7 if axis == 1 else 12):
                gaps.append((lo-end, (lo+end)/2))
            end = max(end, hi)
        if gaps:
            _, cut = max(gaps)
            first = [u for u in units if u["bbox"][axis+2] <= cut]
            second = [u for u in units if u["bbox"][axis] >= cut]
            if first and second and len(first)+len(second) == len(units):
                return xy_order(first)+xy_order(second)
    return sorted(units, key=lambda u: (round(u["bbox"][1]/8), u["bbox"][0]))


def order_page(units):
    """Pair side-by-side headings, then keep each heading with its contents."""
    headers = [u for u in units if u["type"] == "section_header"]
    pairs = []
    for a in headers:
        for b in headers:
            if (a["bbox"][0] < b["bbox"][0] and
                    a["bbox"][2]+12 < b["bbox"][0] and
                    abs(a["bbox"][1]-b["bbox"][1]) < 18):
                pairs.append((min(a["bbox"][1], b["bbox"][1]), a, b))
    if not pairs:
        return xy_order(units)
    paired_ids = {id(u) for _, a, b in pairs for u in (a,b)}
    page_mid = (min(u["bbox"][0] for u in units)+max(u["bbox"][2] for u in units))/2
    page_width = max(u["bbox"][2] for u in units)-min(u["bbox"][0] for u in units)
    output, remaining = [], list(units)
    for top, left, right in sorted(pairs, key=lambda p: p[0]):
        if left not in remaining or right not in remaining:
            continue
        before = [u for u in remaining if u["bbox"][3] <= top]
        output.extend(xy_order(before))
        remaining = [u for u in remaining if u not in before]
        split = page_mid
        next_rows = [p[0] for p in pairs if p[0] > top+18]
        spanning = [u["bbox"][1] for u in remaining
                    if u["bbox"][1] > top+18 and
                    u["bbox"][2]-u["bbox"][0] > page_width*.6 and
                    u["bbox"][0] < split-15 and u["bbox"][2] > split+15]
        next_sections = [u["bbox"][1] for u in headers if id(u) not in paired_ids
                         and u["bbox"][1] > top+18]
        bottom = min(next_rows+spanning+next_sections+[float("inf")])
        band = [u for u in remaining if top-2 <= u["bbox"][1] < bottom]
        lhs = [u for u in band if (u["bbox"][0]+u["bbox"][2])/2 < split]
        rhs = [u for u in band if u not in lhs]
        output.extend(xy_order(lhs)+xy_order(rhs))
        remaining = [u for u in remaining if u not in band]
    return output+xy_order(remaining)


def mark_page_navigation(units, sizes):
    """Repeated narrow vertical margin labels are furniture, not body prose."""
    groups={}
    for unit in units:
        page=unit.get("page")
        if page not in sizes or not unit.get("bbox") or unit.get("table"):
            continue
        b=unit["bbox"]
        width,height=b[2]-b[0],b[3]-b[1]
        pw,ph=sizes[page]["width"],sizes[page]["height"]
        if (width <= 0 or height < width*2 or width > pw*.05 or
                not (b[2] < pw*.12 or b[0] > pw*.88)):
            continue
        key=(normalized(unit["text"]),tuple(round(x,2) for x in
             [b[0]/pw,b[1]/ph,b[2]/pw,b[3]/ph]))
        groups.setdefault(key,[]).append(unit)
    for group in groups.values():
        if len({u["page"] for u in group}) >= 3:
            for unit in group:
                unit["original_type"]=unit["type"]
                unit["type"]="page_navigation"
                unit["exclude_from_events"]=True
                unit["navigation_reason"]="repeated_vertical_margin_label"


def diagram_column_pairs(children):
    """Conservative two-tier spatial pairing; no semantic or connector inference."""
    items=[{'text':c['text'],'bbox':c['locations'][0]['bbox'],'block_id':c['id']}
           for c in children if len(c.get('locations',[]))==1]
    descriptions=[i for i in items if len(clean_text(i['text']))>=18]
    if not 3<=len(descriptions)<=8: return None
    descriptions.sort(key=lambda i:i['bbox'][0])
    heights=[i['bbox'][3]-i['bbox'][1] for i in descriptions]
    if max(i['bbox'][1] for i in descriptions)-min(i['bbox'][1] for i in descriptions)>max(heights)*.6:
        return None
    if any(a['bbox'][2]>=b['bbox'][0] for a,b in zip(descriptions,descriptions[1:])): return None
    labels=[]
    for i in items:
        if i in descriptions: continue
        pieces=i['text'].split()
        if not pieces or not all(re.fullmatch(r'[\u3400-\u9fff]{2,12}',s) for s in pieces): return None
        box=i['bbox']
        # Preserve explicit original word boundaries. Split boxes are estimates,
        # never presented as measured OCR token coordinates.
        total=sum(map(len,pieces));offset=0
        for piece in pieces:
            left=box[0]+(box[2]-box[0])*offset/total
            right=box[0]+(box[2]-box[0])*(offset+len(piece))/total
            labels.append(dict(text=piece,bbox=[left,box[1],right,box[3]],block_id=i['block_id'],
                               bbox_estimated=len(pieces)>1))
            offset+=len(piece)
    labels.sort(key=lambda i:i['bbox'][0])
    if len(labels)!=len(descriptions): return None
    if max(l['bbox'][1] for l in labels)-min(l['bbox'][1] for l in labels)>15: return None
    pairs=[]
    for label,desc in zip(labels,descriptions):
        l,d=label['bbox'],desc['bbox']
        if not (0<l[1]-d[3]<180): return None
        if abs((l[0]+l[2]-d[0]-d[2])/2)>max(d[2]-d[0],l[2]-l[0])*.6: return None
        pairs.append({'label':label['text'],'description':clean_text(desc['text']),
                      'source_block_ids':list(dict.fromkeys([desc['block_id'],label['block_id']])),
                      'description_bbox':d,'label_bbox':l,'label_bbox_estimated':label['bbox_estimated']})
    return {'method':'aligned_description_above_label','status':'spatial_candidate_needs_review','pairs':pairs}


def apply_diagram_pairs(unit, children):
    relation=diagram_column_pairs(children)
    if relation:
        unit.setdefault('original_picture_text',unit['text'])
        unit['diagram_relations']=relation
        escape=lambda t:t.replace('|','\\|').replace('\n',' ')
        unit['text']='\n'.join(['| 標籤 | 對應說明 |','| --- | --- |']+
            [f"| {escape(p['label'])} | {escape(p['description'])} |" for p in relation['pairs']])
        unit['review_required']=True
        unit['review_reason']='Spatial pairing candidate; connector lines and meaning are not verified.'
    return unit


def build_units(raw, events):
    blocks = events["blocks"]
    by_ref = {b["docling_ref"]: b for b in blocks}
    consumed, units, changes = set(), [], []
    sizes = {p["page"]: p for p in events["pages"]}
    for pic in raw.get("pictures", []):
        children = [by_ref[c["$ref"]] for c in pic.get("children", []) if c["$ref"] in by_ref
                    and by_ref[c["$ref"]]["id"] not in consumed
                    and by_ref[c["$ref"]]["type"] != "table"
                    and len(by_ref[c["$ref"]]["locations"]) == 1]
        if not children:
            continue
        prov = pic.get("prov", [])
        if not prov:
            continue
        page = prov[0]["page_no"]
        children = [c for c in children if c["locations"][0]["page"] == page]
        if not children:
            continue
        b = prov[0]["bbox"]
        box = [b["l"], b["t"], b["r"], b["b"]]
        if b["coord_origin"] == "BOTTOMLEFT":
            h = sizes[page]["height"]
            box = [b["l"], h-b["t"], b["r"], h-b["b"]]
        child_ids = [c["id"] for c in children]
        consumed.update(child_ids)
        if children:
            # Use image-local XY cuts so diagram labels stay together.
            groups = [g for g in events.get("picture_text_groups", [])
                      if g["picture_ref"] == pic["self_ref"]]
            # Do not join code, numbers or long phrases into invented words.
            local = []
            local_ids = {c["id"] for c in children}
            for group in groups:
                if not set(group["block_ids"]).issubset(local_ids):
                    continue
                members = [next(c for c in children if c["id"] == k) for k in group["block_ids"]]
                short_han = all(re.fullmatch(r"[\u3400-\u9fff]{1,4}", clean_text(c["text"])) for c in members)
                if short_han and len(group["text"]) <= 8:
                    local.append({"text": clean_text(group["text"]), "bbox": group["bbox"]})
                else:
                    local.extend({"text": c["text"], "bbox": c["locations"][0]["bbox"]}
                                 for c in members)
            included = {k for g in groups if set(g["block_ids"]).issubset(local_ids)
                        for k in g["block_ids"]}
            local.extend({"text": c["text"], "bbox": c["locations"][0]["bbox"]}
                         for c in children if c["id"] not in included)
            text = "\n".join(clean_text(c["text"]) for c in xy_order(local))
        units.append({"type": "picture_text", "picture_ref": pic["self_ref"],
                      "page": page, "bbox": box, "text": text,
                      "block_ids": child_ids,
                      "text_method": "extracted_picture_text",
                      "review_required": True,
                      "review_reason": "OCR and image-local grouping are heuristic; no manual correction applied."})
        apply_diagram_pairs(units[-1],children)
    for block in blocks:
        if block["id"] in consumed:
            continue
        locations = block["locations"]
        if not locations:
            units.append({"type": block["type"], "page": None, "bbox": None,
                          "text": clean_text(block["text"]), "block_ids": [block["id"]],
                          "locations": [], "review_required": True,
                          "review_reason": "No page provenance; retained at end of document."})
            if block.get("table"):
                units[-1]["table"] = clean_table_data(block["table"])
                units[-1]["text"] = table_markdown(block["table"])
            continue
        loc = locations[0]
        text = clean_text(block["text"])
        units.append({"type": block["type"], "page": loc["page"], "bbox": loc["bbox"],
                      "text": text, "block_ids": [block["id"]],
                      "text_method": "original_extraction_whitespace_cleanup",
                      "locations": locations})
        if block.get("table"):
            units[-1]["table"] = clean_table_data(block["table"])
            units[-1]["docling_ref"] = block["docling_ref"]
            units[-1]["text"] = table_markdown(block["table"])
            units[-1]["text_method"] = "table_cell_row_column_export"
        if text != block["text"]:
            changes.append({"block_id": block["id"], "page": loc["page"],
                            "before": block["text"], "after": text,
                            "method": "pdf_glyph_and_whitespace_cleanup"})
    mark_page_navigation(units,sizes)
    ordered = []
    for page in sorted(sizes):
        page_units = [u for u in units if u["page"] == page]
        headers = [u for u in page_units if u["type"] == "page_header"]
        footers = [u for u in page_units if u["type"] == "page_footer"]
        navigation=[u for u in page_units if u["type"] == "page_navigation"]
        content = [u for u in page_units if u not in headers+footers+navigation]
        ordered.extend(xy_order(headers)+order_page(content)+xy_order(footers)+xy_order(navigation))
    ordered.extend(u for u in units if u["page"] not in sizes)
    for i, u in enumerate(ordered):
        u["id"] = f"unit_{i+1:06d}"
        u["reading_order"] = i
    return ordered, changes


def export_md(units, segmented=None):
    out, page, navigation = [], object(), False
    if segmented is not None:
        out.extend(["# 事件切分索引","> 以下為規則式事件候選，需人工確認；不是已驗證的經歷。",
                    "| 事件 | 所屬課程 | 類型 | PDF 頁碼 | 狀態 |","| --- | --- | --- | --- | --- |"])
        event_lookup={e['id']:e for e in segmented}
        for event in segmented:
            title=event["title"].replace("|","\\|").replace("\n"," ")
            parent=event_lookup.get(event.get('parent_event_id'),{}).get('title','—').replace('|','\\|')
            label=('↳ ' if event.get('parent_event_id') else '')+title
            out.append(f"| {event['id']}：{label} | {parent} | {event['type']} | {', '.join(map(str,event.get('all_pages',event['pages'])))} | 待確認 |")
        if not segmented:
            out.append("尚無足夠依據建立事件；原文保留如下。")
        out.append("# 原文解析")
    for u in units:
        if page != u["page"]:
            page = u["page"]
            navigation=False
            out.append(f"# PDF 第 {page} 頁" if page is not None else "# 未定位文字")
        if u["type"] == "page_navigation" and not navigation:
            out.append("## 頁面導覽（非正文）")
            navigation=True
        out.append(f"<!-- page: {page}; unit: {u['id']}; source: {u.get('picture_ref', ','.join(u['block_ids']))} -->")
        prefix = "## " if u["type"] in ("section_header", "title") else ""
        if u.get("text_method") == "encoding_fallback_ocr":
            out.append("> 此區原始文字編碼異常，以下為局部 OCR 補救結果，尚需核對原圖。"
                       + ("含未辨識儲存格。" if u.get("ocr_cell_coverage",1) < 1 else ""))
        out.append(prefix+u["text"])
    return "\n\n".join(out)+"\n"


def refine_events(raw, events=None):
    """Document-independent postprocessing. Never supplies replacement words."""
    if events is None:
        events = simplify(raw)
    units, changes = build_units(raw, events)
    events["schema_version"] = "2.1"
    events["charspan_reference"] = "original block text; not offsets into cleaned reading_units text"
    events["reading_units"] = units
    events["corrections"] = changes
    events["processing_policy"] = {
        "document_specific_overrides": False,
        "manual_transcriptions": False,
        "ocr_spelling_autocorrect": False,
        "pdf_compatibility_glyph_cleanup": True,
        "reading_order": "geometry_and_heading_heuristics",
        "tables": "original_cell_indices_and_spans; generic headers when absent"}
    events["reading_order_policy"] = "Use reading_units for reading order; blocks retain original extraction."
    events["warnings"] = [
        "Layout order is heuristic and may require review.",
        "OCR words are not guessed or replaced; review picture text against the PDF.",
        "Markdown cannot express merged table cells; full spans and cell coordinates remain in table JSON."]
    events["event_input_policy"]="Skip page_header, page_footer and units with exclude_from_events=true."
    return events


EVENT_WORDS = re.compile(
    r"競賽|比賽|大賽|盃|獎|奧林匹亞|檢測|成績證明|參訪|探訪|展演|聯展|成發|社團|總務|股長|主辦|"
    r"志工|服務|營隊|夏令營|研習|年會|講者|主講|行政組|場務|課程|專題|設計|製作|"
    r"資料分析|程式|網站|系統|作品|工具|名片|觀光小書|漏洞|資訊安全|繪圖|政策|地理|"
    r"camp|hackathon|workshop|competition|conference|project|course",
    re.I)
GENERIC_LABELS = {
    "課程概述","課程摘要","個人資料","個人特質","個人簡歷","簡歷","自傳","家庭背景", 
    "學習歷程","團隊合作","主動學習","解決問題與邏輯思考","幹部經驗","社團經驗","校園經歷",
    "動機","分析動機","設計動機","我的成果","課程成果","我的設計","我的分析","成果精華",
    "心得反饋","心得反省","心得","課程心得","學習反思","學習指標","反思與學習指標",
    "獲獎紀錄","獲獎記錄","作品截圖","專案開發","研習課程/社群參與","社群參與",
    "漏洞回報紀錄","網路交流","休閒興趣","其他資料","紀錄回顧","比較","分工","優點","缺點",
    "困難","解決方法","解決辦法","學習過程中遇到的困難","申請動機","讀書計畫",
    "未來學習計畫","生涯規劃","學習歷程反思","目錄","contents","tableofcontents"}


def title_key(text):
    text=unicodedata.normalize("NFKC",clean_text(text)).strip()
    text=re.sub(r"^(?:\d{1,2}\s+|[壹貳參肆伍陸一二三四五六七八九十]+[、.．])","",text)
    return re.sub(r"[\s，,：:、.．？！?！·•\-—–()（）]","",text).lower()


def generic_heading(text):
    key=title_key(text)
    labels={title_key(t) for t in GENERIC_LABELS}
    return (key in labels or not key or len(key)<2 or
            bool(re.search(r"大學|學院|高中|中學|學系|系所",key)) and bool(re.search(r"(?:大學|學院|高中|中學|學系|系所)$",key)) or
            bool(re.fullmatch(r"(?:高|國|大)[一二三四](?:上|下)?(?:學期)?.{0,12}(?:課程|學習成果|加深加廣)",key)) or
            bool(re.fullmatch(r"高[一二三]|大[一二三四]|\d{1,3}",key)) or
            any(key.startswith(title_key(t)) for t in
                ["課程概述","學習過程中遇到的困難","意義與內涵","資料來源","成果影片","成果網址"]) or
            sum(title_key(t) in key for t in ["獲獎紀錄","專案開發","社群參與","網路交流"])>=3)


def same_event_title(a,b):
    ka,kb=title_key(a),title_key(b)
    school_a=set(re.findall(r"高[一二三]|國[一二三]",ka))
    school_b=set(re.findall(r"高[一二三]|國[一二三]",kb))
    if school_a and school_b and school_a != school_b:
        return False
    def identity(key):
        key=re.sub(r"^(?:高|國)[一二三](?:上|下)?(?:學期)?","",key)
        return re.split(r"負責人|主辦方|獲得",key)[0]
    ka,kb=identity(ka),identity(kb)
    if ka==kb:
        return True
    years_a=set(re.findall(r"(?:19|20)\d{2}",ka))
    years_b=set(re.findall(r"(?:19|20)\d{2}",kb))
    if years_a and years_b and years_a != years_b:
        return False
    return min(len(ka),len(kb))>=5 and (ka in kb or kb in ka)


def event_kind(title):
    if re.search(r"競賽|比賽|盃|獎|奧林匹亞",title): return "competition"
    if re.search(r"檢定|檢測|成績證明|證照",title,re.I): return "certification"
    if re.search(r"漏洞|控管|身份認證|注入",title): return "security_contribution"
    if re.search(r"參訪|探訪|聯展|成發|展演|社團|總務|股長|校內",title): return "school_activity"
    if re.search(r"研習|年會|營隊|夏令營|camp|講者|主講|場務|行政組",title,re.I): return "participation"
    if re.search(r"課程|資料分析|繪圖|政策|名片|觀光|地理",title,re.I): return "course_project"
    if re.search(r"程式|專案|設計|製作|網站|系統|project",title,re.I): return "project_or_contribution"
    return "experience"


def segment_events(document):
    """Evidence-preserving event candidates, not factual inference or an LLM."""
    units=document["reading_units"]
    blocks={b["id"]:b for b in document["blocks"]}
    sizes={p["page"]:p for p in document["pages"]}
    pages={p:[] for p in sizes}
    assignments={}
    events=[]
    current=None
    mode="past"
    context=None

    def excluded(u):
        return u["type"] in ("page_header","page_footer","page_navigation","footnote") or u.get("exclude_from_events")

    def anchors_for(page_units):
        anchors=[]
        for u in page_units:
            if u.get("exclude_from_events") or u["type"] in ("page_navigation","page_footer","footnote","table"):
                continue
            if u["type"] in ("section_header","title","page_header"):
                anchors.append({"text":u["text"],"unit":u,"bbox":u["bbox"],"rule":"document_heading"})
            elif u["type"]=="picture_text":
                for bid in u["block_ids"]:
                    b=blocks[bid]
                    if len(b["locations"])!=1: continue
                    box=b["locations"][0]["bbox"]
                    text=clean_text(b["text"])
                    if b["type"]=="caption" and re.match(r"圖\s*\d+",text):
                        subject=re.sub(r"^圖\s*\d+\s*","",text)
                        if re.search(r"[A-Za-z]{4,}|工具|程式|網站",subject):
                            anchors.append({"text":subject,"unit":u,"bbox":box,"block_id":bid,
                                            "rule":"figure_caption_subject_candidate"})
                    if (box[3]-box[1]>=13 and 3<=len(text)<=85 and
                            box[1]<sizes[u["page"]]["height"]*.3 and
                            box[0]>sizes[u["page"]]["width"]*.1):
                        anchors.append({"text":text,"unit":u,"bbox":box,"block_id":bid,
                                        "rule":"picture_child_title_candidate"})
        return anchors

    for u in units:
        if u["page"] in pages: pages[u["page"]].append(u)
        else: assignments[u["id"]]={"reason":"missing_page_provenance"}
    anchors={p:anchors_for(us) for p,us in pages.items()}
    all_anchors=[a for aa in anchors.values() for a in aa]

    def title_score(a):
        text=a["text"]
        if generic_heading(text) or len(text)>100: return -100
        box=a["bbox"]
        h=sizes[a["unit"]["page"]]["height"]
        latin_title=bool(re.fullmatch(r"(?:[A-Z][a-z]+){2,}|[A-Z]{3,8}|[A-Za-z][A-Za-z0-9 .+\-]{4,60}",text.strip()))
        score=2 if EVENT_WORDS.search(text) or latin_title else 0
        if a["rule"]=="document_heading": score+=1
        if a["rule"]=="figure_caption_subject_candidate": score+=2
        if a["rule"]=="document_heading" and box[1]<h*.2 and box[3]-box[1]>=14:
            score+=2
        if box[1]<h*.25: score+=1
        if box[3]-box[1]>=28: score+=1
        repeated={x["unit"]["page"] for x in all_anchors if same_event_title(text,x["text"])}
        if len(repeated)>=2: score+=3
        return score

    def start(a,rule=None):
        nonlocal current
        existing=next((e for e in events if same_event_title(e["title"],a["text"])),None)
        if existing:
            current=existing
        else:
            current={"id":f"event_{len(events)+1:04d}","title":a["text"],
                     "type":event_kind(a["text"]),"status":"candidate_needs_review",
                     "context_title":context,"boundary_evidence":[],"source_unit_ids":[],
                     "quality_flags":[],"subsections":[]}
            events.append(current)
        evidence={"unit_id":a["unit"]["id"],"text":a["text"],"rule":rule or a["rule"]}
        if a.get("block_id"): evidence["block_id"]=a["block_id"]
        if evidence not in current["boundary_evidence"]: current["boundary_evidence"].append(evidence)

    for page,page_units in sorted(pages.items()):
        aa=anchors[page]
        upper=[a for a in aa if a["bbox"][1]<sizes[page]["height"]*.3]
        keys=[title_key(a["text"]) for a in upper]
        has_toc=any("目錄" in k or "tableofcontents" in k for k in keys) or any(
            blocks[k].get("source_label")=="document_index" for u in page_units for k in u["block_ids"])
        if has_toc:
            current=None
            for u in page_units: assignments[u["id"]]={"reason":"table_of_contents_or_overview"}
            continue
        if any(k in {title_key(t) for t in ["讀書計畫","申請動機","未來學習計畫","生涯規劃"]} for k in keys):
            mode="plan"
        elif any(k in {title_key(t) for t in ["其他資料","獲獎紀錄","作品截圖","自傳","學習歷程"]} for k in keys):
            mode="past"
        reflection=any(title_key(a["text"]) in {title_key(t) for t in ["學習反思","學習歷程反思","反思與學習指標","紀錄回顧"]}
                       and a["bbox"][3]-a["bbox"][1]>=28 for a in aa) or any(
                       k in {"學習反思","學習歷程反思","反思與學習指標","紀錄回顧"} for k in keys)
        overview=any(k in {title_key(t) for t in ["其他資料","休閒興趣"]} for k in keys)
        if reflection and any(title_score(a)>=3 and EVENT_WORDS.search(a["text"])
                              and not generic_heading(a["text"]) for a in upper):
            reflection=False
        if overview:
            mode="past"
            current=None
            for u in page_units: assignments[u["id"]]={"reason":"overview_or_mixed_experiences"}
            continue
        if mode=="plan" or reflection:
            current=None
            for u in page_units: assignments[u["id"]]={"reason":"future_plan_or_application" if mode=="plan" else "reflection_or_summary"}
            continue
        # A course portfolio cover supplies context, not a fabricated activity.
        portfolio=[a for a in upper if re.search(r"課程學習成果|課程成果集|學習歷程檔案",a["text"])
                   and a["bbox"][3]-a["bbox"][1]>=28]
        if portfolio:
            context=portfolio[0]["text"]
            current=None
            for u in page_units: assignments[u["id"]]={"reason":"portfolio_context"}
            continue
        candidates=[a for a in aa if title_score(a)>=3]
        upper_candidates=[a for a in candidates if a["bbox"][1]<sizes[page]["height"]*.25]
        # Repeated running titles establish the enclosing event. Smaller
        # headings underneath become subsections, not separate events.
        formal=[a for a in upper_candidates if a["rule"]=="document_heading"]
        page_anchor=min(formal or upper_candidates,key=lambda a:(a["bbox"][1],-title_score(a)),default=None)
        large_covers=[a for a in candidates if a["bbox"][3]-a["bbox"][1]>=28]
        if not formal and large_covers and sum(not excluded(u) for u in page_units)<=6:
            page_anchor=max(large_covers,key=title_score)
        if page_anchor is None and sum(not excluded(u) for u in page_units)<=6:
            covers=[a for a in candidates if a["bbox"][3]-a["bbox"][1]>=28]
            page_anchor=max(covers,key=title_score,default=None)
        if page_anchor is None and not any(a["rule"]=="document_heading" for a in candidates):
            captions=[a for a in candidates if a["rule"]=="figure_caption_subject_candidate"]
            if len(captions)==1: page_anchor=captions[0]
        if page_anchor:
            start(page_anchor)
        resume=any(title_key(a["text"]) in {"個人簡歷","幹部經驗","社團經驗","校園經歷"} for a in aa)
        for u in page_units:
            if excluded(u):
                assignments[u["id"]]={"reason":"page_furniture"}
                continue
            if resume:
                if u["type"]=="list_item" and EVENT_WORDS.search(u["text"]) and len(u["text"])>=5:
                    start({"text":u["text"],"unit":u},"resume_activity_item")
                    current["quality_flags"].append("brief_resume_item")
                else:
                    assignments[u["id"]]={"reason":"profile_or_resume_context"}
                    continue
            elif not page_anchor:
                matched=next((a for a in candidates if a["unit"]["id"]==u["id"]),None)
                if matched and (matched["rule"]!="figure_caption_subject_candidate" or current is None): start(matched)
                elif u["type"]=="section_header" and title_key(u["text"]) in {
                        "團隊合作","主動學習","解決問題與邏輯思考"}:
                    current=None
                elif current is None and u["type"]=="text" and len(u["text"])>=30:
                    quoted=re.search(r"《([^》]{3,60})》",u["text"])
                    excerpt=re.split(r"[，,。]",u["text"])[0]
                    title=quoted.group(1) if quoted and EVENT_WORDS.search(quoted.group(1)) else excerpt
                    if (EVENT_WORDS.search(title) and len(title)<=60 and
                            re.search(r"我|擔任|舉辦|參加|參與|製作|比賽|高[一二三]",u["text"])):
                        start({"text":title,"unit":u},"narrative_excerpt_candidate")
                        current["quality_flags"].append("narrative_boundary_uncertain")
            if current is None:
                assignments[u["id"]]={"reason":"insufficient_event_boundary"}
                continue
            if u["id"] not in current["source_unit_ids"]: current["source_unit_ids"].append(u["id"])
            assignments[u["id"]]={"event_id":current["id"]}
            if u["type"]=="section_header" and not same_event_title(current["title"],u["text"]):
                current["subsections"].append({"title":u["text"],"source_unit_ids":[]})
            if current["subsections"]:
                current["subsections"][-1]["source_unit_ids"].append(u["id"])
            if u.get("review_required") or "〔未辨識〕" in u["text"] or "〔待核對" in u["text"]:
                current["quality_flags"].append("source_requires_review")
        if resume:
            current=None

    lookup={u["id"]:u for u in units}
    # A title with no body is not promoted into an event.
    events=[e for e in events if e["source_unit_ids"]]
    remap={e["id"]:f"event_{i:04d}" for i,e in enumerate(events,1)}
    for e in events: e["id"]=remap[e["id"]]
    for value in assignments.values():
        if value.get("event_id") in remap: value["event_id"]=remap[value["event_id"]]
    kept={e["id"] for e in events}
    # Course covers provide explicit hierarchy evidence. Numbering alone is
    # insufficient: require a course summary and a prominent named cover.
    covers=[]
    for p,us in sorted(pages.items()):
        has_summary=any(title_key(u['text']) in ('課程摘要','課程概述') for u in us)
        has_course_context=any(title_key(u['text'])=='個人資料' or
                               u['type']=='page_header' and '課程' in u['text'] for u in us)
        if not has_summary or not has_course_context: continue
        headings=[u for u in us if u['type'] in ('section_header','title')
                  and u['bbox'][3]-u['bbox'][1]>=28 and not generic_heading(u['text'])]
        if not headings: continue
        heading=max(headings,key=lambda u:u['bbox'][3]-u['bbox'][1])
        parent=next((e for e in events if same_event_title(e['title'],heading['text'])
                     and heading['id'] in e['source_unit_ids']),None)
        if parent: covers.append((p,parent,heading))
    for index,(p,parent,heading) in enumerate(covers):
        end=covers[index+1][0] if index+1<len(covers) else max(pages)+1
        children=[]
        for e in events:
            first=min(lookup[k]['page'] for k in e['source_unit_ids'])
            if first<=p or first>=end or e is parent: continue
            if not re.match(r'^\s*[0-9０-９]{1,2}\s*[^0-9０-９]',e['title']):
                end=first
                break
            children.append(e)
        if not children: continue
        parent['type']='course_portfolio'
        parent['child_event_ids']=[e['id'] for e in children]
        parent['hierarchy_evidence']={'unit_id':heading['id'],'rule':'course_summary_cover_and_numbered_children'}
        for child in children:
            child['parent_event_id']=parent['id']
        # Course-wide reflection belongs to the parent, not its last activity.
        for u in units:
            if p<u['page']<end and assignments.get(u['id'],{}).get('reason')=='reflection_or_summary' and not excluded(u):
                parent['source_unit_ids'].append(u['id'])
                assignments[u['id']]={'event_id':parent['id']}
    for event in events:
        evidence=[lookup[k] for k in event["source_unit_ids"]]
        event["pages"]=sorted({u["page"] for u in evidence})
        event["text"]="\n\n".join(u["text"] for u in evidence)
        event["source_block_ids"]=list(dict.fromkeys(k for u in evidence for k in u["block_ids"]))
        event["locations"]=[{"unit_id":u["id"],"page":u["page"],"bbox":u["bbox"]} for u in evidence]
        event["quality_flags"]=sorted(set(event["quality_flags"]))
        event["time_mentions"]=[]
        event["role_mentions"]=[]
        event["outcome_mentions"]=[]
        patterns={"time_mentions":r"(?:19|20)\d{2}(?:年(?:\d{1,2}月(?:\d{1,2}日)?)?)?|(?:高|國|大)[一二三四](?:上|下)?(?:學期)?|(?:今年|去年|前年)(?:暑假|寒假)?",
                  "role_mentions":r"(?:擔任|負責)[^，。；\n]{1,25}|主辦方|總務|股長|組長|講者|學員|場務組員|行政組人事",
                  "outcome_mentions":r"第\s*[一二三四五六七八九十\d]+\s*名|金獎|銀獎|銅獎|滿級分|實作題滿分"}
        for u in evidence:
            if u["type"]=="picture_text" or u.get("recovery_status"):
                continue  # UI screenshots and low-confidence OCR are not personal facts.
            for field,pattern in patterns.items():
                for match in re.finditer(pattern,unicodedata.normalize("NFKC",u["text"])):
                    item={"text":match.group(),"unit_id":u["id"],"status":"explicit_mention_unverified"}
                    if item not in event[field]: event[field].append(item)
        event["date_normalized"]=None
        event["possible_related_event_ids"]=[other["id"] for other in events
            if other is not event and len(set(re.findall(r"[A-Za-z]{4,}",event["title"].lower())) &
                                         set(re.findall(r"[A-Za-z]{4,}",other["title"].lower())))>0]
    for uid,value in assignments.items():
        if value.get("event_id") and value["event_id"] not in kept:
            assignments[uid]={"reason":"title_without_event_content"}
    document["events"]=events
    by_id={e['id']:e for e in events}
    for e in events:
        e.setdefault('parent_event_id',None)
        e.setdefault('child_event_ids',[])
        e['all_pages']=sorted(set(e['pages'])|{p for cid in e['child_event_ids'] for p in by_id[cid]['pages']})
    document["event_assignments"]=assignments
    document["segmentation"]={"method":"rule_based_v2_hierarchy","event_count":len(events),
        "top_level_event_count":sum(e['parent_event_id'] is None for e in events),
        "child_event_count":sum(e['parent_event_id'] is not None for e in events),
        "assigned_units":sum("event_id" in a for a in assignments.values()),
        "unassigned_units":sum("event_id" not in a for a in assignments.values()),
        "manual_confirmation_required":True,
        "limitations":["Boundaries and categories are candidates, not verified facts.",
                       "No inferred dates, no event extraction from table rows, no semantic coreference."]}
    return document


def encoding_flags(text):
    """High-specificity checks, not a language/grammar correctness score."""
    visible = max(1, len(re.sub(r"\s", "", text)))
    replacement = text.count("\ufffd")
    control = sum(unicodedata.category(c) == "Cc" and c not in "\n\r\t" for c in text)
    private = sum(unicodedata.category(c) == "Co" for c in text)
    flags = []
    if replacement >= 2 or replacement / visible >= .05:
        flags.append("replacement_characters")
    if control >= 2 and control / visible >= .01:
        flags.append("embedded_control_bytes")
    if private >= 2 and private / visible >= .03:
        flags.append("private_use_font_encoding")
    return flags


def table_from_ocr(unit, tokens, page_height):
    """Recover text using existing cell geometry; keep spans and source boxes."""
    table = deepcopy(unit["table"])
    cells = table.get("table_cells", [])
    if not cells:
        return None, 0
    def rect(cell):
        b = cell.get("bbox")
        if not b:
            return None
        if b.get("coord_origin") == "BOTTOMLEFT":
            return [b["l"],page_height-b["t"],b["r"],page_height-b["b"]]
        return [b["l"],b["t"],b["r"],b["b"]]
    row_centers, col_centers = {}, {}
    for i in range(table["num_rows"]):
        boxes = [rect(c) for c in cells if c["start_row_offset_idx"] == i
                 and c.get("row_span",1) == 1 and rect(c)]
        if boxes:
            row_centers[i] = median((b[1]+b[3])/2 for b in boxes)
    for i in range(table["num_cols"]):
        boxes = [rect(c) for c in cells if c["start_col_offset_idx"] == i
                 and c.get("col_span",1) == 1 and rect(c)]
        if boxes:
            col_centers[i] = median((b[0]+b[2])/2 for b in boxes)
    if len(row_centers) != table["num_rows"] or len(col_centers) != table["num_cols"]:
        return None, 0
    table_box = unit.get("bbox") or union([rect(c) for c in cells if rect(c)])
    buckets = {id(c):[] for c in cells}
    for token in tokens:
        box = token["bbox"]
        x,y = (box[0]+box[2])/2,(box[1]+box[3])/2
        if not (table_box[0]-2 <= x <= table_box[2]+2 and
                table_box[1]-2 <= y <= table_box[3]+2):
            continue
        r = min(row_centers,key=lambda k:abs(row_centers[k]-y))
        c = min(col_centers,key=lambda k:abs(col_centers[k]-x))
        for cell in cells:
            if (cell["start_row_offset_idx"] <= r < cell["end_row_offset_idx"] and
                    cell["start_col_offset_idx"] <= c < cell["end_col_offset_idx"]):
                buckets[id(cell)].append(token)
                break
    recognized = 0
    damaged = sum(bool(encoding_flags(c.get("text",""))) for c in cells)
    widespread = damaged >= 3 and damaged / len(cells) >= .25
    for cell in cells:
        assigned = sorted(buckets[id(cell)],key=lambda t:(round(t["bbox"][1]/4),t["bbox"][0]))
        cell["original_text"] = cell.get("text","")
        cell["ocr_tokens"] = assigned
        if not widespread and not encoding_flags(cell["original_text"]):
            cell["text"] = clean_text(cell["original_text"])
            cell["recovery_status"] = "native_preserved"
            recognized += bool(cell["text"])
            continue
        cell["text"] = clean_text(" ".join(t["text"] for t in assigned)) if assigned else "〔未辨識〕"
        cell["recovery_status"] = "ocr_candidate" if assigned else "unrecognized"
        if assigned and re.search(r"(?:19|20)\d[A-Za-z]年|\d{3,4}年\d{1,2}月",cell["text"]):
            cell["text"] = "〔待核對："+cell["text"]+"〕"
            cell["recovery_status"] = "suspicious_date_candidate"
        recognized += bool(assigned)
    # Rebuild grid references so no stale encoded cell text survives there.
    grid = [[None for _ in range(table["num_cols"])] for _ in range(table["num_rows"])]
    for cell in cells:
        for r in range(cell["start_row_offset_idx"],cell["end_row_offset_idx"]):
            for c in range(cell["start_col_offset_idx"],cell["end_col_offset_idx"]):
                grid[r][c] = cell
    table["grid"] = grid
    return table, recognized / len(cells)


def retry_uncertain_cells(table, reader, page_image, scale, page_height, limit=32):
    """Recognize known text-cell crops; never infer values from other rows."""
    import numpy as np
    attempts = 0
    for cell in table.get("table_cells",[]):
        if cell.get("recovery_status") not in ("unrecognized","suspicious_date_candidate"):
            continue
        if attempts >= limit or not cell.get("bbox"):
            continue
        b = cell["bbox"]
        box = [b["l"],b["t"],b["r"],b["b"]]
        if b.get("coord_origin") == "BOTTOMLEFT":
            box = [b["l"],page_height-b["t"],b["r"],page_height-b["b"]]
        bounds = [max(0,round((box[0]-2)*scale)),max(0,round((box[1]-2)*scale)),
                  min(page_image.width,round((box[2]+2)*scale)),
                  min(page_image.height,round((box[3]+2)*scale))]
        if bounds[2] <= bounds[0] or bounds[3] <= bounds[1]:
            continue
        crop = page_image.crop(bounds).convert("L")
        hits = reader.recognize(np.array(crop),detail=1,paragraph=False,batch_size=1,workers=0)
        attempts += 1
        candidates = [{"text":clean_text(t),"confidence":float(c)} for _,t,c in hits]
        cell["ocr_retry_candidates"] = candidates
        valid = [c for c in candidates if c["confidence"] >= .55 and c["text"]
                 and any(unicodedata.category(char)[0] in "LN" for char in c["text"])
                 and not encoding_flags(c["text"]) and not re.search(r"(?:19|20)\d[A-Za-z]年",c["text"])]
        if valid:
            cell["previous_ocr_text"] = cell["text"]
            cell["text"] = " ".join(c["text"] for c in valid)
            cell["recovery_status"] = "ocr_retry_candidate"
            if re.search(r"\d{3,4}年\d{1,2}月|\d+\s*[~～–-]\s*\d+",cell["text"]):
                cell["text"] = "〔待核對："+cell["text"]+"〕"
                cell["recovery_status"] = "ocr_retry_uncertain"
    return attempts


def ocr_region(pdf, region, reader):
    import numpy as np
    page = pdf[region["page"]-1]
    try:
        scale = 4.0
        bitmap = page.render(scale=scale)
        image = bitmap.to_pil().copy()
        bitmap.close()
        width,height = page.get_size()
        b = region["bbox"]
        cropbox = [max(0,b[0]-3),max(0,b[1]-3),min(width,b[2]+3),min(height,b[3]+3)]
        pixelbox = [round(v*scale) for v in cropbox]
        if pixelbox[2] <= pixelbox[0] or pixelbox[3] <= pixelbox[1]:
            raise ValueError("OCR region lies outside the PDF page")
        cropped = image.crop(pixelbox)
        image.close()
        try:
            hits = reader.readtext(np.array(cropped),detail=1,paragraph=False,
                                   batch_size=4,workers=0,canvas_size=4000,width_ths=.3)
        finally:
            cropped.close()
        result=[]
        for polygon,text,confidence in hits:
            box = [min(p[0] for p in polygon)/scale+pixelbox[0]/scale,
                   min(p[1] for p in polygon)/scale+pixelbox[1]/scale,
                   max(p[0] for p in polygon)/scale+pixelbox[0]/scale,
                   max(p[1] for p in polygon)/scale+pixelbox[1]/scale]
            result.append({"page":region["page"],"bbox":box,"text":clean_text(text),
                           "confidence":float(confidence)})
        return result
    finally:
        page.close()


def collect_region_ocr(regions, callback):
    tokens,errors,completed=[],[],0
    for region in regions:
        try:
            logging.info("Encoding recovery: PDF page %s, region %s",region["page"],region["id"])
            tokens.extend(callback(region))
            completed += 1
        except Exception as exc:
            errors.append({"page":region["page"],"region":region["id"],"error":str(exc)})
            logging.warning("Skipping failed OCR region %s: %s",region["id"],exc)
    return tokens,errors,completed


def recover_encoding(events, pdf_path, enabled=True, gpu=False, reader=None):
    """OCR only suspicious regions. No page numbers or known answers embedded."""
    units = events["reading_units"]
    source = {b["id"]: b for b in events["blocks"]}
    suspects = []
    for unit in units:
        original = "\n".join(source[k]["text"] for k in unit["block_ids"])
        flags = encoding_flags(original) or encoding_flags(unit["text"])
        if flags and unit.get("bbox") and unit.get("page"):
            unit["encoding_flags"] = flags
            unit["original_extracted_text"] = unit["text"]
            unit["review_required"] = True
            suspects.append(unit)
    events["encoding_recovery"] = {"suspect_units":len(suspects),"regions_processed":0,
        "recovered_units":0,"partial_units":0,"failed_units":0,"cell_retries":0,
        "status":"not_needed" if not suspects else "pending"}
    if not suspects:
        return events
    # Choose outermost suspect regions, so a table inside a picture uses the
    # same OCR pass rather than repeating OCR per cell or per overlapping unit.
    regions = []
    for unit in sorted(suspects,key=lambda u:-(u["bbox"][2]-u["bbox"][0])*(u["bbox"][3]-u["bbox"][1])):
        a = unit["bbox"]
        if not any(r["page"] == unit["page"] and r["bbox"][0] <= a[0]+1
                   and r["bbox"][1] <= a[1]+1 and r["bbox"][2] >= a[2]-1
                   and r["bbox"][3] >= a[3]-1 for r in regions):
            regions.append(unit)
    detections = []
    error = None
    if enabled:
        try:
            import easyocr
            import pypdfium2
            if reader is None:
                reader = easyocr.Reader(["ch_tra","en"],gpu=gpu,verbose=False)
            with pypdfium2.PdfDocument(pdf_path) as pdf:
                detections,errors,completed = collect_region_ocr(regions,lambda r:ocr_region(pdf,r,reader))
                events["encoding_recovery"]["regions_processed"] = completed
                events["encoding_recovery"]["region_errors"] = errors
        except Exception as exc:
            error = str(exc)
            logging.warning("Encoding recovery incomplete: %s",exc)
    heights = {p["page"]:p["height"] for p in events["pages"]}
    table_suspects = [u for u in suspects if u.get("table")]
    retry_page,retry_image,retry_budget=None,None,32
    def inside(token, unit):
        a,b = token["bbox"],unit["bbox"]
        x,y=(a[0]+a[2])/2,(a[1]+a[3])/2
        return token["page"] == unit["page"] and b[0]-2 <= x <= b[2]+2 and b[1]-2 <= y <= b[3]+2
    for unit in suspects:
        # Keep low-confidence candidates in the audit, but not as trusted text.
        tokens = [t for t in detections if inside(t,unit)]
        unit["ocr_candidates"] = tokens
        accepted = [t for t in tokens if t["confidence"] >= .55 and t["text"] and not encoding_flags(t["text"])]
        if unit["type"] == "picture_text":
            accepted = [t for t in accepted if not any(inside(t,tab) for tab in table_suspects)]
        status = "failed"
        if unit.get("table"):
            repaired,coverage = table_from_ocr(unit,accepted,heights[unit["page"]])
            unit["ocr_cell_coverage"] = coverage
            if repaired is not None:
                if enabled and reader is not None and retry_budget > 0 and any(
                    c.get("recovery_status") in ("unrecognized","suspicious_date_candidate")
                    for c in repaired.get("table_cells",[])):
                    try:
                        if retry_page != unit["page"]:
                            if retry_image is not None:
                                retry_image.close()
                            import pypdfium2
                            with pypdfium2.PdfDocument(pdf_path) as pdf:
                                page=pdf[unit["page"]-1]
                                bitmap=page.render(scale=6)
                                retry_image=bitmap.to_pil().copy()
                                bitmap.close()
                                page.close()
                            retry_page=unit["page"]
                        attempts=retry_uncertain_cells(repaired,reader,retry_image,6,
                                                       heights[unit["page"]],retry_budget)
                        retry_budget-=attempts
                        events["encoding_recovery"]["cell_retries"]+=attempts
                    except Exception as exc:
                        unit["cell_retry_error"]=str(exc)
                coverage=sum(c.get("recovery_status") != "unrecognized" for c in repaired["table_cells"])/len(repaired["table_cells"])
                unit["ocr_cell_coverage"]=coverage
                unit["table"] = repaired
                unit["text"] = table_markdown(repaired)
                if coverage >= .8:
                    status = "recovered_needs_review" if coverage == 1 else "partial_needs_review"
        elif accepted:
            local = [{"text":t["text"],"bbox":t["bbox"]} for t in accepted]
            unit["text"] = "\n".join(t["text"] for t in xy_order(local))
            status = "recovered_needs_review"
        elif tokens and unit["type"] == "picture_text" and any(
                tab["page"] == unit["page"] and overlap(tab["bbox"],unit["bbox"]) >= .9
                for tab in table_suspects):
            unit["text"] = "〔本區可辨識文字已歸入下列表格；其他內容待核對原圖〕"
            status = "partial"
        if status == "failed":
            # Never present the source gibberish as a successful result.
            unit["text"] = "〔文字編碼異常，局部 OCR 未能可靠恢復；請核對原 PDF〕"
            if not enabled:
                unit["recovery_error"] = "OCR disabled by --no-ocr"
            elif error:
                unit["recovery_error"] = error
            events["encoding_recovery"]["failed_units"] += 1
        else:
            unit["text_method"] = "encoding_fallback_ocr"
            key = "partial_units" if status.startswith("partial") else "recovered_units"
            events["encoding_recovery"][key] += 1
        unit["recovery_status"] = status
    if retry_image is not None:
        retry_image.close()
    events["encoding_recovery"]["status"] = (
        "failed" if events["encoding_recovery"]["failed_units"] == len(suspects)
        else "completed_with_review_required")
    return events


def convert_docling(args):
    try:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions, EasyOcrOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption
    except ImportError as exc:
        print(f"Missing dependency: {exc}. Run: python -m pip install -r requirements.txt",
              file=sys.stderr)
        return 2
    options = PdfPipelineOptions()
    options.do_ocr = not args.no_ocr
    options.do_table_structure = True
    # OCR configuration differs between Docling releases.
    ocr_args = dict(lang=["ch_tra", "en"], use_gpu=args.gpu)
    fields = EasyOcrOptions.model_fields
    if "bitmap_area_threshold" in fields:
        ocr_args["bitmap_area_threshold"] = 0.0
    if "mode" in fields:
        ocr_args["mode"] = "full_page" if args.force_ocr else "default"
    else:
        ocr_args["force_full_page_ocr"] = args.force_ocr
    options.ocr_options = EasyOcrOptions(**ocr_args)
    converter = DocumentConverter(format_options={
        InputFormat.PDF: PdfFormatOption(pipeline_options=options)})
    logging.info("Parsing %s; first run may download models", args.pdf)
    conversion_args = {"raises_on_error": True}
    if args.page is not None:
        conversion_args["page_range"] = (args.page, args.page)
        logging.info("Processing only PDF page %s", args.page)
    result = converter.convert(args.pdf, **conversion_args)
    status = getattr(result.status, "value", str(result.status))
    if status != "success":
        raise RuntimeError(f"Conversion did not fully succeed: {status}; {result.errors}")
    raw = result.document.export_to_dict()
    return raw


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--output", type=Path, default=Path("output"))
    parser.add_argument("--force-ocr", action="store_true",
                        help="OCR every page; use for broken embedded text layers")
    parser.add_argument("--no-ocr", action="store_true")
    parser.add_argument("--gpu", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--page", type=int, help="Only process this PDF page (1-based)")
    parser.add_argument("--reuse-json", type=Path,
                        help="Reuse this PDF's existing Docling JSON; run quality checks and local OCR only")
    args = parser.parse_args(argv)
    cached_processing = {}
    if args.page is not None and args.page < 1:
        parser.error("--page must be at least 1")
    if args.no_ocr and args.force_ocr:
        parser.error("--no-ocr and --force-ocr cannot be combined")
    if args.reuse_json and (args.page or args.force_ocr):
        parser.error("--reuse-json cannot be combined with --page or --force-ocr")
    if args.reuse_json and not args.reuse_json.is_file():
        parser.error("--reuse-json file does not exist")
    if not args.pdf.is_file() or args.pdf.suffix.lower() != ".pdf":
        parser.error("Input must be an existing PDF file")
    if args.reuse_json:
        metadata_path = args.reuse_json.with_name(args.reuse_json.name.replace(".docling.json",".events.json"))
        if metadata_path != args.reuse_json and metadata_path.is_file():
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            cached_processing = metadata.get("processing",{})
            expected_hash = metadata.get("source",{}).get("sha256")
            if expected_hash and expected_hash != hashlib.sha256(args.pdf.read_bytes()).hexdigest():
                parser.error("Cached extraction belongs to a different PDF")
    paths = [args.output / f"{args.pdf.stem}.{suffix}" for suffix in
             ("docling.json", "events.json", "md")]
    if not args.overwrite and any(p.exists() for p in paths):
        parser.error("Output exists; choose another --output or use --overwrite")
    raw = (json.loads(args.reuse_json.read_text(encoding="utf-8"))
           if args.reuse_json else convert_docling(args))
    if not isinstance(raw, dict):
        return 2
    if "pages" not in raw or "body" not in raw:
        parser.error("Input JSON must be a Docling document, not events.json")
    events = refine_events(raw)
    events = recover_encoding(events, args.pdf, enabled=not args.no_ocr, gpu=args.gpu)
    events["source"] = {"filename": args.pdf.name,
                        "sha256": hashlib.sha256(args.pdf.read_bytes()).hexdigest()}
    events["processing"] = {"docling_version": importlib.metadata.version("docling"),
                            "ocr": cached_processing.get("ocr") if args.reuse_json else not args.no_ocr,
                            "languages": cached_processing.get("languages",["ch_tra","en"]),
                            "force_full_page": cached_processing.get("force_full_page") if args.reuse_json else args.force_ocr,
                            "selected_page": cached_processing.get("selected_page") if args.reuse_json else args.page,
                            "encoding_recovery_enabled": not args.no_ocr}
    events["processing"]["reused_docling_json"] = bool(args.reuse_json)
    events["warnings"].append("Per-block native/OCR attribution is unresolved.")
    if not events["blocks"]:
        events["warnings"].append("No text blocks extracted; inspect PDF and OCR settings.")
    events = segment_events(events)
    args.output.mkdir(parents=True, exist_ok=True)
    payloads=[json.dumps(raw,ensure_ascii=False,indent=2),
              json.dumps(events,ensure_ascii=False,indent=2),export_md(events["reading_units"],events["events"])]
    temporary=[path.with_name(path.name+".tmp") for path in paths]
    try:
        for path,payload in zip(temporary,payloads):
            path.write_text(payload,encoding="utf-8")
        for path,target in zip(temporary,paths):
            path.replace(target)
    finally:
        for path in temporary:
            path.unlink(missing_ok=True)
    for path in paths:
        print(path.resolve())
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        sys.exit(main())
    except Exception as exc:
        logging.exception("PDF conversion failed: %s", exc)
        sys.exit(1)
