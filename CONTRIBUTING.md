# Contributing

Thanks for your interest in contributing to BrkRaw.

We welcome contributions across:

- New sequence support (custom rules/specs/converter entrypoints)
- Reconstruction pipelines (FID-based or other custom paths)
- Image denoising or ML-powered workflows
- CLI plugins and tooling built on top of the BrkRaw API

## Extension points

You can extend BrkRaw without modifying core code:

- Add rules/specs/transforms via the `addon` CLI.
- Provide `converter_entrypoint` overrides for specialized conversion logic.
- Ship CLI plugins through `brkraw.cli` entrypoints.

See `docs/Addons-and-Plugins.md` for a detailed overview and examples in
`assets/examples/`.

## Defaults we want help with

We are looking for suggestions on default rules/specs to ship out of the box.
If you work with specific Bruker sequences, please propose:

- `info_spec` improvements for `brkraw info` / `BrukerLoader.info`.
- `metadata_spec` mappings for sidecar metadata (BIDS or lab standards).
- Rules that select the right spec based on `method`, `acqp`, or `visu_pars`.

Even small improvements (for example, better labels or parameter keys) are
useful. Open a PR or start a discussion with your sequence details and the
parameter files you rely on.

## Packaging and distribution

We encourage authors to package addons and plugins as standalone repositories
so they can be installed independently. This makes it easier to distribute new
tools to other labs and users.

## Community

If you build something useful, please open a PR or start a discussion. We plan
to periodically highlight community plugins on the BrkRaw main site.
