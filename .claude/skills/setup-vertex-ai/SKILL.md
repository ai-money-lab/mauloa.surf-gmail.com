---
name: setup-vertex-ai
description: Sets up Vertex AI authentication for nano-banana in Claude Code Web environments where the direct Gemini API (generativelanguage.googleapis.com) is blocked by TLS inspection. Configures service account, patches nano-banana to use aiplatform.googleapis.com, and verifies image generation works. Use when nano-banana returns 403 errors, or when setting up a new Claude Code Web session for image generation.
---

# Setup Vertex AI for nano-banana

Configures nano-banana to use Vertex AI (`aiplatform.googleapis.com`) instead of the direct Gemini API (`generativelanguage.googleapis.com`) which is blocked in Claude Code Web sandbox environments.

## When to Use

- nano-banana returns **403 Forbidden** errors
- Setting up a **new Google Cloud project** for image generation
- The TLS inspection proxy blocks `generativelanguage.googleapis.com`

## Diagnosis

First, confirm the issue is TLS inspection blocking:

```bash
# This should return 403 (blocked)
curl -s -o /dev/null -w "%{http_code}" "https://generativelanguage.googleapis.com/v1beta/models"

# This should return 404 (not blocked = Vertex AI route works)
curl -s -o /dev/null -w "%{http_code}" "https://us-central1-aiplatform.googleapis.com/"
```

## Setup Steps

### 1. Google Cloud Project Setup (User Action Required)

Guide the user through these steps:

1. **Enable Vertex AI API**:
   ```
   https://console.cloud.google.com/apis/library/aiplatform.googleapis.com?project=PROJECT_ID
   ```

2. **Create Service Account**:
   ```
   https://console.cloud.google.com/iam-admin/serviceaccounts?project=PROJECT_ID
   ```
   - Name: `nano-banana`
   - Role: **Vertex AI ユーザー** (Vertex AI User)

3. **Create JSON Key**:
   - Click the service account → Keys tab → Add Key → JSON
   - User pastes the JSON content

### 2. Save Service Account Key

```bash
# Save to nano-banana config (runtime)
cat > ~/.nano-banana/vertex-ai-key.json << 'KEYEOF'
{paste JSON here}
KEYEOF
chmod 600 ~/.nano-banana/vertex-ai-key.json

# Also save to repo secrets for SessionStart hook (persists across sessions)
mkdir -p $CLAUDE_PROJECT_DIR/.claude/secrets
cp ~/.nano-banana/vertex-ai-key.json $CLAUDE_PROJECT_DIR/.claude/secrets/vertex-ai-key.json
chmod 600 $CLAUDE_PROJECT_DIR/.claude/secrets/vertex-ai-key.json
```

### 3. Patch nano-banana for Vertex AI

Apply these modifications to `/root/.bun/install/global/node_modules/nano-banana-2/src/cli.ts`:

**a. Add Vertex AI model mapping** (before `DEFAULT_MODEL`):
```typescript
const VERTEX_MODEL_MAP: Record<string, string> = {
  "gemini-3.1-flash-image-preview": "gemini-2.0-flash-preview-image-generation",
  "gemini-3-pro-image-preview": "gemini-2.0-flash-preview-image-generation",
};
```

**b. Replace GoogleGenAI initialization** in `generateImage()`:
```typescript
// Check for Vertex AI service account key
const vertexKeyPath = process.env.GOOGLE_APPLICATION_CREDENTIALS
  || join(homedir(), ".nano-banana", "vertex-ai-key.json");
const useVertexAI = existsSync(vertexKeyPath);

let ai: GoogleGenAI;
if (useVertexAI) {
  const keyData = JSON.parse(readFileSync(vertexKeyPath, "utf-8"));
  const project = keyData.project_id;
  const location = process.env.VERTEX_AI_LOCATION || "us-central1";
  process.env.GOOGLE_APPLICATION_CREDENTIALS = vertexKeyPath;
  ai = new GoogleGenAI({ vertexai: true, project, location });
} else {
  ai = new GoogleGenAI({ apiKey });
}
```

**c. Remove unsupported config for Vertex AI**:
- Remove `tools: [{ googleSearch: {} }]` from config when `useVertexAI` is true
- Remove `imageConfig` from config when `useVertexAI` is true

**d. Map model name for Vertex AI**:
```typescript
const modelName = useVertexAI
  ? (VERTEX_MODEL_MAP[options.model] || options.model)
  : options.model;
```

### 4. Verify

```bash
nano-banana "test image: blue sky with clouds" -s 1K -o vertex-test
```

Expected output should show `Mode: Vertex AI (project-id / us-central1)` and generate an image.

## How It Works

- Claude Code Web runs behind a TLS inspection proxy (`Anthropic sandbox-egress-production`)
- The proxy blocks `generativelanguage.googleapis.com` (direct Gemini API) with 403
- Other `*.googleapis.com` subdomains including `aiplatform.googleapis.com` are NOT blocked
- Vertex AI provides the same Gemini models via `{region}-aiplatform.googleapis.com`
- Vertex AI requires OAuth (service account) instead of API key authentication
- The `@google/genai` SDK v1.42+ supports `vertexai: true` mode natively
- Bun's fetch respects the proxy environment variables (Node.js fetch does not)

## Model Name Mapping

| Direct Gemini API | Vertex AI |
|---|---|
| `gemini-3.1-flash-image-preview` | `gemini-2.0-flash-preview-image-generation` |
| `gemini-3-pro-image-preview` | `gemini-2.0-flash-preview-image-generation` |

## Files

| Path | Purpose |
|---|---|
| `~/.nano-banana/vertex-ai-key.json` | Service account key (runtime) |
| `.claude/secrets/vertex-ai-key.json` | Service account key (persisted, gitignored) |
| `.claude/hooks/setup-nano-banana.sh` | Auto-patches nano-banana on SessionStart |

## Troubleshooting

- **401 Unauthorized**: Service account key is invalid or Vertex AI API not enabled
- **404 Model not found**: Model name mapping is wrong, check VERTEX_MODEL_MAP
- **DNS resolution failed**: Bun must be used (not Node.js) as bun respects proxy env vars
- **No image generated, only text**: Remove `tools` and `imageConfig` from config in Vertex AI mode
