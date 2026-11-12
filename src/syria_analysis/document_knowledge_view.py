"""A self-contained, text-safe policy-document study; no external runtime requests."""

from __future__ import annotations

import base64
import hashlib
import html

CSS = """
:root{font-family:system-ui,sans-serif;color:#24342f;background:#fafbf8;font-size:15px;line-height:1.6}*{box-sizing:border-box}body{margin:0}main{max-width:1120px;margin:auto;padding:48px 24px}h1{font-size:clamp(28px,4vw,46px);line-height:1.12;max-width:850px;letter-spacing:-.04em}h2{font-size:23px;margin-top:40px}h3{font-size:17px}a{color:#126153}button,select{font:inherit;max-width:100%;padding:10px;background:white;color:#24342f;border:1px solid #83978b;border-radius:3px}select{width:100%}summary{cursor:pointer;padding:12px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f0f3ed;padding:18px;max-height:380px;overflow:auto}blockquote{border-left:2px solid #66978b;margin:12px 0;padding:8px 18px}small,.meta{color:#51655a}.meta{font-size:13px}.grid{display:grid;grid-template-columns:1.2fr 1fr;gap:32px}.row{border-top:1px solid #d3dcd3;padding:16px 0}.stats{display:flex;flex-wrap:wrap;gap:16px;margin:20px 0}.stats span{border:1px solid #d3dcd3;padding:10px 16px}.stats strong{display:block;font-size:22px}.label{font-size:12px;letter-spacing:.08em;text-transform:uppercase}.graph{width:100%;height:auto;border:1px solid #d3dcd3;background:white}svg text{font-size:13px;fill:#24342f}svg line{stroke:#a7bdb2;stroke-width:1.3}svg circle{fill:#e6efea;stroke:#456d5e}svg a:focus circle{stroke:#bf452e;stroke-width:3}article:target{outline:2px solid #bf452e;outline-offset:5px}code{overflow-wrap:anywhere}nav{display:flex;gap:22px;flex-wrap:wrap;margin:18px 0}[hidden]{display:none!important}.note{background:#edf2ec;padding:15px}table{border-collapse:collapse;width:100%}th,td{padding:10px;text-align:left;border-bottom:1px solid #d3dcd3}.scroll{overflow:auto}section{scroll-margin-top:20px}a:focus-visible,summary:focus-visible,select:focus-visible{outline:2px solid #bf452e;outline-offset:4px}@media(max-width:700px){.grid{grid-template-columns:1fr}main{padding:28px 18px}.stats{gap:8px}.stats span{flex:1;min-width:130px}h1{font-size:32px}}
"""
JS = """
const selector=document.getElementById('task');
function choose(){for(const panel of document.querySelectorAll('[data-task]'))panel.hidden=panel.dataset.task!==selector.value;document.getElementById('status').textContent=selector.selectedOptions[0].textContent;}
selector.addEventListener('change',choose);choose();
"""


def _hash(value):
    return base64.b64encode(hashlib.sha256(value.encode()).digest()).decode()


