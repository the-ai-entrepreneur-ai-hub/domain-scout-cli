# Simple Web Crawler (PoC)

**Welcome!** This is a custom-built tool designed to automatically find and extract public business information from websites (like email addresses and company names) for a specific country/domain (e.g., `.de` for Germany).

It was built to be robust, efficient, and respectful of website rules.

## ⚡ Quick Start Guide

Follow these simple steps to get the crawler running on your machine.

### 1. Prepare the Folder
Ensure you have the project files on your computer (unzipped if necessary).
Open your terminal (Command Prompt or PowerShell) and **navigate inside this folder**.

### 2. Prerequisites
Make sure you have **Python** installed. If not, download it from [python.org](https://www.python.org/downloads/).

### 3. Installation
Run this command to install the necessary tools:

```bash
pip install -r requirements.txt
```

### 3. How to Run

The tool works in three steps: **Discover**, **Crawl**, and **Export**.

#### Step 1: Find Domains (Discovery)
First, we find a list of active websites. Replace `.de` with any extension you want (e.g., `.ch`, `.fr`).

```bash
python main.py discover --tld .de --limit 1000
```
*This will find up to 1000 domains ending in .de and save them to the database.*

#### Step 2: Extract Data (Crawling)
Now, the bot visits the websites found in Step 1 to find emails and company names.

```bash
python main.py crawl --concurrency 10
```
*You will see colorful logs showing the progress in real-time.*

#### Step 3: Save Results (Export)
Once finished, save the data to a readable Excel/CSV file.

```bash
python main.py export --tld .de
```
*Check the `data/` folder for your new CSV file!*

---

## 🛠️ Advanced Controls

- **Reset:** If the crawler gets stuck or you want to retry failed domains:
  ```bash
  python main.py reset
  ```
- **Stop:** To safely stop the crawler while it's running, just close the window or create a file named `STOP` in this folder.

## 📂 Output Data
Your exported CSV file will contain:
- **Domain:** The website address
- **Company Name:** Official name found on the site
- **Email:** Public contact email
- **Phone:** Public phone number
- **Description:** Short description of the website

## ⚠️ Important Note
This tool is a **Proof of Concept**. It respects `robots.txt` rules and includes a blacklist to avoid crawling massive sites like Amazon or Facebook. Please use responsibly and in accordance with local regulations (GDPR).

---
*Developed by George*
