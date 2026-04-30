# Design Source Access

SafeRoute has a repo-local Figma design reference:

- File key: `hZn31Z6alrXnUoxyyKCrmq`
- URL: `https://www.figma.com/design/hZn31Z6alrXnUoxyyKCrmq`
- Expected/source account from repo docs: `rnva822@gmail.com`
- Current MCP account observed on 2026-04-27: `rnva822@gmail.com`
- Current Figma plan/seat observed on 2026-04-27: Starter team, View seat

## Current Blocker

The Figma MCP connector still cannot access the repo Figma file. The account now matches the expected repo account, but the tool reports that the file cannot be accessed. The observed account is on a Starter/View seat, which has very limited MCP access and may also lack file/team permissions for this design source.

The latest failed MCP inspection returned debug UUID `263f44c5-dea5-4f59-86bb-f545b01a9d17`.

## Required Fix

Use one of these options:

1. Confirm the file key is still valid and belongs to a Figma Design file.
2. Share the file or parent project/team with `rnva822@gmail.com`.
3. Upgrade the MCP-authenticated account from View/Starter to a seat/plan with sufficient MCP read access, if file sharing alone is not enough.
4. If a separate automation account is preferred, share the file with that account and authenticate the MCP connector as that account.

After access is fixed, verify:

- design tokens against implemented CSS;
- route cards and mode selector against the Figma components;
- responsive/mobile layout;
- reduced-motion behavior and state coverage.

## Release Fallback

Figma access is not a product-runtime blocker while browser QA remains passing. Until MCP access is restored, the verified React code and browser-tested UI are the source of truth for release readiness.

Launch-gate recommendation:

- Treat Figma as a design-governance gate, not a runtime MVP launch gate.
- For MVP runtime launch, require browser QA and e2e verification to pass.
- For brand/design-system launch governance, require MCP or human access to the source Figma file and a token/component review.
