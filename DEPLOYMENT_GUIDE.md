# Free Deployment Guide

Deploying our new unified Finance A-R system for free is very achievable by taking advantage of modern cloud hosting providers that offer generous free tiers. Since your **Supabase Database** is already hosted in the cloud for free, we just need to deploy the **FastAPI Backend** and the **React Frontend**.

Here is the recommended 100% free deployment stack:

## The Free Stack

1. **Database:** Supabase (Already hosted and free)
2. **Frontend (React/Vite):** **Vercel** or **Netlify**
   - Vercel is highly recommended. It is completely free for hobbyists, extremely fast, and automatically redeploys whenever you push your code to GitHub.
3. **Backend (FastAPI):** **Render.com**
   - Render offers a free "Web Service" tier. It can host your Python FastAPI backend directly from your GitHub repository. *(Note: Render's free tier goes to sleep after 15 minutes of inactivity, so the very first request after it sleeps might take ~30 seconds to wake up, but subsequent requests are fast).*

---

## Step-by-Step Free Deployment Process

To use these free services, your code needs to be hosted on a free GitHub account.

### Step 1: Push Code to GitHub
1. Create a free account on [GitHub.com](https://github.com).
2. Create a new private or public repository.
3. Push your `Finance---A-R` code to this GitHub repository.

### Step 2: Deploy the Backend on Render.com (Free)
1. Go to [Render.com](https://render.com) and sign up using your GitHub account.
2. Click **New +** and select **Web Service**.
3. Connect your GitHub account and select your `Finance---A-R` repository.
4. Set the following configuration:
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Plan:** Free
5. **Environment Variables:** Add your Supabase credentials here:
   - `SUPABASE_URL` = (your url)
   - `SUPABASE_KEY` = (your key)
   - `JWT_SECRET` = (your secret)
6. Click **Create Web Service**. Once it finishes deploying, Render will give you a free URL (e.g., `https://finance-api.onrender.com`).

### Step 3: Configure the Frontend to point to the new Backend
Before deploying the frontend, you need to tell it to talk to the new Render URL instead of `localhost`.
In your frontend code, you would create an environment variable (e.g., `VITE_API_BASE_URL`) or update your `axios` requests to point to `https://finance-api.onrender.com`.

### Step 4: Deploy the Frontend on Vercel.com (Free)
1. Go to [Vercel.com](https://vercel.com) and sign up using your GitHub account.
2. Click **Add New...** -> **Project**.
3. Import your `Finance---A-R` GitHub repository.
4. Vercel will automatically detect that you are using Vite and React.
5. Set the **Root Directory** to `frontend/` (since your React app is inside the `frontend` folder).
6. Click **Deploy**.

Vercel will give you a free, lightning-fast URL (e.g., `https://finance-ar.vercel.app`) where you can access your beautiful new web app from anywhere in the world!

---

Would you like me to make the quick code adjustments (like setting up the `VITE_API_BASE_URL` in the frontend) so the codebase is completely ready for this Vercel + Render approach?
