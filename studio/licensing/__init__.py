"""Shared licensing for Standard Dataset, Protected Dataset, and Academic Studio.

Honesty note: this module raises the cost of casual redistribution. It does not
make extraction after authorized decryption impossible. Do not corrupt faculty
facts for watermarking.
"""

from studio.licensing.products import SKU, ProductEdition, editions

__all__ = ["SKU", "ProductEdition", "editions"]
