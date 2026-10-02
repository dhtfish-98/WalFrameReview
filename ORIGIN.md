# Source and contribution record

Technical source: [sqlite/sqlite](https://github.com/sqlite/sqlite) at fixed commit `9696acb0c77f1c1a7a400446686debc1312c94bc`. License: `LicenseRef-Public-Domain`; the original license text and original copyright notices are preserved.

This is a Codex-assisted implementation of the explicitly selected standalone scope below. It is not presented as original ownership of the upstream algorithms or as a full rewrite of an upstream platform. No source files have merely been renamed into the runtime package.

Scope: SQLite WAL 3007000 header, legal page sizes, both checksum byte orders, rolling frame checksums, salt/page declarations and commit/uncommitted-tail boundaries.

The upstream entry points, format layouts and relevant default file/network/execution paths were inspected in the fixed files listed in SOURCE_MANIFEST.json. Complete new runtime files are reviewed separately; this does not imply audit of unselected upstream platform code.

Excluded upstream capabilities: SQL/database execution, database engine, page payload interpretation, recovery and authenticity.

The repository owner must verify their actual contribution and authorization before using this record in an application. No CVE, rejected-model task, CVP acceptance or personal identity evidence has been invented.

The new standalone implementation is distributed under MIT. The upstream public-domain dedication is preserved verbatim in THIRD_PARTY_LICENSE.txt; it describes the upstream government/public-domain work, not the authorship of this new implementation.
