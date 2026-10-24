.PHONY: eval eval-full test eval-tests

PYTHON := python
BACKEND := backend

eval:
	cd $(BACKEND) && $(PYTHON) eval/run_eval.py \
		--sample 50 --fixture \
		--datasets scifact qasper beir_nfcorpus beir_scifact \
		--strategies bm25 faiss rrf rrf+rerank full \
		--output-dir eval/results
	@echo "Results written to backend/eval/results/"

eval-full:
	cd $(BACKEND) && $(PYTHON) eval/run_eval.py \
		--datasets scifact qasper beir_nfcorpus beir_scifact \
		--strategies bm25 faiss rrf rrf+rerank full \
		--output-dir eval/results

test:
	cd $(BACKEND) && $(PYTHON) -m pytest tests/ -m "not eval" -q

eval-tests:
	cd $(BACKEND) && $(PYTHON) -m pytest eval/ -m eval -v
