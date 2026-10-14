# Governance

obsei uses a lead-maintainer model for now. The lead maintainer is Lalit Pagaria
([@lalitpagaria](https://github.com/lalitpagaria)). The current maintainers are listed in
[MAINTAINERS.md](MAINTAINERS.md).

## Decisions

- Most decisions happen in pull requests and issues. A maintainer's approving review is enough to
  merge.
- Larger changes, such as a new connector family, a schema change or a change to the privacy
  model, start as a [Discussion](https://github.com/obsei/obsei/discussions) or an issue so others
  can weigh in before code is written.
- Maintainers aim for consensus. When there is none, the lead maintainer decides and records the
  reason in the thread.
- The [roadmap](ROADMAP.md) and the privacy principles in it guide what gets accepted.

## Becoming a maintainer

Contributors become maintainers after sustained, high-quality contributions over several months:
code, reviews, docs, triage or support in Discussions. Any maintainer can nominate someone, and the
nominee joins if the existing maintainers agree. Maintainers who are inactive for six months may
be moved to emeritus status and can return by asking.

## When there are three or more maintainers

Once at least three people are maintainers, the lead-maintainer model ends: decisions without
consensus go to a simple majority vote of maintainers, nominations need a majority, and changes to
this document need two thirds. Until then, the lead maintainer may change this document by pull
request.

## Code of conduct and security

Everyone follows the [Code of Conduct](CODE_OF_CONDUCT.md). Security reports go through
[SECURITY.md](SECURITY.md).
