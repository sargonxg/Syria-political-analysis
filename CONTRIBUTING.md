# Contributions

Use a small change focused on a specific source, record or workflow. Include an original public URL, the relevant publication/check date and a page or section locator for factual changes. Explain whether you are proposing a new question, paraphrasing a dated document or correcting an earlier record.

Do not paste full copyrighted articles or private material. Do not submit private correspondence, personal contact details, exact beneficiary locations or non-public employment records. Preserve the source's language where appropriate and identify translations.

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
