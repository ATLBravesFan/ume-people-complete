# UME People Complete v5 — GitHub Pages edition

This repository generates a static Stremio catalog add-on for AIOMetadata/Strand using TMDB data.

## What it contains

- 59 actors × Movies + Shows = 118 actor catalogs
- 20 directors × Movies = 20 director catalogs
- 138 catalogs total
- Existing UME person catalog IDs preserved where they already existed
- 17 missing actor TV catalogs added
- Directors are filtered to TMDB crew credits whose `job` is exactly `Director`
- Actors use TMDB cast credits; obvious Self/archive-footage appearances are excluded
- No Cloudflare, no server, no MDBList quota, no self-hosting

## Important safety rule

Do **not** delete or replace your current AIOMetadata actor/director catalogs yet. Import this manifest alongside them, test it, then export your updated AIOMetadata configuration. The Strand library IDs for a custom manifest can differ from your existing MDBList-backed libraries, so the final Strand patch should be made only after AIOMetadata has created those libraries.

## Setup summary

1. Create a public GitHub repository.
2. Upload the **contents** of this folder (including `.github`).
3. Add repository secret `TMDB_API_KEY` containing your TMDB v3 API key.
4. Settings → Pages → Source: **GitHub Actions**.
5. Actions → **Build and deploy UME People catalogs** → Run workflow.
6. When deployment finishes, your manifest will be:
   `https://YOUR-GITHUB-USERNAME.github.io/YOUR-REPO-NAME/manifest.json`
7. Open that URL in Safari first. It should show JSON with `"catalogs"` and 138 catalog entries.
8. In AIOMetadata: Catalogs → Import Custom Manifest → paste the manifest URL.
9. Add/import the new catalogs but **leave your old actor/director catalogs in place for now**.
10. Save AIOMetadata.
11. Test Christopher Nolan, Steven Spielberg, Zendaya Movies, Zendaya Shows, and Adam Sandler Shows.
12. Export the newly saved AIOMetadata config and your current Strand `.strand` setup and send them back to ChatGPT for the exact final Strand remap.

## Useful test URLs

- `/health.json` — should say `status: ok`, `catalogs: 138`
- `/build-report.json` — generated counts for every person
- `/catalog/movie/mdblist.159441.json` — Christopher Nolan directed movies

## Updates

The GitHub Action runs once a day. It rebuilds the static catalogs from TMDB, so newly added credits can appear without you touching Strand.

## Rollback

Your current AIOMetadata and Strand exports remain the rollback. If the new custom manifest fails, remove/disable the newly imported catalogs and continue using the existing setup.
