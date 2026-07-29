# Connect project-ashvector/ebeinc to ebeinc.online

This pack is prepared for:

- GitHub account: `project-ashvector`
- Repository: `ebeinc`
- Custom domain: `ebeinc.online`

The trailing `+` from the message is treated as a typo because GitHub repository names do not use `+` here.

## 1. Upload the site to GitHub

Open:

```text
https://github.com/project-ashvector/ebeinc
```

Upload every file from this folder to the repository root. Keep these files at the top level:

```text
index.html
.nojekyll
CNAME
```

The `CNAME` file already contains:

```text
ebeinc.online
```

## 2. Turn on GitHub Pages

1. Open the `ebeinc` repository.
2. Select **Settings**.
3. Select **Pages** under **Code and automation**.
4. Under **Build and deployment**, choose **Deploy from a branch**.
5. Choose branch `main` and folder `/(root)`.
6. Select **Save**.
7. In **Custom domain**, enter `ebeinc.online` and save.

Before the custom domain finishes, the project site should be available at:

```text
https://project-ashvector.github.io/ebeinc/
```

## 3. Add the DNS records

At the DNS provider for `ebeinc.online`, remove conflicting parking, redirect, or old A/CNAME records for `@` and `www`, then add exactly:

| Type | Host | Value | TTL |
|---|---|---|---|
| A | @ | 185.199.108.153 | Automatic |
| A | @ | 185.199.109.153 | Automatic |
| A | @ | 185.199.110.153 | Automatic |
| A | @ | 185.199.111.153 | Automatic |
| CNAME | www | project-ashvector.github.io | Automatic |

Do **not** put `/ebeinc`, `https://`, or a trailing slash in the `www` CNAME value.

## 4. Namecheap field mapping

In **Namecheap → Domain List → Manage → Advanced DNS**, use:

- `A Record` / Host `@` / Value `185.199.108.153`
- `A Record` / Host `@` / Value `185.199.109.153`
- `A Record` / Host `@` / Value `185.199.110.153`
- `A Record` / Host `@` / Value `185.199.111.153`
- `CNAME Record` / Host `www` / Value `project-ashvector.github.io`

Delete Namecheap parking records or URL redirects that use `@` or `www` before saving these records.

## 5. Enable HTTPS

Return to **GitHub repository → Settings → Pages**. When the DNS check passes, enable **Enforce HTTPS**.

DNS updates can take time to propagate. GitHub's certificate may also take up to about an hour after the DNS is correct.

## 6. Optional domain verification

For extra protection, verify `ebeinc.online` in the GitHub account's domain settings and keep the TXT verification record GitHub gives you.

## Troubleshooting

- **404 at project-ashvector.github.io/ebeinc/**: confirm Pages uses `main` and `/(root)` and that `index.html` is at the repository root.
- **Domain check failed**: remove conflicting DNS records and confirm all four A records are present.
- **www does not work**: confirm `www` is a CNAME to `project-ashvector.github.io`, not to the repository URL.
- **HTTPS option unavailable**: wait for DNS propagation, then remove and re-add `ebeinc.online` under GitHub Pages if needed.
- **CNAME disappears after an upload**: restore the root-level `CNAME` file containing only `ebeinc.online`.
