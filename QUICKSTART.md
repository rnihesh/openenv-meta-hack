# Quick Start Guide

## 🎯 Deploy in 5 Minutes

### 1. Create HF Space

Go to https://huggingface.co/new-space

- SDK: **Docker**
- Name: `ticket-triage-env`

### 2. Push Code

```bash
git remote add space https://huggingface.co/spaces/YOUR_USERNAME/ticket-triage-env
git push space main
```

### 3. Wait for Build

Watch logs at: `https://huggingface.co/spaces/YOUR_USERNAME/ticket-triage-env`

### 4. Validate

```bash
./validate-submission.sh https://YOUR_USERNAME-ticket-triage-env.hf.space .
```

### 5. Submit

Submit URL: `https://YOUR_USERNAME-ticket-triage-env.hf.space`

---

## 🧪 Test Locally First

```bash
# Build and run
docker build -t ticket-triage-env:latest -f server/Dockerfile .
docker run --rm -p 8000:8000 ticket-triage-env:latest

# In another terminal, test inference
export API_BASE_URL=""
export MODEL_NAME="heuristic"
export HF_TOKEN=""
python3 inference.py
```

Expected output:

```
[START] {"task": "easy", "env": "ticket_triage_env", "model": "heuristic"}
[STEP] {"step": 1, "action": {...}, "reward": 1.0, "done": false, "error": null}
...
[END] {"success": true, "steps": 2, "score": 0.975, "rewards": [1.0, 1.0]}
```

---

## 📋 What's Included

✅ Real-world ticket triage environment  
✅ 3 tasks with deterministic graders  
✅ Shaped reward function  
✅ Baseline inference script  
✅ Working Docker setup  
✅ Validation script  
✅ Full documentation

---

## 🔗 Key Files

- `inference.py` - Baseline inference script (required)
- `Dockerfile` - Container definition for HF Spaces
- `openenv.yaml` - Environment metadata
- `validate-submission.sh` - Pre-submission validator
- `DEPLOY.md` - Detailed deployment guide
- `SUBMISSION_CHECKLIST.md` - Full checklist

---

## 💡 Tips

1. **Test locally first** - Catch issues before deploying
2. **Check HF logs** - If build fails, logs show why
3. **Use heuristic mode** - Test without API keys first
4. **Validate before submit** - Run validation script

---

## 🆘 Common Issues

**Build fails**: Check Dockerfile and dependencies  
**Space won't start**: Check logs for Python errors  
**Validation fails**: Ensure Space is running first  
**Inference errors**: Verify ENV_BASE_URL is correct

See DEPLOY.md for detailed troubleshooting.

---

## 📊 Expected Scores

Heuristic (no LLM): ~0.85 average  
With GPT-4o-mini: ~0.90 average

---

Ready to deploy? Follow DEPLOY.md for step-by-step instructions! 🚀
