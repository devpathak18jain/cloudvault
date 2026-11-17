# Step 2: Deploy CloudVault on AWS EC2 with Docker (beginner guide)

You do everything in the **browser**. Nothing needs installing on your laptop.
This reuses what you did in Lab Report 2 (Experiment 3 and 5: EC2 + Docker).

**What we are doing:** rent a small virtual server (EC2), install Docker on it, download the
project from GitHub, and start it with one command. Then anyone can open it using the
server's public IP address.

---
## PART A: Put the project on GitHub (10 min)
1. Unzip `cloudvault_step2.zip` on your laptop. You get a folder named `cloudvault`.
2. Log in to https://github.com (create a free account if needed).
3. Click **+** (top right) > **New repository**. Name: `cloudvault`. Choose **Public**. Click **Create repository**.
4. On the new page click the link **uploading an existing file**.
5. Open the `cloudvault` folder on your laptop, select **everything inside it** (the folders `cloudvault`, `tests`, `scripts` and all files), and drag them into the GitHub page.
   - Hidden files `.env.example`, `.gitignore`, `.dockerignore` must be included. If you cannot see them, turn on "Show hidden files" in your file explorer.
6. Click **Commit changes**.
7. Check that the repository shows `Dockerfile`, `docker-compose.yml`, `wsgi.py` and the folder `cloudvault`.
8. Copy the repository address, like `https://github.com/YOURNAME/cloudvault.git`. You need it in Part C.

> Take screenshot 1: the GitHub repository page.

---
## PART B: Launch the EC2 server (10 min)
1. Log in to the AWS Console. At the top right choose your region (for example **Asia Pacific (Mumbai) ap-south-1**).
2. Search for **EC2** and open it. Click **Launch instance**.
3. Fill in:
   - **Name:** `cloudvault-server`
   - **Image:** Amazon Linux 2023 AMI (Free tier eligible), architecture **64-bit (x86)**
   - **Instance type:** `t3.micro` (or the one marked "Free tier eligible")
   - **Key pair:** choose **Proceed without a key pair** (we connect from the browser)
4. Under **Network settings** click **Edit** and set:
   - Auto-assign public IP: **Enable**
   - Security group rules: keep **SSH (port 22)**, and click **Add security group rule**: Type **HTTP**, Source **Anywhere (0.0.0.0/0)**
5. **Storage:** leave 8 GiB.
6. Click **Launch instance**. Then click the instance ID.
7. Wait until **Instance state = Running** and **Status check = 2/2 passed** (about 2 minutes).

> Take screenshot 2: the instance page showing Running and the public IPv4 address.

---
## PART C: Install Docker and start CloudVault (15 min)
1. Select your instance, click **Connect**, tab **EC2 Instance Connect**, click **Connect**. A black terminal opens in the browser.
2. Run these commands **one at a time** (copy, paste, press Enter). Wait for each to finish.

**Install Docker and Git**
```bash
sudo dnf install -y docker git
sudo systemctl enable --now docker
sudo usermod -aG docker ec2-user
```
**Install Docker Compose**
```bash
sudo mkdir -p /usr/local/lib/docker/cli-plugins
sudo curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 -o /usr/local/lib/docker/cli-plugins/docker-compose
sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
```
**Reload your login so Docker works without sudo**
```bash
exit
```
Then in the AWS page click **Connect** again (EC2 Instance Connect > Connect). Now check:
```bash
docker --version
docker compose version
```
Both should print a version number.

> Take screenshot 3: the output of those two version commands.

**Download the project** (use YOUR GitHub address)
```bash
git clone https://github.com/YOURNAME/cloudvault.git
cd cloudvault
```
**Create the settings file with a random secret key**
```bash
cp .env.example .env
sed -i "s/^SECRET_KEY=.*/SECRET_KEY=$(openssl rand -hex 32)/" .env
```
**Build and start**
```bash
docker compose up --build -d
```
The first build takes 2 to 4 minutes. Then check:
```bash
docker compose ps
```
Wait until STATUS shows `(healthy)`. Run the command again after 30 seconds if it says `starting`.

> Take screenshot 4: `docker compose ps` showing healthy.

---
## PART D: Test it (5 min)
1. Run the automatic test on the server:
```bash
chmod +x scripts/smoke_test.sh
scripts/smoke_test.sh http://localhost
```
Every line must say PASS and the last line must say "All checks passed."

> Take screenshot 5: the smoke test output.

2. Open a new browser tab and go to `http://YOUR-PUBLIC-IP` (the IPv4 address from Part B).
   Use **http**, not https. The browser may say "Not secure"; that is expected for now, we add HTTPS later.
3. Click **Create one**, register, log in, upload a small file, download it, click **Share** and open the link in a private window.

> Take screenshot 6: the dashboard with your file in the browser, with the public IP visible in the address bar.

4. Show that the app does not run as root:
```bash
docker exec cloudvault-cloudvault-1 whoami
```
It prints `appuser`.

5. Show that data survives a restart:
```bash
docker compose down
docker compose up -d
```
Refresh the browser and log in again: your file is still there.

> Take screenshot 7: the file still present after restart.

---
## PART E: When you are done (important, to avoid charges)
- After showing sir: EC2 > select instance > **Instance state** > **Stop instance** (keeps the data, free).
- Do **not** leave it running for weeks. When the project is fully finished, choose **Terminate instance**.
- Every time you start it again, the public IP changes. Check the new one on the instance page.

## Common problems
| Problem | Fix |
|---|---|
| Browser cannot open the IP | Security group is missing HTTP port 80. EC2 > Security > click the group > Edit inbound rules > add HTTP 0.0.0.0/0 |
| `docker: permission denied` | You skipped the `exit` and reconnect step. Do it again |
| `docker compose` not found | Redo the "Install Docker Compose" commands |
| `git clone` asks for a password | Repository is Private. Make it Public in GitHub Settings |
| Status stays `starting` | Run `docker compose logs` and send me the last 20 lines |

## What to explain to sir (short)
- **IaaS:** EC2 gives us a raw server; we manage the OS and software.
- **Containerization:** Docker packs the app and its libraries into an image, so it runs the same everywhere.
- **Docker volume:** the database and files live outside the container, so they survive restarts.
- **Security:** non-root container user, CSRF protection, hashed passwords, security group only opens ports 22 and 80.
- **Health check:** Docker calls /health to know the app is alive.
