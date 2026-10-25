# UNKNOWN

## Setup & Installation

### Backend Prerequisites
Install backend requirements:
```bash
pip install -r backend/requirements.txt
```

To enable spaCy for named entity extraction, download the English language model:
```bash
python -m spacy download en_core_web_sm
```
*(If spaCy or the model is not installed, the accuracy engine automatically falls back to pure-Python entity extraction).*
