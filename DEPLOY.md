# Put the coach online (free)

This gives you a public link like `https://pm-interview-coach.onrender.com`
that anyone can open, with no account needed. It uses your free Gemini key.

You'll need a free GitHub account and a free Render account.

## 1. Get a Gemini key
Go to https://aistudio.google.com/apikey, sign in with Google, click
**Create API key**, and copy it.

## 2. Put the code on GitHub
1. Sign in at https://github.com and click **New** (green button) to make a repository.
2. Name it `pm-interview-coach`, choose **Public**, and click **Create repository**.
3. On the next page click **uploading an existing file**.
4. Drag in everything from this folder: `app.py`, `requirements.txt`,
   `render.yaml`, `README.md`, `DEPLOY.md`, `env.example`, `.gitignore`
   and the whole `static` folder. **Do not upload your `.env` file.**
5. Click **Commit changes**.

Tip: `.gitignore` starts with a dot, so your computer may hide it. It's
fine to skip it as long as you don't upload `.env`.

## 3. Deploy on Render
1. Go to https://render.com and sign up with your GitHub account.
2. Click **New** → **Blueprint**, pick your `pm-interview-coach` repository,
   and click **Connect**. Render reads `render.yaml` and sets everything up.
3. When it asks for `GEMINI_API_KEY`, paste your key. Click **Apply**.
4. Wait a few minutes for the build. When it says **Live**, click the
   `.onrender.com` link at the top. That's your public link.

## Good to know
- **First visit is slow.** Render's free plan sleeps when nobody has used
  it for a while. The first visit after that takes up to a minute to wake.
- **Limits protect your free quota.** Each visitor can make 30 AI requests
  an hour, and the whole app 400 a day. Change these in Render under
  **Environment** (`LIMIT_PER_PERSON_PER_HOUR`, `LIMIT_TOTAL_PER_DAY`).
  If people hit Gemini's own free limit, they'll see a "wait a minute" message.
- **Privacy.** On Gemini's free tier, Google may use what's sent to improve
  its products. Tell users not to paste anything confidential.
- **Your key stays secret.** It lives only in Render's settings, never in
  GitHub or the web page.
- **Updating.** Edit a file on GitHub (or upload a new version) and Render
  redeploys automatically.
