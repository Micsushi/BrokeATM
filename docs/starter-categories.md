# Starter Categories

`app/data/starter_categories.json` defines the app's default category set.

## How it works

- On startup, the app seeds starter categories only if the live `categories` table is empty.
- Those starter categories are copied into the real database and then behave like normal categories.
- Import matching uses the saved database categories, not the JSON file directly.

## Why this file exists

This keeps a clear split between:

- starter templates you want every new install or future new user to begin with
- live categories that people can rename, delete, merge, recolor, and edit freely

## If we add user accounts

When multi-user support is added, this file should stay the base template set.
The signup flow can copy these starter templates into that user's own categories.

## Editing rules

- Keep names lowercase.
- Use a 6-digit hex color like `#6366f1`.
- Put keywords in the `keywords` array.
- The file order is preserved when starter categories are copied into a fresh database.

## Note

Changing `starter_categories.json` does not rewrite categories already saved in an existing database.
It affects:

- a fresh local database
- any future "clone starter categories for new user" flow
- any future reseed/reset tool we add
