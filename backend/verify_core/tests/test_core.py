import json, unittest
from verify_core import *
from verify_core.evidence import (Corroboration, DocumentEvidence, ExternalEvidence, ExternalResearch,
    Inspection, Level, Mode, SearchInfo, SourceType, Verdict, to_dict)
from verify_core.numeric import NumericStatus, check_numeric, parse_quantities
from verify_core.claims import StatementKind, ClaimCategory, extract_statements, split_sentences
from verify_core.verdict import cluster_external
from verify_core.pipeline import verify_claim

PASSAGE = ("Under the neutral storage model with mutation rate u=10^-6, a single copy achieved "
           "recovery accuracy of 0.767 after 3,000 generations.")
CLAIM = PASSAGE

def doc(text=PASSAGE, page=7):
    return DocumentEvidence("d1", "paper.pdf", text, page=page, chunk_id="c1")

def ext(text, st=SourceType.PRIMARY_PAPER, insp=Inspection.FULL_TEXT, url="https://doi.org/10.1/x", **kw):
    return ExternalEvidence(url=url, passage=text, source_type=st, inspection=insp, **kw)

def boom(_): raise AssertionError("must not be called")


class ClaimTests(unittest.TestCase):
    def test_strips_instruction_prefix_and_tail(self):
        t = f"Verify this claim: {CLAIM} and return supporting evidence."
        v = [s for s in extract_statements(t) if s.kind == StatementKind.VERIFIABLE]
        self.assertEqual(len(v), 1)
        self.assertEqual(v[0].text, CLAIM.rstrip("."))  # original wording kept
        self.assertIn("0.767", v[0].numbers)

    def test_quoted_claim_inside_instruction(self):
        t = f'Please verify the following: "{CLAIM}"'
        v = [s for s in extract_statements(t) if s.kind == StatementKind.VERIFIABLE]
        self.assertEqual(len(v), 1); self.assertIn("0.767", v[0].text)

    def test_pure_instruction_is_not_a_claim(self):
        for t in ["Return supporting evidence for this.", "Check whether it is correct."]:
            self.assertFalse([s for s in extract_statements(t) if s.kind == StatementKind.VERIFIABLE])

    def test_non_verifiable_kinds(self):
        kinds = {s.text: s.kind for s in extract_statements(
            "We recommend using larger pools. Mutation may reduce accuracy in future. "
            "Is the model robust? We believe this design is elegant.")}
        self.assertEqual(set(kinds.values()), {StatementKind.RECOMMENDATION, StatementKind.HYPOTHESIS,
                                               StatementKind.QUESTION, StatementKind.OPINION})

    def test_sentence_split_keeps_decimals_and_abbrevs(self):
        s = split_sentences("Accuracy was 0.767 (Fig. 3). Smith et al. reported 0.7. Done here now.")
        self.assertEqual(len(s), 3)

    def test_category_and_citation(self):
        s = extract_statements("Our method outperforms the baseline by 4.2% [12].")[0]
        self.assertEqual(s.category, ClaimCategory.COMPARISON); self.assertTrue(s.citations)


