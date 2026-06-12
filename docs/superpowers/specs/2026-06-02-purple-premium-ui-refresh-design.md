# Purple Premium UI Refresh Design

## Goal

Refresh the full web app UI so it feels more refined, unified, and closer to a ChatGPT-like product surface while preserving the brand's deep purple identity.

## Visual Direction

- Use deep purple as the main brand/action color.
- Keep the overall surface quiet: off-white backgrounds, restrained borders, soft shadows, and dense but readable layouts.
- Purple should appear on primary actions, active navigation, focus rings, selected audit specs, drag states, and a few brand anchors.
- Avoid purple-dominant pages, decorative blobs, hero marketing layouts, and unrelated illustration.

## Scope

Apply the style system to:

- Public login and register pages.
- Authenticated app shell and sidebar.
- Upload composer and audit spec selector.
- Running/history task lists.
- Task detail and image status tables.
- Spec search chat surface.
- Admin user table and action controls.

## Interaction Rules

- Buttons, links, inputs, table rows, task rows, and upload zones should share consistent hover/focus feedback.
- Focus states must be visible and use the brand purple without layout shift.
- Existing UI contracts must remain unchanged:
  - audit specs stay checkbox multi-select;
  - no audit spec is selected by default;
  - missing spec submission remains rejected;
  - polling and report links keep existing selectors and data attributes.

## Implementation Notes

- Keep changes concentrated in `app/static/app.css` and only make template changes if markup is needed for styling.
- Do not introduce a UI framework, icon library, or JavaScript design dependency.
- Prefer CSS custom properties for colors, radius, shadow, and spacing.
- Preserve compact operational density; this is an audit workbench, not a landing page.

## Verification

- Run `node --check app/static/app.js`.
- Run focused frontend/template tests.
- Run full `npm run verify` before completion.
- Use browser screenshots for upload, task list, task detail/spec search, and public auth pages when possible.
