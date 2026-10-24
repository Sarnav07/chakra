# Deploy CHAKRA on Render

CHAKRA deploys as two services: a FastAPI API and a React static site. The
configuration is in `render.yaml`; do not commit the classifier model or any
token.

## 1. Publish the private classifier model

From the repository root, authenticate the GitHub CLI and create a private
release containing the locally trained model:

```bash
gh auth login
gh release create classifier-v1 backend/data/model/item_classifier.pt \
  --repo Sarnav07/chakra \
  --title "Classifier model v1" \
  --notes "Private deployment asset."
git push origin main
```

Create a fine-grained GitHub personal access token that has **Contents: Read**
permission for only the `Sarnav07/chakra` repository. Keep the token private.

## 2. Create the API service

1. Open the [Render Dashboard](https://dashboard.render.com/), select **New →
   Blueprint**, and connect `Sarnav07/chakra` on branch `main`.
2. Render reads `render.yaml` and creates `chakra-api` and `chakra-web`.
3. Before the API's first successful build, open `chakra-api` → **Environment**
   and add these secrets:

   ```text
   MODEL_URL=https://github.com/Sarnav07/chakra/releases/download/classifier-v1/item_classifier.pt
   GITHUB_TOKEN=<your read-only GitHub token>
   CHAKRA_CORS_ORIGINS=https://chakra-web.onrender.com
   ```

   If Render gives your static site a different URL, use that exact URL for
   `CHAKRA_CORS_ORIGINS` (without a trailing slash).

4. Deploy `chakra-api`, then verify:

   ```text
   https://chakra-api.onrender.com/api/health
   https://chakra-api.onrender.com/docs
   ```

## 3. Configure and deploy the static site

In `chakra-web` → **Environment**, set this build variable to the real API
URL, then manually redeploy the static site:

```text
VITE_API_BASE_URL=https://chakra-api.onrender.com
```

Open the static-site URL and check Dashboard, Forecast, Routes, Mess Log, and
Check Item. The Check Item screen should report that the classifier is
available.

## Notes

- Render's local filesystem is intentionally used only for this resettable
  hackathon demo. SQLite records, uploads, and generated runtime data can be
  lost after a restart or redeploy.
- The model is downloaded only during the backend build and is not added to
  Git history.
- Each push to `main` triggers a new build. The `MODEL_URL` and
  `GITHUB_TOKEN` secrets must remain configured for backend builds to succeed.