class NumericTests(unittest.TestCase):
    def test_power_of_ten_forms_equal(self):
        vals = [parse_quantities(x)[0].value for x in ("u=10^-6", "u=10⁻⁶", "u = 1e-6", "u=1 x 10^-6")]
        self.assertTrue(all(abs(v - 1e-6) < 1e-15 for v in vals))

    def test_exact_match_with_conditions(self):
        r = check_numeric(CLAIM, PASSAGE)
        self.assertEqual(r.status, NumericStatus.MATCH); self.assertEqual(r.coverage, 1.0)

    def test_altered_value_is_mismatch(self):
        r = check_numeric(CLAIM.replace("0.767", "0.867"), PASSAGE)
        self.assertEqual(r.status, NumericStatus.MISMATCH)

    def test_rounding_tolerance(self):
        self.assertEqual(check_numeric(CLAIM.replace("0.767", "0.77"), PASSAGE).status, NumericStatus.MATCH)
        self.assertEqual(check_numeric(CLAIM.replace("0.767", "0.76"), PASSAGE).status, NumericStatus.MISMATCH)

    def test_percent_vs_fraction(self):
        r = check_numeric("The model reached accuracy of 76.7% on the test set.",
                          "The model reached accuracy of 0.767 on the test set.")
        self.assertEqual(r.status, NumericStatus.MATCH)

    def test_unit_conversion(self):
        r = check_numeric("The decoding latency was 1500 ms per read.", "The decoding latency was 1.5 s per read.")
        self.assertEqual(r.status, NumericStatus.MATCH)

    def test_incompatible_units_not_converted(self):
        r = check_numeric("The sample mass was 5 kg in the assay.", "The sample length was 5 m in the assay.")
        self.assertEqual(r.status, NumericStatus.INCOMPATIBLE_UNITS)

    def test_different_conditions_are_unresolved_not_contradiction(self):
        other = PASSAGE.replace("u=10^-6", "u=10^-4").replace("0.767", "0.512")
        r = check_numeric(CLAIM, other)
        self.assertEqual(r.status, NumericStatus.UNRESOLVED_CONDITIONS)

    def test_different_generations_unresolved(self):
        r = check_numeric(CLAIM, PASSAGE.replace("3,000", "500").replace("0.767", "0.9"))
        self.assertEqual(r.status, NumericStatus.UNRESOLVED_CONDITIONS)

    def test_irrelevant_passage_is_not_a_mismatch(self):
        r = check_numeric(CLAIM.replace("0.767", "0.9"), "Sequencing cost fell to 12 dollars per megabase in 2020.")
        self.assertEqual(r.status, NumericStatus.NOT_FOUND)

    def test_partial_when_one_number_wrong(self):
        c = "Accuracy was 0.767 and precision was 0.9 for the neutral storage model."
        p = "Accuracy was 0.767 and precision was 0.8 for the neutral storage model."
        self.assertEqual(check_numeric(c, p).status, NumericStatus.PARTIAL_MATCH)