def viewer(text, receipt, model, selections, evaluations):
    e = lambda value: html.escape(str(value), quote=True)
    panels = []
    for task in model["tasks"]:
        key = task["id"]
        selection = selections[key]
        context = selection["context"]
        result = evaluations[key]
        claims = context["assertions"]
        paragraphs = {p["id"]: p for p in context["paragraphs"]}
        edge_lines, nodes = [], []
        claim_y = {claim["id"]: 56 + 47 * index for index, claim in enumerate(claims)}
        evidence_y = {pid: 56 + 40 * index for index, pid in enumerate(paragraphs)}
        cy = 56 + 47 * (len(claims) - 1) / 2
        for claim in claims:
            y = claim_y[claim["id"]]
            edge_lines.append(f'<line x1="80" y1="{cy}" x2="260" y2="{y}"/>')
            for pid in claim["paragraph_ids"]:
                edge_lines.append(
                    f'<line x1="260" y1="{y}" x2="535" y2="{evidence_y[pid]}"/>'
                )
            for required in claim["requires"]:
                other = claim_y[required]
                edge_lines.append(
                    f'<path d="M250 {y} C205 {y},205 {other},250 {other}" stroke="#ac8150" stroke-dasharray="3 3" fill="none"><title>{e(claim["id"])} requires {e(required)}</title></path>'
                )
            nodes.append(
                f'<a href="#{e(key)}-{e(claim["id"])}" aria-label="Inspect {e(claim["id"])}"><circle cx="260" cy="{y}" r="7"/><text x="270" y="{y + 18}">{e(claim["id"])}</text></a>'
            )
        for pid, y in evidence_y.items():
            nodes.append(
                f'<circle cx="535" cy="{y}" r="5"/><text x="548" y="{y + 5}">{e(pid)}</text>'
            )
        graph_height = 105 + max(len(claims) * 47, len(paragraphs) * 40)
        graph = f'<svg class="graph" viewBox="0 0 620 {graph_height}" role="group" aria-labelledby="{key}-graph-title"><title id="{key}-graph-title">Actual source, assertion, evidence and qualification relationships. Select an assertion to inspect it below.</title><text x="25" y="24">Source</text><text x="230" y="24">Draft assertion</text><text x="510" y="24">Passage</text>{"".join(edge_lines)}<circle cx="80" cy="{cy}" r="12"/><text x="20" y="{cy + 35}">Document</text>{"".join(nodes)}</svg>'
        details = []
        for claim in claims:
            subject = next(
                x for x in model["entities"] if x["id"] == claim["subject_id"]
            )
            target = next(x for x in model["entities"] if x["id"] == claim["object_id"])
            typed = f"{subject['type']} · {subject['label']} → {claim['relation_id']} → {target['type']} · {target['label']}"
            quotes = "".join(
                f"<blockquote><small>{e(pid)} · bytes {p['span']['start']}–{p['span']['end']}</small><p>{e(p['text'])}</p></blockquote>"
                for pid in claim["paragraph_ids"]
                for p in [paragraphs[pid]]
            )
            actor_labels = [
                next(x["label"] for x in model["entities"] if x["id"] == a)
                for a in claim["addressed_to_ids"]
            ]
            details.append(
                f'<article class="row" id="{e(key)}-{e(claim["id"])}"><span class="label">{e(claim["epistemic_type"])} · unreviewed draft</span><h3>{e(claim["id"])}</h3><p class="meta">{e(typed)}</p><p>{e(claim["statement"])}</p><p><strong>Source verb:</strong> {e(claim["source_verb"])}</p><p><strong>Qualification:</strong> {e(claim["qualifications"])}</p><p><strong>Addressed roles:</strong> {e("; ".join(actor_labels) or "No addressed actor encoded")}</p><p><strong>Required context:</strong> {e(", ".join(claim["requires"]) or "None declared")}</p><details><summary>Exact source passages and local UTF-8 spans</summary>{quotes}</details></article>'
            )
        panels.append(
            f'''<section data-task="{e(key)}"><h2>{e(task["label"])}</h2><p>{e(task["question"])}</p><div class="stats"><span><strong>{len(claims)}</strong>selected assertions</span><span><strong>{len(paragraphs)} / {result["total_paragraphs"]}</strong>selected text blocks</span><span><strong>{selection["prompt_bytes"]:,}</strong>complete prompt bytes</span></div><div class="grid"><div><h3>Follow the evidence</h3>{graph}<p class="meta">Solid links connect the source, draft assertions and exact passage IDs. Dashed links retain declared required context. The same relationships are listed below; spatial proximity has no analytical meaning.</p></div><div><h3>What does selection preserve?</h3><p>Explicit task seeds bring their declared qualifications. A small seed-only prompt misses: <strong>{e(", ".join(result["seed_only_missing_required_ids"]) or "none in this task")}</strong>.</p><div class="scroll"><table><caption>Exact UTF-8 prompt measurements</caption><thead><tr><th scope="col">Input</th><th scope="col">Bytes</th></tr></thead><tbody><tr><th scope="row">Original normalized source</th><td>{result["source_text_bytes"]:,}</td></tr><tr><th scope="row">All structured assertions</th><td>{result["full_structured_prompt_bytes"]:,}</td></tr><tr><th scope="row">Selected + dependencies</th><td>{result["selected_prompt_bytes"]:,}</td></tr><tr><th scope="row">Seeds only (negative comparison)</th><td>{result["seed_only_prompt_bytes"]:,}</td></tr></tbody></table></div><p class="meta">The structured prompt is larger than this short original. Compared with the full structured baseline, selection includes fewer records. Bytes are not tokens, cost, speed or evidence of better generated answers.</p><nav aria-label="{e(key)} exports"><a href="contexts/{e(key)}.json" download>Context JSON</a><a href="contexts/{e(key)}.txt" download>Draft prompt</a></nav></div></div>{"".join(details)}<details><summary>Inspect complete prompt, including omissions</summary><pre>{e(selection["prompt"])}</pre></details></section>'''
        )
    options = "".join(
        f'<option value="{e(t["id"])}">{e(t["label"])}</option>' for t in model["tasks"]
    )
    raw_notice = receipt.get("capture", {}).get(
        "transformation",
        "Offsets refer to the supplied document.txt text. Publisher completeness and source authenticity are not established.",
    )
    publication_link = (
        f'<a href="{e(receipt["uri"])}" target="_blank" rel="noopener noreferrer">Official publication</a>'
        if receipt.get("uri")
        else "<span>No original publication URL supplied</span>"
    )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'sha256-{_hash(JS)}'; style-src 'sha256-{_hash(CSS)}'; connect-src 'none'; img-src data:; base-uri 'none'; form-action 'none'"><link rel="icon" href="data:,"><title>Policy document → qualified context · TACITUS</title><style>{CSS}</style></head><body><main><p class="label">TACITUS · Local policy-document case</p><h1>One instrument. Its instructions, qualifications and gaps.</h1><p>{e(receipt["title"])} · signed {e(receipt.get("signed_on") or "not supplied")} · published {e(receipt["published_on"])}</p><p class="note">Historical document study. Complete source text is retained; {len(model["assertions"])} supplied semantic annotations are unreviewed drafts. This does not establish current legal status, implementation, complete semantic extraction or improved AI answers.</p><nav aria-label="Study navigation"><a href="#case">Explore a question</a><a href="#source">Complete captured text</a><a href="graph.jsonld" download>Qualified JSON-LD graph</a><a href="research.sqlite3" download>Local SQLite database</a></nav><section id="case"><h2>Choose a research task</h2><label for="task">Research question</label><select id="task">{options}</select><p id="status" class="meta" role="status"></p>{"".join(panels)}</section><section id="source"><h2>Source and normalization</h2><p>{e(raw_notice)}</p><p>Raw response SHA-256: <code>{e(receipt.get("sha256") or "not supplied")}</code><br>Normalized text SHA-256: <code>{e(receipt["normalized_sha256"])}</code></p><p>{e(receipt.get("license", {}).get("basis", "Source rights not supplied; review redistribution separately."))}</p><nav aria-label="Source files"><a href="document.txt">Normalized text</a><a href="receipt.json">Capture receipt</a>{publication_link}</nav><details><summary>Read every normalized text block</summary><pre>{e(text)}</pre></details></section></main><script>{JS}</script></body></html>"""
