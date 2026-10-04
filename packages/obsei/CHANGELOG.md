# Changelog

## [1.0.0-rc.2](https://github.com/obsei/obsei/compare/v1.0.0-rc.1...v1.0.0-rc.2) (2026-10-04)


### Bug Fixes

* **serve:** sign webhook timestamps and refuse replays outside a five-minute window ([#406](https://github.com/obsei/obsei/issues/406)) ([b21a415](https://github.com/obsei/obsei/commit/b21a415e3ee766ca4e332d080f077ae9eba00962))


### Documentation

* point installs at 1.0.0rc1 and document decision models and routing everywhere ([#401](https://github.com/obsei/obsei/issues/401)) ([96f6b23](https://github.com/obsei/obsei/commit/96f6b233820bfc35c439ba9c69af46953de7bdd8))

## [1.0.0-rc.1](https://github.com/obsei/obsei/compare/v1.0.0-alpha.1...v1.0.0-rc.1) (2026-10-04)


### Features

* **blog:** add blog.obsei.com with the first post, and SEO across the sites ([#397](https://github.com/obsei/obsei/issues/397)) ([f98dfc0](https://github.com/obsei/obsei/commit/f98dfc046b1199c3550e331fc21657555d4e3a1c))
* brand the website, docs and Studio with the logo colours ([#373](https://github.com/obsei/obsei/issues/373)) ([a3e96ca](https://github.com/obsei/obsei/commit/a3e96ca61e1db722218f535e3dc1585b2bc05abf))
* decision models for classify, a filter enricher and an ask grounding judge ([#393](https://github.com/obsei/obsei/issues/393)) ([5896826](https://github.com/obsei/obsei/commit/58968265f8a3014024379b367d9c0675d7e4778f))
* **demo:** stable theme labels, a clearer demo story and a multilingual demo option ([#385](https://github.com/obsei/obsei/issues/385)) ([d916cde](https://github.com/obsei/obsei/commit/d916cde3dddd874cbce9665acf10a45f16168dba))
* ordered routes and richer conditions on decision-model outputs ([#395](https://github.com/obsei/obsei/issues/395)) ([a2f030d](https://github.com/obsei/obsei/commit/a2f030df7a577065c432b15cec10744f8f656fb6))
* **studio:** privacy, decisions and trends panels with a demo that shows them off ([#396](https://github.com/obsei/obsei/issues/396)) ([4f67c4b](https://github.com/obsei/obsei/commit/4f67c4baa609dd214f11903510fa8bdb22fe5275))


### Bug Fixes

* build the image from uv.lock, normalise the version and tighten plugin pins ([#380](https://github.com/obsei/obsei/issues/380)) ([e39bfa0](https://github.com/obsei/obsei/commit/e39bfa04656d9dd88779751a8795c602658988ab))
* close privacy and egress gaps found in the 1.0.0a1 review ([#383](https://github.com/obsei/obsei/issues/383)) ([7cea91d](https://github.com/obsei/obsei/commit/7cea91d2e73ce838ea2f3c35d71906f1ce5f9a44))
* isolate pipeline failures and keep the store lock off network calls ([#382](https://github.com/obsei/obsei/issues/382)) ([3e5e721](https://github.com/obsei/obsei/commit/3e5e721dbafb1e397e7dd54ea413cc260d037063))
* **studio:** compute theme summaries once per snapshot ([#399](https://github.com/obsei/obsei/issues/399)) ([aaa6bed](https://github.com/obsei/obsei/commit/aaa6bed10106f3a024d19e7bd946f9a2abfa0901))
* **studio:** harden Studio and fix live-mode UX, with browser tests ([#381](https://github.com/obsei/obsei/issues/381)) ([6b7a790](https://github.com/obsei/obsei/commit/6b7a790db909c32298c4bdd663c7c56347b2f89d))


### Documentation

* add an examples gallery, REST recipes and HTML text support ([#387](https://github.com/obsei/obsei/issues/387)) ([de029a2](https://github.com/obsei/obsei/commit/de029a20703bdc4344044264acc99df0aece3b26))
* fix installation, Docker and reference docs found in the 1.0.0a1 review ([#379](https://github.com/obsei/obsei/issues/379)) ([5855aab](https://github.com/obsei/obsei/commit/5855aabaed4de5cdc85ccbe193db891b493f3105))

## [1.0.0-alpha.1](https://github.com/obsei/obsei/compare/v0.0.15...v1.0.0-alpha.1) (2026-10-04)


### Features

* add encrypted DuckDB feedback store ([#358](https://github.com/obsei/obsei/issues/358)) ([28251bd](https://github.com/obsei/obsei/commit/28251bdc969e733aee395259aaf04be125c16182))
* add local multilingual embeddings for themes ([#371](https://github.com/obsei/obsei/issues/371)) ([1245c40](https://github.com/obsei/obsei/commit/1245c400013f9b6945892f635784b68f3912f372))
* add optional person-name redaction ([#368](https://github.com/obsei/obsei/issues/368)) ([549d5f5](https://github.com/obsei/obsei/commit/549d5f5eb8325e911d7198d1d1654f21720e99c4))
* add role-based access and SSO proxy support to obsei serve ([#372](https://github.com/obsei/obsei/issues/372)) ([0061924](https://github.com/obsei/obsei/commit/0061924266dd6eca941b3d721481f0194fd6e451))
* phase 0.1 private core (1.0.0a1) ([#359](https://github.com/obsei/obsei/issues/359)) ([f94a15c](https://github.com/obsei/obsei/commit/f94a15cb1249e06153a4e731def20b88eb12abdb))
* phase 0.2 MCP and Claude plugin (1.0.0a2) ([#360](https://github.com/obsei/obsei/issues/360)) ([5eb50bb](https://github.com/obsei/obsei/commit/5eb50bb1f77e7a2609180040d6ec215e867a8ed9))
* phase 0.3 enterprise bring-your-own (1.0.0b1) ([#361](https://github.com/obsei/obsei/issues/361)) ([0d3aa49](https://github.com/obsei/obsei/commit/0d3aa4988a22571b762255307602ba474ce4197c))
* phase 0.4 themes and Studio (1.0.0rc1) ([#362](https://github.com/obsei/obsei/issues/362)) ([df3b172](https://github.com/obsei/obsei/commit/df3b17216e5bf47326087c501b24b4790741678a))
* schedule pipelines in obsei serve and isolate pipeline failures ([#365](https://github.com/obsei/obsei/issues/365)) ([4df012f](https://github.com/obsei/obsei/commit/4df012f2a5d9f56379f549265b12e3fcdd44cc9e))
* start the obsei rebuild with new core skeleton and automation ([#354](https://github.com/obsei/obsei/issues/354)) ([55eae7d](https://github.com/obsei/obsei/commit/55eae7d297c473930e5c03796c32d8ac05c35c13))


### Bug Fixes

* release the exact pre-release version ([#364](https://github.com/obsei/obsei/issues/364)) ([d325377](https://github.com/obsei/obsei/commit/d32537722bfaa9231535be136414e1a4e30ea56c))
