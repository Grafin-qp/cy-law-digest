"""Collector package for the Opiniq Cyprus law digest.

Modules:
  window      – reporting window arithmetic (previous ISO week by default)
  http        – HTTP client with retries, encoding handling and block detection
  model       – Item dataclass shared by all collectors
  relevance   – practice-area classification (keyword + taxonomy based)
  greekdates  – Greek date parsing helpers
  pdftext     – pdftotext wrapper
  gazette     – Επίσημη Εφημερίδα (Official Gazette) collectors
  cylaw       – CyLaw numbered index + per-law PDF headers
  nomoplatform– Nomoplatform WP REST API (bills, plenary decisions)
  govcy       – gov.cy central announcements API
  registrar   – Registrar of Companies news
  cbc         – Central Bank of Cyprus announcements
"""

__version__ = "2.0.0"
