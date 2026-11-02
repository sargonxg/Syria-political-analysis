"""Regenerate the explicitly fictional practice case without touching a live database."""

import json
import tempfile
from pathlib import Path

from syria_analysis.desk.models import RecordWrite
from syria_analysis.desk.store import Store

ROOT = Path(__file__).resolve().parents[1]


def build():
    with tempfile.TemporaryDirectory() as directory:
        store = Store(Path(directory) / "training.sqlite3")
        case_id = "training-announcement-versus-outcome"
        store.create_case(
            "TRAINING ONLY / Does an announcement establish an outcome?", case_id
        )
        provenance = {
            "synthetic": True,
            "real_world_evidence": False,
            "purpose": "Fictional training material for evidence handling. No real actor, incident or source text is represented.",
        }

        def save(rid, **fields):
            return store.write(
                case_id,
                RecordWrite(**fields),
                rid="training-" + rid,
                metadata=provenance,
            )

        save(
            "source",
            kind="source",
            title="TRAINING / Example Council notices",
            url="https://example.org/",
            tags=["training", "synthetic"],
            body="Fictional publisher. example.org is a reserved example domain; this is not an actual council or a verified news source.",
        )
        passage = (
            "FICTIONAL TRAINING DOCUMENT. No real incident is described.\n\n"
            "On 15 January 2020, the Example Council proposed opening a community centre. "
            "The notice did not confirm a budget, construction start or opening date. "
            "The proposal will be reviewed at a later meeting.\n\n"
            "This invented notice is supplied only to practise exact excerpts, uncertainty and revision history."
        )
        save(
            "document",
            kind="document",
            title="TRAINING / A proposed community centre",
            source_id="training-source",
            body=passage,
            published_on="2020-01-15",
            tags=["training", "synthetic", "announcement"],
        )
        save(
            "actor",
            kind="actor",
            title="TRAINING / Example Council (fictional)",
            body="Fictional institution used in the training document. This record does not assert a real organizational role.",
            tags=["training", "synthetic"],
        )
        save(
            "theme",
            kind="theme",
            title="TRAINING / Public announcements and implementation",
            body="Research question: which separate records would establish funding, work begun, completion and use?",
            tags=["training", "synthetic", "governance"],
        )
        save(
            "event",
            kind="event",
            title="TRAINING / A proposal is announced",
            event_on="2020-01-15",
            body="Fictional announcement only. The event day is different from the creation time of this training record.",
            links=["training-actor", "training-document"],
            tags=["training", "synthetic"],
        )
        save(
            "claim-proposal",
            kind="claim",
            title="TRAINING / The notice describes a proposal",
            body="Attributed reading of the fictional notice. It does not establish that a facility opened.",
            document_id="training-document",
            excerpt="the Example Council proposed opening a community centre.",
            locator="Training document, paragraph 2, sentence 1",
            tags=["training", "synthetic", "proposal"],
        )
        save(
            "claim-limit",
            kind="claim",
            title="TRAINING / Budget and opening date are not confirmed",
            body="The absence of confirmation in this fictional notice does not prove that no funding or work exists elsewhere.",
            document_id="training-document",
            excerpt="The notice did not confirm a budget, construction start or opening date.",
            locator="Training document, paragraph 2, sentence 2",
            tags=["training", "synthetic", "information-gap"],
        )
        save(
            "assessment",
            kind="note",
            title="TRAINING / Assessment, alternatives and next evidence",
            body=(
                "Question: does this announcement establish a completed facility?\n\n"
                "Evidence: the fictional notice records a proposal and explicitly leaves milestones unconfirmed.\n\n"
                "Judgment: this document alone is insufficient to establish implementation.\n\n"
                "Assumption: the stored notice is complete. If it is only an extract, omitted passages may matter.\n\n"
                "Alternative: funding and work may be recorded in another document. Lack of confirmation is not proof of absence.\n\n"
                "Contrary evidence to seek: a dated budget decision, work record or independently sourced opening report.\n\n"
                "What would change the assessment: attributable records establishing the relevant milestone.\n\n"
                "TRAINING ONLY. This is a worked reasoning example, not an assessment of a real place."
            ),
            links=[
                "training-claim-proposal",
                "training-claim-limit",
                "training-event",
                "training-theme",
            ],
            tags=["training", "synthetic", "alternatives"],
        )
        return store.export(case_id)


if __name__ == "__main__":
    output = ROOT / "examples/training-case.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(build(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("Wrote fictional practice case; no live database was changed.")
