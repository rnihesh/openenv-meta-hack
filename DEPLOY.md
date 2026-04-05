# Deployment Guide

## 🚀 Deploy to Hugging Face Spaces

### Step 1: Create a New Space

1. Go to https://huggingface.co/new-space
2. Fill in the details:
   - **Space name**: `ticket-triage-env` (or your preferred name)
   - **License**: Choose appropriate license (e.g., MIT)
   - **Select the Space SDK**: Choose **Docker**
   - **Space hardware**: CPU basic (free tier works fine)
   - **Visibility**: Public or Private (your choice)

3. Click **Create Space**

### Step 2: Add Git Remote

```bash
# Replace YOUR_USERNAME with your HuggingFace username
git remote add space https://huggingface.co/spaces/YOUR_USERNAME/ticket-triage-env
```

### Step 3: Push to Hugging Face

```bash
git push space main
```

This will:

- Upload all your code to HF
- Trigger an automatic Docker build
- Start the container when build completes

### Step 4: Monitor Build Progress

1. Go to your Space URL: `https://huggingface.co/spaces/YOUR_USERNAME/ticket-triage-env`
2. Click on the **"Logs"** tab to watch the build
3. Wait for the message: `Application startup complete`
4. The Space will show "Running" status when ready

### Step 5: Test Your Deployed Space

```bash
# Test the /reset endpoint
curl -X POST https://YOUR_USERNAME-ticket-triage-env.hf.space/reset \
  -H "Content-Type: application/json" \
  -d '{"task_id": "easy"}'
```

Expected response: JSON with observation data and HTTP 200

### Step 6: Run Final Validation

```bash
./validate-submission.sh https://YOUR_USERNAME-ticket-triage-env.hf.space .
```

All 3 checks should pass:

- ✅ HF Space is live and responds to /reset
- ✅ Docker build succeeded
- ✅ openenv validate passed

### Step 7: Test Inference Against Deployed Space

```bash
# Set your API credentials
export API_BASE_URL="https://api.openai.com/v1"
export MODEL_NAME="gpt-4o-mini"
export HF_TOKEN="your-openai-api-key"

# Point to your deployed space
export ENV_BASE_URL="https://YOUR_USERNAME-ticket-triage-env.hf.space"

# Run inference
python3 inference.py
```

You should see [START], [STEP], and [END] logs for all 3 tasks.

### Step 8: Submit Your Space URL

Submit this URL to the competition:

```
https://YOUR_USERNAME-ticket-triage-env.hf.space
```

---

## 🔧 Troubleshooting

### Build Fails on HF

**Check the logs** in the HF Space dashboard. Common issues:

1. **Missing dependencies**: All deps are in Dockerfile, should work
2. **Timeout**: HF has build time limits, our build is ~2-3 minutes
3. **Memory issues**: CPU basic tier has 16GB RAM, sufficient for our env

### Space Shows "Building" Forever

- HF sometimes has queue delays
- Check the "Logs" tab for actual status
- If stuck >10 minutes, try restarting the Space

### /reset Returns 404 or 500

1. Check Space logs for Python errors
2. Verify the Space is in "Running" state
3. Try restarting the Space from the settings

### Validation Script Fails on Step 1

```bash
# Test manually first
curl -X POST https://YOUR_USERNAME-ticket-triage-env.hf.space/reset \
  -H "Content-Type: application/json" \
  -d '{}'
```

If this works but validation fails, check your Space URL format.

---

## 📊 Expected Performance

### Heuristic Baseline (no LLM)

- easy: 0.975
- medium: 0.65
- hard: 0.925
- average: 0.85

### With GPT-4o-mini

- easy: 0.95-1.0
- medium: 0.85-0.95
- hard: 0.75-0.90
- average: 0.85-0.95

---

## 🎯 Space Configuration

Your Space should have these settings:

**README.md frontmatter:**

```yaml
---
title: Ticket Triage OpenEnv
emoji: 📥
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
app_port: 8000
tags:
  - openenv
---
```

This is already in your README.md, so it will be automatically configured.

---

## 🔄 Updating Your Space

If you need to make changes:

```bash
# Make your changes locally
git add .
git commit -m "Update: description of changes"

# Push to HF (will trigger rebuild)
git push space main
```

The Space will automatically rebuild and redeploy.

---

## ✅ Final Checklist

Before submitting:

- [ ] Space is in "Running" state
- [ ] /reset endpoint returns 200
- [ ] /health endpoint returns {"status":"healthy"}
- [ ] validate-submission.sh passes all 3 checks
- [ ] inference.py runs successfully against deployed Space
- [ ] All 3 tasks (easy, medium, hard) complete

---

## 📞 Support

If you encounter issues:

1. Check HF Space logs first
2. Review SUBMISSION_CHECKLIST.md
3. Test locally with Docker to isolate issues
4. Verify all environment variables are set correctly

Good luck with your submission! 🚀
