# Your first research case

This public repository contains code, documentation and public-source research. You can read, clone and run it without an account or paid API. It does **not** provide an anonymously accessible hosted desk. Your own running desk requires a private key; anyone holding that key can access all its cases.

To explore the public directory and compare reports without private case storage, use the [offline source-comparison application](media-assessment.md#use-the-offline-application). Its entered evidence trail and JSON/Markdown downloads need no access key. The steps below set up the separate private notebook.

## 1. Install locally

Use Python 3.12 and Git. No Docker or cloud account is needed for this route:

```sh
git clone https://github.com/sargonxg/Syria-political-analysis.git
cd Syria-political-analysis
python -m venv .venv
```

Activate the environment:

| Your shell | Command |
| --- | --- |
| macOS/Linux Bash | `. .venv/bin/activate` |
| Windows PowerShell | `.venv\Scripts\Activate.ps1` |

If Windows prevents activation, use `.venv\Scripts\python.exe -m pip ...` instead of `python -m pip ...`, and prefix the other executable commands with `.venv\Scripts\`. You do not need to change system execution policy.

```sh
python -m pip install -r requirements-desk.lock
python -m pip install --no-deps .
syria-analysis validate
analysis-desk-admin --database var/desk.sqlite3 restore-case --input examples/training-case.json
```

The last command installs an eight-record **fictional practice case**. Its institutions, notice and event are invented and labelled throughout; it is not Syria reporting. Running it a second time refuses to overwrite the existing case. To begin empty instead, replace that command with `analysis-desk-admin --database var/desk.sqlite3 migrate`.

## 2. Start your private desk

Choose your own private random key of at least 32 characters. The repository deliberately supplies no default key. Keep it out of Git, screenshots and command history. Enter it without echoing it:

**Bash**

```sh
read -rsp 'Private key (at least 32 characters): ' SYRIA_DESK_ACCESS_KEY; echo
export SYRIA_DESK_ACCESS_KEY
export SYRIA_DESK_DATABASE=var/desk.sqlite3
export SYRIA_DESK_SECURE_COOKIE=0
uvicorn syria_analysis.desk.app:create_app --factory --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
```

**Windows PowerShell**

```powershell
$deskKey = Read-Host 'Private key (at least 32 characters)' -AsSecureString
$env:SYRIA_DESK_ACCESS_KEY = [System.Net.NetworkCredential]::new('', $deskKey).Password
$env:SYRIA_DESK_DATABASE = 'var/desk.sqlite3'
$env:SYRIA_DESK_SECURE_COOKIE = '0'
uvicorn syria_analysis.desk.app:create_app --factory --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
```

Open **http://127.0.0.1:8000**, enter the same key and choose the training case. These settings are for HTTP on your own loopback interface only. For a cloud host, keep secure cookies enabled and follow the separate [private HTTPS/container instructions](deployment.md). A missing/short key fails at startup; if a browser cannot remain signed in on local HTTP, check the explicit loopback cookie setting above.

Stop the local server with Ctrl+C. The SQLite file in `var/` persists; restart with the same database path to reopen the case. That directory, private keys and backups are ignored by Git. Do not commit an exported personal case: exports contain notes and revision history.

## 3. Follow the practice chain

1. Open **TRAINING / A proposed community centre**. Its stored text says a proposal was made, while budget and opening dates remain unconfirmed. Publication day is a fictional scenario date, not the record's creation time.
2. Open **TRAINING / The notice describes a proposal**. Inspect the exact excerpt and paragraph locator. The saved claim records the document revision it cited. An exact match establishes traceability; it does not certify truth.
3. Follow its document link or open the document's backlinks. Notice that several records may depend on the **same** notice. They are not independent confirmations.
4. Open **TRAINING / Assessment, alternatives and next evidence**. It distinguishes evidence, judgment, assumptions, alternatives, gaps and indicators that could change the assessment.
5. Edit that note and save. Open **Revision history** to inspect earlier text. In another browser tab, a stale edit will be rejected rather than silently overwriting a newer revision.
6. Use **Export this case**. A clean database can restore it with `analysis-desk-admin --database var/restored.sqlite3 restore-case --input PATH_TO_EXPORT.json`. This preserves IDs, backlinks and history and rejects conflicting IDs.

The [worked case guide](../examples/README.md) explains why the example contains two claims but no verified implementation finding.

## 4. Start real research deliberately

Create a new case with a narrow question. Register a source and its public URL, then a document with text you may retain. Add a claim only when you can supply an exact passage and locator. Write your assessment as a note; link supporting and contrary material and explain uncertainty. Actors and events are analyst-authored records, not automatically verified facts.

For the repository's **real public-source directory and dated references**, explicitly run:

```sh
analysis-desk-admin --database var/desk.sqlite3 import-public --root .
```

This creates a separate public-research case and preserves source qualifications. Existing paraphrases import as attributed notes because their original passages are not bundled. Source profiles are not certifications of every article. Collection remains manual; opening the desk does not scrape websites or start a live feed.

Read the [architecture and provenance guide](architecture.md), [analytical method](analysis-method.md), [source qualifications](sources.md), [API contracts](desk-api.md) and [contribution guide](../CONTRIBUTING.md) when adapting the project. The current server is a shared single-operator notebook, not a multi-tenant production service. Cloud use still needs private access, HTTPS, persistent storage and protected backups.
