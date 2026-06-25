FROM python:3.10-slim

# প্রয়োজনীয় সিস্টেম ডিপেন্ডেন্সি এবং আধুনিক নিয়মে Chrome ইনস্টল করা
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    curl \
    unzip \
    && mkdir -p /etc/apt/keyrings \
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /etc/apt/keyrings/google-chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# সরাসরি এখানেই লাইব্রেরিগুলো ইনস্টল করে নেওয়া
RUN pip install --no-cache-dir pyTelegramBotAPI selenium requests webdriver-manager

COPY . .

# বট রান করার কমান্ড
CMD ["python", "bot.py"]
