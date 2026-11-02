# Contributions

Use a small change focused on a specific source, record or workflow. Include an original public URL, the relevant publication/check date and a page or section locator for factual changes. Explain whether you are proposing a new question, paraphrasing a dated document or correcting an earlier record.

Do not paste full copyrighted articles or private material. Do not submit private correspondence, personal contact details, exact beneficiary locations or non-public employment records. Preserve the source's language where appropriate and identify translations.

Start with the [quickstart](docs/quickstart.md) and [worked case](examples/README.md). Contributions to source corrections, documentation, accessibility and code are welcome.

Install development and optional desk test dependencies before checking a change:

```sh
python -m pip install -r requirements-desk.lock
python -m pip install -e '.[dev,desk,test]'
```

Before opening a change:

```sh
syria-analysis validate
python -m unittest discover -s tests -v
syria-analysis build-context
syria-analysis export-graph --format json
syria-analysis export-graph --format graphml
syria-analysis export-csv
```

For code changes, test the failure case that matters: lost provenance, invalid dates, dependent sources, overwritten reviewed records, unsafe XML or an incorrectly mapped reference. Avoid tests that merely reproduce an implementation detail.

For corrections, identify the record, source URL, locator and publication/review dates. Preserve the earlier evidence and explain the change. Geographic proximity does not establish affiliation; multiple reports repeating one origin are not independent confirmations.

Use synthetic examples in bug reports. Never attach private databases, keys, personal notes or real-account screenshots. See [security guidance](SECURITY.md). Code is MIT licensed; data is CC BY 4.0 subject to the underlying sources’ rights. The training fixture is fictional and separate from the public corpus. CI tests and builds; it does not deploy.
