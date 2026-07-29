# Upload EBE INC to GitHub

## Fastest method

1. Extract `EBE-INC-GitHub-Hub-v2.0.0.zip`.
2. Create a new GitHub repository named `ebe-inc`.
3. Choose **Add file → Upload files**.
4. Drag every extracted file and folder into the upload area, including `.nojekyll`.
5. Commit to `main`.
6. Open **Settings → Pages**.
7. Set the source to **Deploy from a branch**.
8. Select `main` and `/(root)`.
9. Save and wait for the published address to appear.

## Important

- Upload the extracted contents, not the ZIP file.
- `index.html` must be directly at the repository root.
- Keep the `assets` and `downloads` folders intact.
- A public repository exposes the website source through GitHub even though the site itself only presents APK downloads.
