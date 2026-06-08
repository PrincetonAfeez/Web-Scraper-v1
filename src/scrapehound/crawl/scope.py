"""Domain scope checks."""

from __future__ import annotations

from scrapehound.crawl.normalize import domain_for_url


def _canonical_domain(domain: str) -> str:
    """Fold a host to its scope identity (treat www.X and X as the same site)."""
    domain = domain.lower()
    # Only strip a "www." label when something registrable remains, so a literal
    # host like "www.com" is not folded down to the bare TLD "com".
    if domain.startswith("www.") and "." in domain[4:]:
        domain = domain[4:]
    return domain


class DomainScope:
    def __init__(
        self,
        seed_url: str,
        *,
        stay_on_seed_domain: bool = True,
        allowed_domains: set[str] | None = None,
    ):
        self.seed_domain = _canonical_domain(domain_for_url(seed_url))
        self.stay_on_seed_domain = stay_on_seed_domain
        self.allowed_domains = {_canonical_domain(domain) for domain in (allowed_domains or set())}
        if self.seed_domain:
            self.allowed_domains.add(self.seed_domain)

    def allows(self, url: str) -> bool:
        if not self.stay_on_seed_domain:
            return True
        return _canonical_domain(domain_for_url(url)) in self.allowed_domains
