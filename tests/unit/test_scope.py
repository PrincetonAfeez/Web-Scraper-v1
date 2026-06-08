"""Unit test for scope."""

from __future__ import annotations

from scrapehound.crawl.scope import DomainScope


def test_www_is_equivalent_to_bare_domain():
    seed = DomainScope("http://example.com/")
    assert seed.allows("http://www.example.com/page")

    www_seed = DomainScope("http://www.example.com/")
    assert www_seed.allows("http://example.com/page")


def test_other_subdomains_and_domains_are_rejected():
    seed = DomainScope("http://example.com/")
    assert not seed.allows("http://blog.example.com/page")
    assert not seed.allows("http://evil.com/page")


def test_allowed_domains_extend_scope():
    seed = DomainScope("http://example.com/", allowed_domains={"www.partner.org"})
    assert seed.allows("http://partner.org/x")
    assert seed.allows("http://www.partner.org/x")


def test_stay_on_seed_domain_disabled_allows_anything():
    seed = DomainScope("http://example.com/", stay_on_seed_domain=False)
    assert seed.allows("http://anywhere.example/")


def test_www_fold_does_not_collapse_to_a_bare_tld():
    # "www.com" must stay distinct (not fold to "com").
    seed = DomainScope("http://www.com/")
    assert seed.allows("http://www.com/page")
    assert not seed.allows("http://other.com/page")
