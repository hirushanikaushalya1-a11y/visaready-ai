# Put VisaReady AI online — no technical skills needed

This puts your tool on the internet as a **test website** (payments are in test mode — no real money).
You only click buttons in a web browser. It takes about 20 minutes, most of it waiting.

## Step 1 — Create a Render account (2 minutes)
1. Open **https://render.com** and click **Get Started**.
2. Choose **"Sign up with GitHub"** and allow access.

## Step 2 — Start the deployment (1 minute)
Open this link while signed in to Render:

**https://render.com/deploy?repo=https://github.com/hirushanikaushalya1-a11y/visaready-ai**

You will see a page listing two things to create: **visaready** (the website) and **visaready-db** (the database).

## Step 3 — Choose your admin login (1 minute)
Render asks for two values:
- **SEED_ADMIN_EMAIL** — your email address (this becomes the admin login).
- **SEED_ADMIN_PASSWORD** — a strong password (at least 10 characters, with capital letters, small letters and a number). Write it down.

Click **Deploy Blueprint** (or **Apply**). If Render asks for a payment card, it is for identity verification on the free plan.

## Step 4 — Wait (10–20 minutes)
Render builds the tool. You can watch the progress; it is finished when the website shows **"Live"** (green).

## Step 5 — Open your website
Click **visaready**, then the link at the top (it looks like `https://visaready-xxxx.onrender.com`).
- To test as an applicant: click **Get started** and register.
- To use the admin console: sign in with the email and password from Step 3.
- Sample documents to upload are in the `test-documents` folder of your GitHub repository.

## Good to know
- **Free plan sleeps**: after 15 minutes without visitors the site sleeps, and the next visit takes about a minute to wake up. Paid plans stay awake.
- **Free database**: Render's free database is temporary (check Render's current terms — free databases have historically been removed after about 30 days). Upgrade the database in Render before you store anything you want to keep.
- **Test mode**: payments are simulated. Real payments need a PayHere merchant account; emails need an email provider. Both are added later in Render under **visaready → Environment**.
- **Updates**: when new code is pushed to GitHub, Render rebuilds the site automatically.

## If something goes wrong
In Render, click **visaready → Logs**, take a screenshot, and send it to Claude.
