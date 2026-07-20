"""Cloud-native modernization of the CardDemo core batch pipeline.

The package re-implements the COBOL/VSAM batch programs POSTTRAN (CBTRN02C),
INTCALC (CBACT04C), COMBTRAN (SORT), CREASTMT (CBSTM03A) and TRANREPT (CBTRN03C)
as containerizable services backed by PostgreSQL. See ``BUSINESS_RULES.md`` for the
functional specification the services preserve.
"""

__version__ = "1.0.0"
