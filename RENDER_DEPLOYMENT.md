# Render.com Deployment Guide

## Prerequisites

- [x] GitHub repository created and pushed
- [x] Render account created
- [x] PostgreSQL database created on Render

## Step 1: Configure Environment Variables

Go to your Render service Dashboard → **Environment** tab and add these variables:

### Required Variables

```env
# Database - Use "Internal Connection String" from your Render PostgreSQL
DATABASE_URL=postgresql+asyncpg://user:password@host/database

# Security - Generate with: openssl rand -hex 32
SECRET_KEY=your-generated-secret-key-here

# Environment
ENV=prod

# CORS - Add your frontend URL
CORS_ORIGINS=https://your-frontend-url.onrender.com
```

### Optional but Recommended

```env
# Rate limiting (recommended for production)
RATE_LIMIT_PER_MINUTE=60

# Admin credentials (change default!)
DEFAULT_ADMIN_USERNAME=admin
DEFAULT_ADMIN_PASSWORD=strong-password-here
```

### AI Features (Optional)

```env
# OpenAI Integration
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
ASSISTANT_ENABLE_LLM=True

# Google TTS (if using)
GOOGLE_TTS_API_KEY=...
```

## Step 2: Get Database Connection String

1. Go to your **PostgreSQL instance** on Render
2. Copy the **Internal Connection String**
3. Replace `postgresql://` with `postgresql+asyncpg://`
4. Set as `DATABASE_URL` environment variable

Example transformation:
```
FROM: postgresql://user:pass@host/db
TO:   postgresql+asyncpg://user:pass@host/db
```

## Step 3: Deploy

1. **Manual Deploy**: Click "Manual Deploy" → "Deploy latest commit"
2. **Auto Deploy**: Enable in Settings → "Auto-Deploy" (deploys on git push)

## Step 4: Monitor Deployment

Watch the logs in the Render Dashboard:
- Build logs: Check for dependency installation issues
- Runtime logs: Check for application startup

## Common Issues

### Issue: `Name or service not known`
**Solution**: DATABASE_URL is not set or incorrect
- Verify the environment variable is set
- Check the connection string format includes `+asyncpg`

### Issue: `ModuleNotFoundError`
**Solution**: Missing dependency in requirements.txt
- Check the logs for the missing module name
- Add it to `backend/requirements.txt`
- Commit and push

### Issue: `Application startup failed`
**Solution**: Check environment variables
- SECRET_KEY must be set
- DATABASE_URL must be accessible
- CORS_ORIGINS should include frontend URL

## Step 5: Verify Deployment

Once deployed, test the API:

```bash
# Health check
curl https://your-app.onrender.com/health

# API docs
open https://your-app.onrender.com/docs
```

## Frontend Configuration

Update your frontend environment to point to the backend:

```env
VITE_API_BASE_URL=https://your-backend.onrender.com
```

## Database Migrations

After first deployment, check if migrations ran:

```bash
# In Render Shell (Dashboard → Shell)
alembic current
alembic upgrade head
```

## Security Checklist

- [ ] Changed DEFAULT_ADMIN_PASSWORD
- [ ] Set strong SECRET_KEY (32+ characters)
- [ ] DATABASE_URL uses internal connection string
- [ ] CORS_ORIGINS includes only trusted domains
- [ ] RATE_LIMIT_PER_MINUTE is enabled (>0)
- [ ] ENV=prod is set

## Need Help?

Check logs in Render Dashboard → Logs tab for error messages.
