# Dependency licenses

This project prefers permissive open-source licenses and keeps a record of all dependency licenses and compliance obligations.

| Dependency | Version | License | Purpose | Commercial-use restriction | Source URL | Replacement strategy |
| --- | --- | --- | --- | --- | --- | --- |
| Python | 3.13+ | PSF License | Runtime | Permissive | https://www.python.org/ | N/A |
| FastAPI | 0.115+ | MIT | API framework | Permissive | https://fastapi.tiangolo.com/ | Replaceable with ASGI-compatible server |
| SQLAlchemy | 2.x | MIT | ORM and database layer | Permissive | https://www.sqlalchemy.org/ | Replaceable with another async ORM |
| React | 19 | MIT | Frontend UI | Permissive | https://react.dev/ | Replaceable with another UI framework |
| Vite | 6.x | MIT | Build tooling | Permissive | https://vite.dev/ | Swap to alternate bundler |
| PostgreSQL | 17 | PostgreSQL License | Authoritative database | Permissive for self-hosting | https://www.postgresql.org/ | Alternate relational database |

The implementation is intentionally written to keep provider and vendor interfaces abstracted so that dependency replacements can happen without rewriting business logic.