class PipelineTests(unittest.TestCase):
    def test_document_only_never_calls_external(self):
        r = verify_claim(CLAIM, Mode.DOCUMENT_ONLY, retrieve_document=lambda c: [doc()], research_external=boom)
        self.assertEqual(r.verdict, Verdict.SUPPORTED)
        self.assertEqual(r.corroboration, Corroboration.NOT_CHECKED); self.assertIsNone(r.external)
        self.assertEqual(r.document.evidence[0].page, 7)
        self.assertTrue(any("No independent external" in l for l in r.limitations))

    def test_external_only_never_calls_document(self):
        res = ExternalResearch([ext(PASSAGE), ext(PASSAGE.replace("achieved", "obtained"), url="https://nature.com/a")],
                               SearchInfo(["q"], 2, 2, 0))
        r = verify_claim(CLAIM, Mode.EXTERNAL_ONLY, retrieve_document=boom, research_external=lambda c: res)
        self.assertEqual(r.verdict, Verdict.SUPPORTED); self.assertIsNone(r.document)

    def test_altered_value_contradicted_in_document(self):
        r = verify_claim(CLAIM.replace("0.767", "0.867"), Mode.DOCUMENT_ONLY, retrieve_document=lambda c: [doc()])
        self.assertEqual(r.verdict, Verdict.CONTRADICTED)

    def test_claim_not_in_document_is_unsupported(self):
        r = verify_claim("The pipeline sequenced 40 terabases of ocean water.", Mode.DOCUMENT_ONLY,
                         retrieve_document=lambda c: [doc()])
        self.assertEqual(r.verdict, Verdict.UNSUPPORTED)
        self.assertLessEqual(r.confidence.verdict_confidence, Level.MODERATE)

    def test_empty_retrieval(self):
        r = verify_claim(CLAIM, Mode.DOCUMENT_ONLY, retrieve_document=lambda c: [])
        self.assertEqual(r.verdict, Verdict.UNSUPPORTED)

    def test_retriever_failure_is_unverifiable_not_crash(self):
        def bad(c): raise RuntimeError("index down")
        r = verify_claim(CLAIM, Mode.DOCUMENT_ONLY, retrieve_document=bad)
        self.assertEqual(r.verdict, Verdict.UNVERIFIABLE)
        self.assertTrue(any("retrieval failed" in l for l in r.limitations))

    def test_combined_doc_supported_but_external_empty(self):
        res = ExternalResearch([], SearchInfo(["q"], 0, 0, 0))
        r = verify_claim(CLAIM, Mode.DOCUMENT_AND_EXTERNAL, retrieve_document=lambda c: [doc()],
                         research_external=lambda c: res)
        self.assertEqual(r.document.verdict, Verdict.SUPPORTED)
        self.assertEqual(r.corroboration, Corroboration.NOT_FOUND)
        self.assertTrue(any("not independently corroborated" in l for l in r.limitations))

    def test_combined_external_contradiction_wins(self):
        res = ExternalResearch([ext(PASSAGE.replace("0.767", "0.512"))], SearchInfo(["q"], 1, 1, 0))
        r = verify_claim(CLAIM, Mode.DOCUMENT_AND_EXTERNAL, retrieve_document=lambda c: [doc()],
                         research_external=lambda c: res)
        self.assertEqual(r.document.verdict, Verdict.SUPPORTED)
        self.assertEqual(r.external.verdict, Verdict.CONTRADICTED)
        self.assertEqual(r.verdict, Verdict.CONTRADICTED)

    def test_snippet_only_contradiction_cannot_decide(self):
        res = ExternalResearch([ext(PASSAGE.replace("0.767", "0.512"), insp=Inspection.SNIPPET_ONLY)],
                               SearchInfo(["q"], 1, 0, 0))
        r = verify_claim(CLAIM, Mode.EXTERNAL_ONLY, research_external=lambda c: res)
        self.assertEqual(r.verdict, Verdict.UNVERIFIABLE)

    def test_duplicate_sources_count_once(self):
        copies = [ext(PASSAGE, url=f"https://site{i}.com/story") for i in range(10)]
        self.assertEqual(len(cluster_external(copies)), 1)
        res = ExternalResearch(copies, SearchInfo(["q"], 10, 10, 0))
        r = verify_claim(CLAIM, Mode.EXTERNAL_ONLY, research_external=lambda c: res)
        self.assertEqual(r.external.independent_clusters, 1)
        self.assertLessEqual(r.confidence.verdict_confidence, Level.MODERATE)

    def test_derived_source_clusters(self):
        a = ext("Alpha beta gamma delta epsilon zeta eta theta", url="https://orig.org/p")
        b = ext("Totally reworded press coverage of the work", url="https://news.com/x", derived_from="https://orig.org/p/")
        self.assertEqual(len(cluster_external([a, b])), 1)

    def test_conflicting_evidence_lowers_confidence(self):
        res = ExternalResearch([ext(PASSAGE), ext(PASSAGE.replace("0.767", "0.512"), url="https://other.org/z")],
                               SearchInfo(["q"], 2, 2, 0))
        r = verify_claim(CLAIM, Mode.EXTERNAL_ONLY, research_external=lambda c: res)
        self.assertEqual(r.verdict, Verdict.PARTIALLY_SUPPORTED)
        self.assertLessEqual(r.confidence.verdict_confidence, Level.LOW)

    def test_invalid_citations_dropped_and_reported(self):
        bad_doc = DocumentEvidence("", "p.pdf", "", page=0)
        bad_ext = ExternalEvidence(url="not a url", passage="x")
        res = ExternalResearch([bad_ext, ext(PASSAGE)], SearchInfo(["q"], 2, 1, 0))
        r = verify_claim(CLAIM, Mode.DOCUMENT_AND_EXTERNAL, retrieve_document=lambda c: [bad_doc, "junk", doc()],
                         research_external=lambda c: res)
        self.assertGreaterEqual(len(r.citation_problems), 4)
        self.assertEqual(len(r.document.evidence), 1)

    def test_passage_must_exist_in_cited_chunk(self):
        r = verify_claim(CLAIM, Mode.DOCUMENT_ONLY, retrieve_document=lambda c: [doc()],
                         chunk_lookup=lambda d, c: "completely different text")
        self.assertTrue(any("not contained" in p for p in r.citation_problems))
        self.assertEqual(r.verdict, Verdict.UNSUPPORTED)

    def test_unavailable_external_sources_reported(self):
        res = ExternalResearch([], SearchInfo(["q"], 3, 0, 3, ["timeout"] * 3))
        r = verify_claim(CLAIM, Mode.EXTERNAL_ONLY, research_external=lambda c: res)
        self.assertEqual(r.verdict, Verdict.UNVERIFIABLE)
        self.assertTrue(any("could not be inspected" in l for l in r.limitations))

    def test_full_confidence_report_has_four_signals_and_serializes(self):
        r = verify_claim(CLAIM, Mode.DOCUMENT_ONLY, retrieve_document=lambda c: [doc()])
        c = r.confidence
        self.assertEqual(c.verdict_confidence, Level.HIGH)
        self.assertEqual({c.source_quality, c.evidence_coverage, c.search_completeness}, {Level.HIGH})
        json.dumps(to_dict(r))

if __name__ == "__main__":
    unittest.main()
