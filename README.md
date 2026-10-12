# AI Interview Coach

A practice tool for PM interviews. It writes role-specific questions,
scores your answers against a rubric, and shows a stronger version.

It can use three different AIs. You pick one in a settings file:

| Option | Cost | Needs |
|---|---|---|
| **Ollama** (default) | Free | Runs on your own computer, no key. Best with 8 GB+ of RAM. |
| **Gemini** | Free tier | A free key from Google |
| **Claude** (Anthropic) | Paid (cents) | A key and credit from console.anthropic.com |

## 1. Folder layout

Your folder must look like this, with `index.html` inside a folder named `static`:

```
interview-coach-fixed/
├── app.py
├── requirements.txt
├── env.example
├── README.md
└── static/
    └── index.html
```

## 2. Install the Python packages

In VS Code's terminal, inside this folder:

```bash
pip install -r requirements.txt
```

## 3. Make your settings file

Copy `env.example` and name the copy exactly `.env` (with the dot at the
front and nothing after it). The app reads it every time it starts, so
you only do this once. Never share or upload your `.env`.

## 4a. Using Ollama (free, on your computer)

1. Download and install Ollama from https://ollama.com/download, then open it.
2. In a terminal, download the model (about 5 GB, one time only):
   ```bash
   ollama pull llama3.1:8b
   ```
   On an older or slower laptop, use the smaller one instead:
   `ollama pull llama3.2:3b`, and put `MODEL=llama3.2:3b` in `.env`.
3. In `.env`, keep `PROVIDER=ollama`.

Answers take longer than with the cloud options, especially the first
one, and the feedback is less sharp than Gemini or Claude.

## 4b. Using Gemini (free tier)

1. Go to https://aistudio.google.com/apikey, sign in with Google, and click **Create API key**.
2. In `.env`, set:
   ```
   PROVIDER=gemini
   GEMINI_API_KEY=paste-your-key-here
   ```

The free tier has a per-minute limit. If you hit it, wait a minute.

## 4c. Using Claude (paid)

Run `pip install anthropic`, then in `.env` set `PROVIDER=anthropic` and
`ANTHROPIC_API_KEY=sk-ant-...`. You'll need credit at console.anthropic.com.

## 5. Run it

```bash
python app.py
```

The terminal says which AI it's using. Open **http://localhost:5000** in your browser.

## Troubleshooting

The red error on the page tells you what's wrong. The common ones:

- **"Not Found" in the browser:** `index.html` isn't inside the `static/` folder.
- **"Couldn't reach Ollama":** open the Ollama app, then try again.
- **"Ollama doesn't have the model":** run the `ollama pull ...` command it shows.
- **"key was rejected":** re-copy the key into `.env`, then stop the app (Ctrl+C) and run `python app.py` again.
- **"model ... wasn't found":** set a different `MODEL=` in `.env`.
- Anything else: read the last lines in the terminal running `python app.py`.

After you edit `.env`, stop the app with Ctrl+C and start it again.
